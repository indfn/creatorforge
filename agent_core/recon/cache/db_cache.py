"""
SQLite-backed transcript cache for Content Skeleton Ripper.

Provides DbTranscriptCache — a persistent, thread-safe cache that replaces
the flat-file TranscriptCache with structured storage, TTL eviction, and
a migration helper to transfer existing flat-file entries.
"""

import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Tuple

from agent_core.recon.skeleton_ripper.cache import is_valid_transcript
from agent_core.recon.utils.logger import get_logger

logger = get_logger()

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_CACHE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "recon" / "cache"
DEFAULT_TTL_SECONDS = 2592000  # 30 days
FLAT_FILE_PATTERN = re.compile(r"^(.+?)_(.+?)_(.+)\.txt$")

# ── Thread safety ────────────────────────────────────────────────────────────
_global_lock = threading.Lock()


class DbTranscriptCache:
    """SQLite-backed transcript cache with TTL eviction.

    Thread-safe. Uses WAL mode and busy_timeout for concurrent access.
    Interface matches the flat-file TranscriptCache for drop-in replacement.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the cache.

        Args:
            db_path: Path to SQLite database file. If None, defaults to
                     RECON_DATA_DIR / 'transcript_cache.db'. Use ":memory:"
                     for in-memory (testing only).
        """
        self._lock = threading.Lock()
        self._db_path: Optional[str] = None
        self._conn: Optional[sqlite3.Connection] = None

        if db_path is None:
            db_path = os.environ.get(
                "RECON_CACHE_DB",
                str(DEFAULT_CACHE_DIR / "transcript_cache.db"),
            )

        if db_path and db_path != ":memory:":
            parent = Path(db_path).parent
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning("DB_CACHE", f"Could not create cache dir {parent}: {e}")
                self._db_path = None
                return

        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create the database and schema if needed."""
        if not self._db_path:
            return
        try:
            self._conn = sqlite3.connect(
                self._db_path,
                timeout=5,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA busy_timeout=5000;")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    username TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    transcript_text TEXT NOT NULL,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'whisper_api',
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ttl_seconds INTEGER DEFAULT 2592000,
                    UNIQUE(platform, username, video_id)
                );
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_lookup
                ON transcripts(platform, username, video_id);
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expiry
                ON transcripts(last_accessed_at, ttl_seconds);
            """)
            self._conn.commit()
        except Exception as e:
            logger.warning("DB_CACHE", f"Failed to init database: {e}")
            self._db_path = None
            self._conn = None

    def _is_expired(self, row: sqlite3.Row) -> bool:
        """Check if a row's TTL has expired.

        Compares last_accessed_at + ttl_seconds with current time.
        Does not query the database (safe to call within a lock).
        """
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            last_accessed_str = row["last_accessed_at"]
            ttl = row["ttl_seconds"]
            # Handle both ISO format and 'YYYY-MM-DD HH:MM:SS' from SQLite
            if isinstance(last_accessed_str, str):
                # SQLite CURRENT_TIMESTAMP is UTC, format: '2026-07-18 12:34:56'
                if "T" not in last_accessed_str:
                    last_accessed_str = last_accessed_str.replace(" ", "T")
                if "+" not in last_accessed_str and not last_accessed_str.endswith("Z"):
                    last_accessed_str += "Z"
                last_ts = datetime.fromisoformat(last_accessed_str)
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
            else:
                # Assume it's a float timestamp
                last_ts = datetime.fromtimestamp(float(last_accessed_str), tz=timezone.utc)

            from datetime import timedelta
            return last_ts + timedelta(seconds=ttl) < now
        except Exception:
            return False

    def get(self, platform: str, username: str, video_id: str) -> Optional[str]:
        """Retrieve a cached transcript.

        If the entry's TTL has expired, it is deleted and None is returned.
        On success, last_accessed_at is updated.

        Returns:
            The transcript text, or None if not found or expired.
        """
        if not self._conn:
            return None
        try:
            with self._lock:
                cur = self._conn.execute(
                    """SELECT transcript_text, last_accessed_at, ttl_seconds
                       FROM transcripts
                       WHERE platform=? AND username=? AND video_id=?""",
                    (platform, username, video_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                # Check TTL expiry
                if self._is_expired(row):
                    self._conn.execute(
                        """DELETE FROM transcripts
                           WHERE platform=? AND username=? AND video_id=?""",
                        (platform, username, video_id),
                    )
                    self._conn.commit()
                    logger.debug("DB_CACHE", f"TTL expired: {platform}/{username}/{video_id}")
                    return None

                # Update last_accessed_at
                self._conn.execute(
                    """UPDATE transcripts
                       SET last_accessed_at=CURRENT_TIMESTAMP
                       WHERE platform=? AND username=? AND video_id=?""",
                    (platform, username, video_id),
                )
                self._conn.commit()
                return row["transcript_text"]
        except Exception as e:
            logger.warning("DB_CACHE", f"Error reading {video_id}: {e}")
            return None

    def set(
        self,
        platform: str,
        username: str,
        video_id: str,
        transcript_text: str,
        source: str = "whisper_api",
        language: str = "en",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> bool:
        """Store a transcript in the cache.

        Skips storage if is_valid_transcript() returns False.

        Returns:
            True on success, False on failure or invalid transcript.
        """
        # Cache accepts transcripts with at least 2 words (protects against
        # single-word garbage like "short"). Pipeline-level quality threshold
        # (MIN_TRANSCRIPT_WORDS=10) is enforced by the caller, not the cache.
        if not is_valid_transcript(transcript_text, min_words=2):
            return False
        if not self._conn:
            return False
        try:
            word_count = len(transcript_text.split())
            with self._lock:
                self._conn.execute(
                    """INSERT OR REPLACE INTO transcripts
                       (platform, username, video_id, transcript_text, word_count,
                        source, language, last_accessed_at, ttl_seconds)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)""",
                    (platform, username, video_id, transcript_text,
                     word_count, source, language, ttl_seconds),
                )
                self._conn.commit()
            logger.debug("DB_CACHE", f"Cached: {platform}/{username}/{video_id} ({word_count}w)")
            return True
        except Exception as e:
            logger.warning("DB_CACHE", f"Error writing {video_id}: {e}")
            return False

    def exists(self, platform: str, username: str, video_id: str) -> bool:
        """Check if a valid (non-expired) transcript exists.

        Returns:
            True if exists and not expired, False otherwise.
        """
        if not self._conn:
            return False
        try:
            with self._lock:
                cur = self._conn.execute(
                    """SELECT last_accessed_at, ttl_seconds
                       FROM transcripts
                       WHERE platform=? AND username=? AND video_id=?""",
                    (platform, username, video_id),
                )
                row = cur.fetchone()
                if row is None:
                    return False
                if self._is_expired(row):
                    # Delete expired entry
                    self._conn.execute(
                        """DELETE FROM transcripts
                           WHERE platform=? AND username=? AND video_id=?""",
                        (platform, username, video_id),
                    )
                    self._conn.commit()
                    return False
                return True
        except Exception as e:
            logger.warning("DB_CACHE", f"Error checking existence: {e}")
            return False

    def clear_all(self) -> int:
        """Delete all cached transcripts.

        Returns:
            Number of deleted rows, or 0 on error.
        """
        if not self._conn:
            return 0
        try:
            with self._lock:
                cur = self._conn.execute("SELECT COUNT(*) FROM transcripts")
                count = cur.fetchone()[0]
                self._conn.execute("DELETE FROM transcripts")
                self._conn.commit()
                return count
        except Exception as e:
            logger.warning("DB_CACHE", f"Error clearing cache: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get statistics about the cache contents.

        Returns:
            dict with keys: total_transcripts, total_platforms, total_words, db_path
        """
        stats = {
            "total_transcripts": 0,
            "total_platforms": [],
            "total_words": 0,
            "db_path": str(self._db_path) if self._db_path else ":memory:",
        }
        if not self._conn:
            return stats
        try:
            with self._lock:
                cur = self._conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM transcripts"
                )
                row = cur.fetchone()
                stats["total_transcripts"] = row[0]
                stats["total_words"] = row[1]

                cur = self._conn.execute(
                    "SELECT DISTINCT platform FROM transcripts ORDER BY platform"
                )
                stats["total_platforms"] = [r[0] for r in cur.fetchall()]
        except Exception as e:
            logger.warning("DB_CACHE", f"Error getting stats: {e}")
        return stats


def migrate_from_flat_cache(
    flat_cache_dir: str,
    db_cache: DbTranscriptCache,
) -> Tuple[int, int]:
    """Migrate existing flat-file cache entries into SQLite.

    Scans flat_cache_dir for *.txt files named {platform}_{username}_{video_id}.txt,
    reads each, and stores them via db_cache.set().

    Args:
        flat_cache_dir: Path to the flat file cache directory.
        db_cache: An initialized DbTranscriptCache instance.

    Returns:
        Tuple of (total_found, total_migrated).
    """
    cache_path = Path(flat_cache_dir)
    if not cache_path.is_dir():
        logger.warning("CACHE_MIGRATE", f"Flat cache dir not found: {flat_cache_dir}")
        return (0, 0)

    txt_files = sorted(cache_path.glob("*.txt"))
    total_found = len(txt_files)
    total_migrated = 0

    for txt_file in txt_files:
        match = FLAT_FILE_PATTERN.match(txt_file.name)
        if not match:
            logger.debug("CACHE_MIGRATE", f"Skipping non-matching file: {txt_file.name}")
            continue

        platform = match.group(1)
        username = match.group(2)
        video_id = match.group(3)

        try:
            content = txt_file.read_text(encoding="utf-8")
            if db_cache.set(
                platform, username, video_id, content,
                source="migrated",
            ):
                total_migrated += 1
                logger.debug(
                    "CACHE_MIGRATE",
                    f"Migrated: {platform}/{username}/{video_id}",
                )
            else:
                logger.debug(
                    "CACHE_MIGRATE",
                    f"Skipped (invalid): {platform}/{username}/{video_id}",
                )
        except Exception as e:
            logger.warning(
                "CACHE_MIGRATE",
                f"Error migrating {txt_file.name}: {e}",
            )

    logger.info(
        "CACHE_MIGRATE",
        f"Migrated {total_migrated}/{total_found} flat cache entries",
    )
    return (total_found, total_migrated)
