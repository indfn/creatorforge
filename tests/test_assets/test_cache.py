"""
Tests for AssetCache — SQLite-backed cache with TTL eviction.

Covers:
    - get() returns dict on cache hit, None on miss
    - set() stores entries and respects ttl_seconds (including permanent)
    - evict_expired() removes expired rows and leaves valid ones
    - orphan_cleanup() removes entries with missing files
    - clear() removes all entries (Pitfall 2 mitigation test)
    - file validation on get(): returns None if file deleted on disk
"""

from pathlib import Path

import pytest


class TestAssetCache:
    """Tests for the AssetCache class."""

    # ------------------------------------------------------------------
    # Basic get/set
    # ------------------------------------------------------------------

    def test_set_and_get(self, sample_asset_cache):
        """Set an entry, then get it back as a dict with expected keys."""
        cache = sample_asset_cache
        cache.set(
            "broll",
            "http://example.com/v.mp4",
            "abc12345",
            "/tmp/test_exists.mp4",
            {"source": "pexels"},
            ttl_seconds=3600,
        )

        # Create the file so Pitfall 2 check passes
        Path("/tmp/test_exists.mp4").touch()

        entry = cache.get("broll", "http://example.com/v.mp4")
        assert entry is not None
        assert entry["asset_type"] == "broll"
        assert entry["source_url"] == "http://example.com/v.mp4"
        assert entry["content_hash"] == "abc12345"
        assert entry["file_path"] == "/tmp/test_exists.mp4"
        assert entry["ttl_seconds"] == 3600
        assert entry["expires_at"] is not None  # not permanent

    def test_get_missing_returns_none(self, sample_asset_cache):
        """Get with an unknown asset_type + source_url returns None."""
        cache = sample_asset_cache
        result = cache.get("broll", "http://example.com/nonexistent.mp4")
        assert result is None

    def test_get_returns_dict_with_expected_keys(self, sample_asset_cache):
        """Returned dict contains all cache_entries columns."""
        cache = sample_asset_cache
        Path("/tmp/test_keys.mp4").touch()
        cache.set(
            "image",
            "http://example.com/img.jpg",
            "def56789",
            "/tmp/test_keys.mp4",
            {"source": "test"},
            ttl_seconds=7200,
        )

        entry = cache.get("image", "http://example.com/img.jpg")
        assert entry is not None
        expected_keys = {
            "id", "asset_type", "source_url", "content_hash", "file_path",
            "channel_id", "scene_id", "metadata", "cached_at", "expires_at",
            "ttl_seconds", "file_size_bytes",
        }
        assert expected_keys.issubset(entry.keys())

    # ------------------------------------------------------------------
    # TTL / expiry
    # ------------------------------------------------------------------

    def test_expired_entry_returns_none(self, sample_asset_cache):
        """Entry with ttl_seconds=0 should be expired and return None."""
        cache = sample_asset_cache
        Path("/tmp/test_expired.mp4").touch()
        cache.set(
            "broll",
            "http://example.com/expired.mp4",
            "expired01",
            "/tmp/test_expired.mp4",
            {},
            ttl_seconds=0,  # Immediate expiry
        )

        result = cache.get("broll", "http://example.com/expired.mp4")
        assert result is None

    def test_permanent_entry_never_expires(self, sample_asset_cache):
        """Entry with ttl_seconds=None is permanent and always returned."""
        cache = sample_asset_cache
        Path("/tmp/test_permanent.mp4").touch()
        cache.set(
            "broll",
            "http://example.com/permanent.mp4",
            "perm0001",
            "/tmp/test_permanent.mp4",
            {},
            ttl_seconds=None,  # Permanent
        )

        result = cache.get("broll", "http://example.com/permanent.mp4")
        assert result is not None
        assert result["expires_at"] is None

    def test_short_ttl_eventually_expires(self, sample_asset_cache):
        """Entry with a very short TTL (1 second) expires after waiting."""
        import time

        cache = sample_asset_cache
        Path("/tmp/test_short_ttl.mp4").touch()
        cache.set(
            "broll",
            "http://example.com/short_ttl.mp4",
            "short001",
            "/tmp/test_short_ttl.mp4",
            {},
            ttl_seconds=1,
        )

        # Should be valid immediately
        assert cache.get("broll", "http://example.com/short_ttl.mp4") is not None

        # Wait for expiry
        time.sleep(1.1)

        # Should now be expired
        assert cache.get("broll", "http://example.com/short_ttl.mp4") is None

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def test_evict_expired_removes_expired(self, sample_asset_cache):
        """evict_expired removes only expired entries, keeping valid ones."""
        cache = sample_asset_cache
        Path("/tmp/test_evict_valid.mp4").touch()
        Path("/tmp/test_evict_expired.mp4").touch()

        # Permanent entry (never expires)
        cache.set(
            "broll",
            "http://example.com/perm.mp4",
            "perm002",
            "/tmp/test_evict_valid.mp4",
            {},
            ttl_seconds=None,
        )

        # Expired entry
        cache.set(
            "broll",
            "http://example.com/exp.mp4",
            "exp002",
            "/tmp/test_evict_expired.mp4",
            {},
            ttl_seconds=0,
        )

        evicted = cache.evict_expired()
        assert evicted == 1

        # Permanent entry should still be accessible
        assert cache.get("broll", "http://example.com/perm.mp4") is not None
        # Expired entry should now be gone
        assert cache.get("broll", "http://example.com/exp.mp4") is None

    # ------------------------------------------------------------------
    # Orphan cleanup (Pitfall 2)
    # ------------------------------------------------------------------

    def test_orphan_cleanup_removes_missing_file(self, sample_asset_cache):
        """orphan_cleanup removes entries whose files no longer exist."""
        cache = sample_asset_cache
        file_path = "/tmp/test_orphan.missing"
        Path(file_path).touch()
        cache.set(
            "image",
            "http://example.com/orphan.jpg",
            "orphan01",
            file_path,
            {},
        )

        # Confirm it exists
        assert cache.get("image", "http://example.com/orphan.jpg") is not None

        # Delete the file
        Path(file_path).unlink()

        # Orphan cleanup should remove the entry
        removed = cache.orphan_cleanup()
        assert removed == 1

        # Entry should now return None
        assert cache.get("image", "http://example.com/orphan.jpg") is None

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def test_clear_removes_all(self, sample_asset_cache):
        """Clear removes all entries, returns count."""
        cache = sample_asset_cache
        Path("/tmp/test_clear_1.mp4").touch()
        Path("/tmp/test_clear_2.mp4").touch()

        cache.set(
            "broll",
            "http://example.com/clear1.mp4",
            "clear001",
            "/tmp/test_clear_1.mp4",
            {},
        )
        cache.set(
            "broll",
            "http://example.com/clear2.mp4",
            "clear002",
            "/tmp/test_clear_2.mp4",
            {},
        )

        deleted = cache.clear()
        assert deleted == 2

        assert cache.get("broll", "http://example.com/clear1.mp4") is None
        assert cache.get("broll", "http://example.com/clear2.mp4") is None

    # ------------------------------------------------------------------
    # Pitfall 2: Deleted file returns None
    # ------------------------------------------------------------------

    def test_get_returns_none_for_deleted_file(self, sample_asset_cache):
        """If cached file is deleted on disk, get() should return None (Pitfall 2)."""
        cache = sample_asset_cache
        file_path = "/tmp/test_pitfall2.mp4"
        Path(file_path).touch()

        cache.set(
            "broll",
            "http://example.com/pitfall2.mp4",
            "pitfall2",
            file_path,
            {},
        )

        # Should work initially
        assert cache.get("broll", "http://example.com/pitfall2.mp4") is not None

        # Delete the file behind cache's back
        Path(file_path).unlink()

        # After deletion, get should return None
        assert cache.get("broll", "http://example.com/pitfall2.mp4") is None

    # ------------------------------------------------------------------
    # Size tracking
    # ------------------------------------------------------------------

    def test_get_total_size_mb_returns_float(self, sample_asset_cache):
        """get_total_size_mb returns a float (0.0 for empty cache)."""
        cache = sample_asset_cache
        size = cache.get_total_size_mb()
        assert isinstance(size, float)
        assert size == 0.0

    def test_set_with_file_size(self, sample_asset_cache):
        """Setting an entry with file_size_bytes updates total size."""
        cache = sample_asset_cache
        Path("/tmp/test_size.mp4").touch()

        cache.set(
            "broll",
            "http://example.com/size.mp4",
            "size001",
            "/tmp/test_size.mp4",
            {},
            ttl_seconds=3600,
            file_size_bytes=5_000_000,  # ~5 MB
        )

        size_mb = cache.get_total_size_mb()
        assert size_mb > 0
        assert 4.0 < size_mb < 6.0  # Approximately 5 MB
