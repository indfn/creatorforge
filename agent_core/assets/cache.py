"""
SQLite-backed asset cache with TTL eviction.

Provides :class:`AssetCache` — a cache-aside store for asset metadata and file paths.
Uses WAL mode with ``threading.Lock`` for safe single-process concurrent access.

Cache invariants:
    - ``expires_at IS NULL`` entries are **permanent** (consistent assets — D-11).
    - ``expires_at IS NOT NULL`` entries are evicted by :meth:`evict_expired`.
    - On cache HIT, the file is validated on disk before returning (Pitfall 2).
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import portalocker

logger = logging.getLogger(__name__)

#: Default path for the cache database under the project assets directory.
CACHE_DB_PATH = Path("assets/.cache/cache.db")
#: Default TTL for stock assets: 7 days (D-11).
DEFAULT_TTL_SECONDS = 604800
#: Maximum cache size before LRU eviction should trigger (Pitfall 4, T-10-04).
MAX_CACHE_SIZE_MB = 2048


class AssetCache:
    """SQLite-backed cache for downloaded asset metadata and file paths.

    Thread-safe for single-process concurrent access via ``threading.Lock``
    and SQLite WAL mode with a 5-second busy timeout (Pitfall 3).

    Usage::

        cache = AssetCache()
        cache.set("broll", "http://...", "abc12345", "/path/to/file.mp4", {})
        entry = cache.get("broll", "http://...")
        if entry:
            print(entry["file_path"])
    """

    def __init__(self, db_path: Path = CACHE_DB_PATH):
        """Initialise the cache, creating DB and table if they do not exist.

        Args:
            db_path: Path to the SQLite database file (string or Path).
        """
        if isinstance(db_path, str):
            db_path = Path(db_path)
        self.db_path = db_path.resolve()
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Database initialisation
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the SQLite database file and tables if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")               # Pitfall 3
            conn.execute("PRAGMA busy_timeout=5000;")              # Pitfall 3
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    id              TEXT PRIMARY KEY,
                    asset_type      TEXT NOT NULL,
                    source_url      TEXT NOT NULL,
                    content_hash    TEXT NOT NULL,
                    file_path       TEXT NOT NULL,
                    channel_id      TEXT,
                    scene_id        TEXT,
                    metadata        TEXT,
                    cached_at       TEXT NOT NULL DEFAULT (datetime('now')),
                    expires_at      TEXT,
                    ttl_seconds     INTEGER DEFAULT 604800,
                    file_size_bytes INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_type_source
                ON cache_entries(asset_type, source_url)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON cache_entries(expires_at)
            """)

    # ------------------------------------------------------------------
    # Timestamp helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        """Return the current UTC time as an ISO-format string.

        Uses the same format as :meth:`set` for ``expires_at`` so string
        comparisons are consistent.
        """
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def get(self, asset_type: str, source_url: str) -> Optional[dict]:
        """Retrieve a valid (non-expired) cache entry.

        If the entry exists and has not expired, the file is validated on disk
        (Pitfall 2 / T-10-03).  If the file is missing, the entry is deleted
        and ``None`` is returned.

        Returns:
            Row dict with keys matching the ``cache_entries`` columns, or
            ``None`` if not found, expired, or file is missing.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                now = self._now()
                row = conn.execute(
                    "SELECT * FROM cache_entries "
                    "WHERE asset_type=? AND source_url=? "
                    "AND (expires_at IS NULL OR expires_at > ?)",
                    (asset_type, source_url, now),
                ).fetchone()

                if row is None:
                    return None

                entry = dict(row)

                # Validate file exists on disk (Pitfall 2 / T-10-03)
                if not Path(entry["file_path"]).exists():
                    logger.warning(
                        "Cache entry %s points to missing file %s — deleting",
                        entry["id"],
                        entry["file_path"],
                    )
                    conn.execute(
                        "DELETE FROM cache_entries WHERE id=?",
                        (entry["id"],),
                    )
                    return None

                logger.debug(
                    "Cache HIT: %s/%s -> %s",
                    asset_type, source_url, entry["file_path"],
                )
                return entry

    def set(
        self,
        asset_type: str,
        source_url: str,
        content_hash: str,
        file_path: str,
        metadata: dict,
        ttl_seconds: Optional[int] = DEFAULT_TTL_SECONDS,
        channel_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        file_size_bytes: int = 0,
    ) -> None:
        """Insert or replace a cache entry.

        Args:
            asset_type: One of ``"broll"``, ``"image"``, ``"sfx"``, ``"character"``.
            source_url: Original asset URL.
            content_hash: 8-character SHA-256 hash of the source URL.
            file_path: Absolute path to the downloaded file on disk.
            metadata: Arbitrary metadata dict (serialised as JSON).
            ttl_seconds: Time-to-live in seconds, or ``None`` for permanent.
            channel_id: Optional channel name the asset belongs to.
            scene_id: Optional scene identifier the asset belongs to.
            file_size_bytes: File size in bytes (default 0).
        """
        entry_id = f"{asset_type}_{content_hash}"
        expires_at: Optional[str] = None
        if ttl_seconds is not None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            ).isoformat()

        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (id, asset_type, source_url, content_hash, file_path,
                     channel_id, scene_id, metadata, cached_at, expires_at,
                     ttl_seconds, file_size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
                    """,
                    (
                        entry_id,
                        asset_type,
                        source_url,
                        content_hash,
                        str(file_path),
                        channel_id,
                        scene_id,
                        json.dumps(metadata),
                        expires_at,
                        ttl_seconds,
                        file_size_bytes,
                    ),
                )
                logger.debug("Cache SET: %s -> %s", entry_id, file_path)

    # ------------------------------------------------------------------
    # Eviction & cleanup
    # ------------------------------------------------------------------

    def evict_expired(self) -> int:
        """Delete all expired cache entries.

        Returns:
            Number of rows deleted.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                now = self._now()
                cursor = conn.execute(
                    "DELETE FROM cache_entries "
                    "WHERE expires_at IS NOT NULL "
                    "AND expires_at < ?",
                    (now,),
                )
                deleted = cursor.rowcount
                logger.info("Evicted %d expired cache entries", deleted)
                return deleted

    def orphan_cleanup(self) -> int:
        """Remove cache entries pointing to files that no longer exist on disk.

        Iterates all entries and deletes those whose ``file_path`` does not
        resolve to an existing file (Pitfall 2 ongoing mitigation).

        Returns:
            Number of orphaned entries removed.
        """
        orphans: list[str] = []
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, file_path FROM cache_entries"
                ).fetchall()
                for row in rows:
                    if not Path(row["file_path"]).exists():
                        orphans.append(row["id"])

                for entry_id in orphans:
                    conn.execute(
                        "DELETE FROM cache_entries WHERE id=?", (entry_id,)
                    )

                count = len(orphans)
                if count:
                    logger.info("Orphan cleanup removed %d entries", count)
                return count

    # ------------------------------------------------------------------
    # Size management
    # ------------------------------------------------------------------

    def get_total_size_mb(self) -> float:
        """Return the total size of all cached files in megabytes.

        Uses the ``file_size_bytes`` column (an estimate) rather than querying
        the filesystem. Returns 0.0 if no entries exist.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(file_size_bytes), 0) FROM cache_entries"
                ).fetchone()
                total_bytes = row[0] if row else 0
                return total_bytes / (1024.0 * 1024.0)

    def clear(self) -> int:
        """Delete all cache entries.

        Returns:
            Number of rows deleted.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("DELETE FROM cache_entries")
                deleted = cursor.rowcount
                logger.info("Cache cleared: %d entries removed", deleted)
                return deleted
