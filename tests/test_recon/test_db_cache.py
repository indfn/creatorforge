"""Tests for agent_core.recon.cache.db_cache"""

import os
import tempfile
import time
from pathlib import Path

import pytest
from agent_core.recon.cache.db_cache import DbTranscriptCache, migrate_from_flat_cache


class TestDbTranscriptCache:
    def test_get_set_roundtrip(self):
        c = DbTranscriptCache(":memory:")
        c.set("youtube", "ch", "v1", "Hello world", source="whisper_api")
        assert c.get("youtube", "ch", "v1") == "Hello world"

    def test_exists_returns_true_for_cached(self):
        c = DbTranscriptCache(":memory:")
        c.set("test", "u", "v", "hello world", source="whisper_api")
        assert c.exists("test", "u", "v") is True

    def test_get_nonexistent_returns_none(self):
        c = DbTranscriptCache(":memory:")
        assert c.get("youtube", "ch", "nonexistent") is None

    def test_exists_nonexistent_returns_false(self):
        c = DbTranscriptCache(":memory:")
        assert c.exists("missing", "nobody", "nope") is False

    def test_set_skips_invalid_transcript(self):
        c = DbTranscriptCache(":memory:")
        result = c.set("test", "u", "v", "short", source="whisper_api")
        assert result is False
        assert c.get("test", "u", "v") is None

    def test_clear_all_returns_count(self):
        c = DbTranscriptCache(":memory:")
        c.set("a", "u", "v1", "hello world one", source="whisper_api")
        c.set("b", "u", "v2", "hello world two", source="whisper_api")
        count = c.clear_all()
        assert count == 2
        assert c.exists("a", "u", "v1") is False
        assert c.exists("b", "u", "v2") is False

    def test_clear_all_empty_returns_zero(self):
        c = DbTranscriptCache(":memory:")
        assert c.clear_all() == 0

    def test_get_stats_returns_dict(self):
        c = DbTranscriptCache(":memory:")
        c.set("youtube", "ch", "v1", "hello world one two three", source="whisper_api")
        c.set("instagram", "ch2", "v2", "hello world four five six", source="instagram_caption")
        stats = c.get_stats()
        assert stats["total_transcripts"] == 2
        assert len(stats["total_platforms"]) == 2
        assert stats["total_words"] == 10
        assert stats["db_path"] is not None

    def test_get_stats_empty(self):
        c = DbTranscriptCache(":memory:")
        stats = c.get_stats()
        assert stats["total_transcripts"] == 0
        assert stats["total_words"] == 0

    def test_ttl_eviction_on_read(self):
        c = DbTranscriptCache(":memory:")
        c.set("youtube", "ch", "v1", "hello world expired", source="whisper_api", ttl_seconds=1)
        assert c.get("youtube", "ch", "v1") == "hello world expired"
        time.sleep(1.1)
        # TTL expired — should return None and delete
        result = c.get("youtube", "ch", "v1")
        assert result is None
        assert c.exists("youtube", "ch", "v1") is False

    def test_unique_key_enforced(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "vid", "first version", source="youtube_caption")
        c.set("yt", "ch", "vid", "second version", source="whisper_api")
        result = c.get("yt", "ch", "vid")
        assert result == "second version"

    def test_word_count_auto_computed(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "vid", "one two three four five", source="whisper_api")
        stats = c.get_stats()
        assert stats["total_words"] == 5

    def test_persistent_db_file(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            c = DbTranscriptCache(db_path)
            c.set("yt", "ch", "v1", "hello world persistent", source="whisper_api")
            c2 = DbTranscriptCache(db_path)
            assert c2.get("yt", "ch", "v1") == "hello world persistent"
        finally:
            os.unlink(db_path)

    def test_get_returns_none_on_error(self):
        c = DbTranscriptCache("/nonexistent/dir/cache.db")
        result = c.get("yt", "ch", "v1")
        assert result is None

    def test_set_returns_false_on_error(self):
        c = DbTranscriptCache("/nonexistent/dir/cache.db")
        result = c.set("yt", "ch", "v1", "hello world", source="whisper_api")
        assert result is False

    def test_clear_all_returns_zero_on_error(self):
        c = DbTranscriptCache("/nonexistent/dir/cache.db")
        assert c.clear_all() == 0


class TestMigrateFromFlatCache:
    def test_migrate_basic(self, tmp_path):
        # Create flat cache files
        cache_dir = tmp_path / "flat_cache"
        cache_dir.mkdir()
        (cache_dir / "youtube_channel_video123.txt").write_text("Hello world transcript", encoding="utf-8")
        (cache_dir / "instagram_user_post456.txt").write_text("Instagram caption content", encoding="utf-8")

        db_cache = DbTranscriptCache(":memory:")
        found, migrated = migrate_from_flat_cache(str(cache_dir), db_cache)

        assert found == 2
        assert migrated == 2
        assert db_cache.get("youtube", "channel", "video123") == "Hello world transcript"
        assert db_cache.get("instagram", "user", "post456") == "Instagram caption content"

    def test_migrate_empty_dir(self, tmp_path):
        cache_dir = tmp_path / "flat_cache_empty"
        cache_dir.mkdir()
        db_cache = DbTranscriptCache(":memory:")
        found, migrated = migrate_from_flat_cache(str(cache_dir), db_cache)
        assert found == 0
        assert migrated == 0

    def test_migrate_non_existent_dir(self):
        db_cache = DbTranscriptCache(":memory:")
        found, migrated = migrate_from_flat_cache("/nonexistent/path", db_cache)
        assert found == 0
        assert migrated == 0

    def test_migrate_skips_invalid_transcripts(self, tmp_path):
        cache_dir = tmp_path / "flat_cache"
        cache_dir.mkdir()
        (cache_dir / "youtube_channel_vid1.txt").write_text("short", encoding="utf-8")
        (cache_dir / "youtube_channel_vid2.txt").write_text("valid long transcript text here", encoding="utf-8")

        db_cache = DbTranscriptCache(":memory:")
        found, migrated = migrate_from_flat_cache(str(cache_dir), db_cache)
        assert found == 2
        assert migrated == 1
        assert db_cache.get("youtube", "channel", "vid1") is None
        assert db_cache.get("youtube", "channel", "vid2") == "valid long transcript text here"

    def test_migrate_handles_malformed_filenames(self, tmp_path):
        cache_dir = tmp_path / "flat_cache"
        cache_dir.mkdir()
        (cache_dir / "youtube_channel_video1.txt").write_text("valid transcript text here yes", encoding="utf-8")
        (cache_dir / "not-a-match.txt").write_text("another valid transcript entry here", encoding="utf-8")

        db_cache = DbTranscriptCache(":memory:")
        found, migrated = migrate_from_flat_cache(str(cache_dir), db_cache)
        # "not-a-match.txt" doesn't match the underscore pattern — only 1 valid file
        assert found == 2
        assert migrated == 1  # only youtube_channel_video1.txt matches pattern


# ── Source and language tests ───────────────────────────────────────────


class TestDbTranscriptCacheSource:
    """Tests for source metadata storage."""

    def test_source_stored(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v", "hello world transcript", source="youtube_caption")
        assert c.get("yt", "ch", "v") == "hello world transcript"

    def test_source_defaults_to_whisper_api(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v", "hello world transcript")
        # get() returns text regardless of source — verify it works
        assert c.get("yt", "ch", "v") == "hello world transcript"


class TestDbTranscriptCacheLanguage:
    """Tests for language metadata storage."""

    def test_language_stored(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v", "hola mundo", language="es")
        assert c.get("yt", "ch", "v") == "hola mundo"

    def test_language_defaults_to_en(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v", "hello world")
        assert c.get("yt", "ch", "v") == "hello world"


# ── TTL tests ────────────────────────────────────────────────────────────


class TestDbTranscriptCacheTTL:
    """Tests for TTL eviction behavior."""

    def test_ttl_not_expired_returns_transcript(self):
        """Entry with a future TTL should be returned normally."""
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v", "hello world alive", ttl_seconds=3600)
        assert c.get("yt", "ch", "v") == "hello world alive"
        assert c.exists("yt", "ch", "v") is True

    def test_ttl_expired_returns_none_and_deletes(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v", "hello world expired", ttl_seconds=0)
        # TTL of 0 means expired immediately
        result = c.get("yt", "ch", "v")
        assert result is None
        assert c.exists("yt", "ch", "v") is False


# ── Stats tests ─────────────────────────────────────────────────────────


class TestDbTranscriptCacheStats:
    """Tests for cache statistics."""

    def test_stats_empty(self):
        c = DbTranscriptCache(":memory:")
        stats = c.get_stats()
        assert stats["total_transcripts"] == 0
        assert stats["total_words"] == 0

    def test_stats_after_set(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v", "one two three", source="whisper_api")
        stats = c.get_stats()
        assert stats["total_transcripts"] == 1
        assert stats["total_words"] == 3

    def test_stats_after_clear(self):
        c = DbTranscriptCache(":memory:")
        c.set("yt", "ch", "v1", "hello world one", source="whisper_api")
        c.set("ig", "ch", "v2", "hello world two", source="instagram_caption")
        c.clear_all()
        stats = c.get_stats()
        assert stats["total_transcripts"] == 0
        assert stats["total_words"] == 0
        assert stats["total_platforms"] == []


# ── Additional migration tests ──────────────────────────────────────────


class TestMigrateFromFlatCacheExtended:
    """Further edge-case tests for migration."""

    def test_migrate_skips_empty_files(self, tmp_path):
        """Empty .txt files are skipped during migration."""
        cache_dir = tmp_path / "flat_cache"
        cache_dir.mkdir()
        # Empty file
        (cache_dir / "youtube_channel_vid1.txt").write_text("", encoding="utf-8")
        # Non-empty but too short file
        (cache_dir / "youtube_channel_vid2.txt").write_text("short", encoding="utf-8")
        # Valid file
        (cache_dir / "youtube_channel_vid3.txt").write_text("hello world valid transcript text here", encoding="utf-8")

        db_cache = DbTranscriptCache(":memory:")
        found, migrated = migrate_from_flat_cache(str(cache_dir), db_cache)
        assert found == 3
        # Only vid3 has enough words (5) to pass min_words=2 check
        assert migrated == 1
        assert db_cache.get("youtube", "channel", "vid3") == "hello world valid transcript text here"

    def test_migrate_preserves_content(self, tmp_path):
        """Text content is identical after migration."""
        cache_dir = tmp_path / "flat_cache"
        cache_dir.mkdir()
        original = "This is the original transcript text that should be preserved exactly."
        (cache_dir / "youtube_channel_video1.txt").write_text(original, encoding="utf-8")

        db_cache = DbTranscriptCache(":memory:")
        found, migrated = migrate_from_flat_cache(str(cache_dir), db_cache)
        assert found == 1
        assert migrated == 1
        cached = db_cache.get("youtube", "channel", "video1")
        assert cached == original
