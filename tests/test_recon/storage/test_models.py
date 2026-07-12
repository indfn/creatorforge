"""
Tests for agent_core.recon.storage.models — Asset and Collection CRUD,
AssetCollection relationships, FTS search, and edge cases.

Database isolation via monkeypatched DATABASE_PATH + tmp_path per test.
"""

import json
from pathlib import Path

import pytest

from agent_core.recon.storage import database
from agent_core.recon.storage import models


# ---------------------------------------------------------------------------
# Fixture: isolated temp database
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path, monkeypatch):
    """Set up an isolated temp SQLite database for each test.

    Monkeypatches ``database.DATABASE_PATH`` to point to a ``test.db``
    inside the pytest-managed ``tmp_path`` so no real data is touched.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    database.init_db()
    return db_path


# ===================================================================
# Asset — create & read
# ===================================================================

class TestAssetCreate:
    """Verify :meth:`Asset.create` produces well-formed records."""

    def test_create_asset_with_required_fields(self, db):
        """Calling create with only type+title sets defaults (starred=False,
        timestamps populated, UUID generated)."""
        asset = models.Asset.create(type="report", title="Test Report")
        assert asset.id is not None
        assert len(asset.id) > 0
        assert asset.type == "report"
        assert asset.title == "Test Report"
        assert asset.starred is False
        assert asset.created_at is not None
        assert asset.updated_at is not None

    def test_create_asset_with_all_fields(self, db):
        """All optional fields are stored correctly."""
        meta = {"duration": 120, "resolution": "1080p"}
        asset = models.Asset.create(
            type="video",
            title="Test Video",
            content_path="/path/to/video.mp4",
            preview="Video preview text",
            metadata=meta,
        )
        assert asset.content_path == "/path/to/video.mp4"
        assert asset.preview == "Video preview text"
        assert asset.metadata == meta


class TestAssetGet:
    """Verify :meth:`Asset.get` retrieves records correctly."""

    def test_get_existing_asset(self, db):
        """Round-trip: create → get preserves all fields including JSON
        metadata and boolean starred."""
        meta = {"key": "val", "nested": {"a": 1}}
        created = models.Asset.create(
            type="report", title="Test", metadata=meta
        )
        fetched = models.Asset.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.type == "report"
        assert fetched.title == "Test"
        assert fetched.metadata == meta
        assert fetched.starred is False

    def test_get_nonexistent_asset(self, db):
        """Querying a non-existent ID returns None, never raises."""
        assert models.Asset.get("nonexistent-id") is None

    def test_asset_to_dict(self, db):
        """:meth:`Asset.to_dict` returns all expected keys with correct
        values."""
        asset = models.Asset.create(
            type="report", title="Test", metadata={"a": 1}
        )
        d = asset.to_dict()
        assert d["type"] == "report"
        assert d["title"] == "Test"
        assert d["metadata"] == {"a": 1}
        assert d["starred"] is False
        assert "id" in d
        assert "created_at" in d
        assert "updated_at" in d
        assert "content_path" in d
        assert "preview" in d


# ===================================================================
# Asset — update
# ===================================================================

class TestAssetUpdate:
    """Verify :meth:`Asset.update` mutates fields and persists to DB."""

    def test_update_title(self, db):
        """Updating the title changes the Python object and the DB row."""
        asset = models.Asset.create(type="report", title="Old Title")
        asset.update(title="New Title")
        assert asset.title == "New Title"

        reloaded = models.Asset.get(asset.id)
        assert reloaded.title == "New Title"

    def test_update_starred(self, db):
        """Setting starred flips the boolean (INTEGER 0/1 in DB)."""
        asset = models.Asset.create(type="report", title="Test")
        assert asset.starred is False

        asset.update(starred=True)
        assert asset.starred is True

        reloaded = models.Asset.get(asset.id)
        assert reloaded.starred is True

    def test_update_metadata(self, db):
        """Metadata JSON is serialised on write and deserialised on read."""
        asset = models.Asset.create(type="report", title="Test")
        new_meta = {"key": "value", "count": 42}
        asset.update(metadata=new_meta)
        assert asset.metadata == new_meta

        reloaded = models.Asset.get(asset.id)
        assert reloaded.metadata == new_meta

    def test_update_unknown_field_ignored(self, db):
        """Passing a key not in the allowed set silently no-ops."""
        asset = models.Asset.create(type="report", title="Test")
        original_updated_at = asset.updated_at

        asset.update(nonexistent_field="val", another_bad="x")
        # Object unchanged
        assert asset.title == "Test"
        # DB also unchanged
        reloaded = models.Asset.get(asset.id)
        assert reloaded.title == "Test"

    def test_update_no_changes_returns_same_asset(self, db):
        """Calling update() with empty kwargs returns self unchanged."""
        asset = models.Asset.create(type="report", title="Test")
        original_updated = asset.updated_at

        result = asset.update()
        assert result is asset
        assert asset.updated_at == original_updated

    def test_update_persists_to_database(self, db):
        """Composite change: after multiple updates all values are reflected
        in a fresh get()."""
        asset = models.Asset.create(type="report", title="A")
        asset.update(title="B", starred=True, metadata={"x": 1})
        asset.update(title="C")

        reloaded = models.Asset.get(asset.id)
        assert reloaded.title == "C"
        assert reloaded.starred is True
        assert reloaded.metadata == {"x": 1}


# ===================================================================
# Asset — delete
# ===================================================================

class TestAssetDelete:
    """Verify :meth:`Asset.delete` removes the row from the database."""

    def test_delete_asset(self, db):
        """After deletion, get() returns None."""
        asset = models.Asset.create(type="report", title="To Delete")
        asset_id = asset.id
        asset.delete()
        assert models.Asset.get(asset_id) is None

    def test_delete_nonexistent_asset(self, db):
        """Calling delete() on an already-deleted asset doesn't raise."""
        asset = models.Asset.create(type="report", title="Ghost")
        asset_id = asset.id
        asset.delete()
        # Second delete on same instance (id still in memory) is a no-op SQL
        asset.delete()  # should not raise

    def test_delete_updates_database(self, db):
        """After delete, a direct SQL query confirms the row is gone."""
        asset = models.Asset.create(type="report", title="Gone")
        asset_id = asset.id
        asset.delete()

        conn = database.get_db_connection()
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        conn.close()
        assert row["cnt"] == 0


# ===================================================================
# Asset — list
# ===================================================================

class TestAssetList:
    """Verify :meth:`Asset.list` filtering and pagination."""

    @pytest.fixture
    def three_assets(self, db):
        """Seed three assets of mixed types and star status.

        ``Asset.create()`` doesn't accept ``starred`` directly, so we
        use ``update()`` after creation for starred assets.
        """
        a1 = models.Asset.create(type="report", title="Report A")
        a1.update(starred=True)
        a2 = models.Asset.create(type="report", title="Report B")
        a3 = models.Asset.create(type="video", title="Video A")
        a3.update(starred=True)
        return a1, a2, a3

    def test_list_all_assets(self, three_assets):
        """list() returns all assets ordered by created_at DESC (most
        recent first)."""
        assets = models.Asset.list()
        assert len(assets) == 3
        # Created most-recent first
        assert assets[0].title == "Video A"

    def test_list_filter_by_type(self, three_assets):
        """list(type='report') returns only report-type assets."""
        assets = models.Asset.list(type="report")
        assert len(assets) == 2
        assert all(a.type == "report" for a in assets)

    def test_list_filter_by_starred(self, three_assets):
        """list(starred=True) returns only starred assets."""
        assets = models.Asset.list(starred=True)
        assert len(assets) == 2
        assert all(a.starred for a in assets)

    def test_list_with_limit_and_offset(self, three_assets):
        """list(limit=2, offset=1) returns a correct subset (skip first,
        take next two — but there are only 3 assets, so we'd get the last
        one + nothing)."""
        # There are 3 assets; offset=1 skips the most recent → 2 remain
        assets = models.Asset.list(limit=2, offset=1)
        assert len(assets) == 2

    def test_list_with_collection_filter(self, db):
        """list(collection_id=…) returns only assets in that collection."""
        a1 = models.Asset.create(type="report", title="A")
        a2 = models.Asset.create(type="report", title="B")
        col = models.Collection.create(name="My Collection")

        models.AssetCollection.add(a1.id, col.id)

        assets = models.Asset.list(collection_id=col.id)
        assert len(assets) == 1
        assert assets[0].id == a1.id

    def test_list_empty_returns_empty_list(self, db):
        """list() on an empty database returns []."""
        assert models.Asset.list() == []

    def test_list_filter_nonexistent_type(self, db):
        """list(type='nonexistent') returns []."""
        models.Asset.create(type="report", title="R")
        assert models.Asset.list(type="pdf") == []


# ===================================================================
# Asset — FTS search
# ===================================================================

class TestAssetSearch:
    """Verify :meth:`Asset.search` via FTS5 virtual table."""

    def test_search_finds_matching_title(self, db):
        """FTS matches against the title field."""
        models.Asset.create(type="report", title="Annual Report 2026")
        models.Asset.create(type="video", title="Random Clip")

        results = models.Asset.search("Annual")
        assert len(results) >= 1
        assert any("Annual" in r.title for r in results)

    def test_search_returns_empty_for_no_match(self, db):
        """No matches → empty list."""
        models.Asset.create(type="report", title="Alpha")
        results = models.Asset.search("xyznonexistent")
        assert results == []

    def test_search_finds_matching_preview(self, db):
        """FTS also indexes the preview column."""
        models.Asset.create(
            type="report",
            title="Something",
            preview="The quarterly benchmark results are here",
        )
        results = models.Asset.search("benchmark")
        assert len(results) >= 1

    def test_search_respects_limit(self, db):
        """search(limit=1) returns at most one row."""
        for i in range(3):
            models.Asset.create(type="report", title=f"Report {i}")
        results = models.Asset.search("Report", limit=1)
        assert len(results) == 1

    def test_search_multiple_terms(self, db):
        """Search can match on multiple space-separated terms (FTS5
        implicit AND)."""
        models.Asset.create(type="report", title="Annual Report Data")
        models.Asset.create(type="report", title="Report Summary")
        # "Annual" should narrow
        results = models.Asset.search("Annual Report")
        assert len(results) >= 1
        assert all("Annual" in r.title for r in results)


# ===================================================================
# Collection — create & list
# ===================================================================

class TestCollectionCreate:
    """Verify :meth:`Collection.create` behaviour."""

    def test_create_collection_with_required(self, db):
        """Creating with just a name succeeds."""
        col = models.Collection.create(name="Work")
        assert col.id is not None
        assert col.name == "Work"

    def test_create_collection_with_all_fields(self, db):
        """Custom colour and icon are persisted."""
        col = models.Collection.create(
            name="Design",
            description="Design inspiration",
            color="#ff5733",
            icon="palette",
        )
        assert col.description == "Design inspiration"
        assert col.color == "#ff5733"
        assert col.icon == "palette"

    def test_create_collection_default_color(self, db):
        """The default colour is the indigo brand colour (#6366f1)."""
        col = models.Collection.create(name="Default")
        assert col.color == "#6366f1"

    def test_created_at_is_set(self, db):
        """Timestamp is populated on creation."""
        col = models.Collection.create(name="Timed")
        assert col.created_at is not None


class TestCollectionList:
    """Verify :meth:`Collection.list`."""

    def test_list_all_collections(self, db):
        """list() returns all collections ordered by name."""
        models.Collection.create(name="Zoo")
        models.Collection.create(name="Alpha")
        cols = models.Collection.list()
        assert len(cols) == 2
        assert cols[0].name == "Alpha"  # alphabetical ASC

    def test_list_empty(self, db):
        """No collections → []."""
        assert models.Collection.list() == []

    def test_collection_to_dict(self, db):
        """:meth:`Collection.to_dict` returns expected keys."""
        col = models.Collection.create(
            name="Test", description="Desc", color="#112233", icon="star"
        )
        d = col.to_dict()
        assert d["name"] == "Test"
        assert d["description"] == "Desc"
        assert d["color"] == "#112233"
        assert d["icon"] == "star"
        assert "id" in d
        assert "created_at" in d


# ===================================================================
# AssetCollection — relationship
# ===================================================================

class TestAssetCollection:
    """Verify the many-to-many junction between Asset and Collection."""

    def test_add_asset_to_collection(self, db):
        """Adding an asset to a collection creates a junction record;
        ``list(collection_id=…)`` returns it."""
        asset = models.Asset.create(type="report", title="Test")
        col = models.Collection.create(name="My Collection")

        models.AssetCollection.add(asset.id, col.id)

        assets = models.Asset.list(collection_id=col.id)
        assert len(assets) == 1
        assert assets[0].id == asset.id

    def test_remove_asset_from_collection(self, db):
        """Removing deletes the junction record."""
        asset = models.Asset.create(type="report", title="Test")
        col = models.Collection.create(name="My Collection")

        models.AssetCollection.add(asset.id, col.id)
        models.AssetCollection.remove(asset.id, col.id)

        assets = models.Asset.list(collection_id=col.id)
        assert assets == []

    def test_asset_list_filtered_by_collection(self, db):
        """Only assets explicitly added to the collection appear in the
        filtered list."""
        a1 = models.Asset.create(type="report", title="In Collection")
        a2 = models.Asset.create(type="report", title="Not in Collection")
        col = models.Collection.create(name="Col")

        models.AssetCollection.add(a1.id, col.id)

        assets = models.Asset.list(collection_id=col.id)
        assert len(assets) == 1
        assert assets[0].id == a1.id

    def test_add_duplicate_is_idempotent(self, db):
        """Calling add() twice for the same pair doesn't raise (INSERT OR
        IGNORE)."""
        asset = models.Asset.create(type="report", title="Test")
        col = models.Collection.create(name="Col")

        models.AssetCollection.add(asset.id, col.id)
        models.AssetCollection.add(asset.id, col.id)  # should not raise

        assets = models.Asset.list(collection_id=col.id)
        assert len(assets) == 1

    def test_cascade_delete_removes_junction(self, db):
        """Deleting an asset automatically cascades to remove its
        asset_collections rows (ON DELETE CASCADE)."""
        asset = models.Asset.create(type="report", title="Cascade Test")
        col = models.Collection.create(name="Col")

        models.AssetCollection.add(asset.id, col.id)

        # Confirm junction exists
        assets_before = models.Asset.list(collection_id=col.id)
        assert len(assets_before) == 1

        asset.delete()

        # Cascade should have removed the junction
        assets_after = models.Asset.list(collection_id=col.id)
        assert assets_after == []

    def test_cascade_delete_removes_junction_direct_query(self, db):
        """Verify cascade at the SQL level: after asset deletion, a direct
        query on asset_collections returns 0 rows for that asset, and
        the collection still exists."""
        asset = models.Asset.create(type="report", title="Cascade Direct")
        col = models.Collection.create(name="Col")

        models.AssetCollection.add(asset.id, col.id)

        asset.delete()

        # Direct SQL on junction table
        conn = database.get_db_connection()
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM asset_collections WHERE asset_id = ?",
            (asset.id,),
        ).fetchone()
        conn.close()
        assert row["cnt"] == 0

        # Collection itself is not deleted by the cascade
        reloaded_list = models.Collection.list()
        assert any(c.id == col.id for c in reloaded_list)


# ===================================================================
# Edge cases & error handling
# ===================================================================

class TestAssetEdgeCases:
    """Corner cases and defensive behaviour."""

    def test_create_asset_without_type_raises(self, db):
        """:meth:`Asset.create` requires ``type`` as a positional
        argument — omitting it raises :class:`TypeError`."""
        with pytest.raises(TypeError):
            # type is a required positional arg in the method signature
            models.Asset.create(title="No Type")  # type: ignore[call-arg]

    def test_update_only_allowed_fields(self, db):
        """Calling update(id=…) or update(created_at=…) silently no-ops
        because those keys are not in the ``allowed`` set."""
        asset = models.Asset.create(type="report", title="Original")
        original_id = asset.id
        original_created = asset.created_at

        asset.update(id="new-id", created_at="2020-01-01")
        assert asset.id == original_id
        assert asset.created_at == original_created

    def test_delete_then_create_same_attributes(self, db):
        """After deletion, a new asset with the same attribute values can
        be created (no uniqueness constraints on non-PK fields)."""
        asset = models.Asset.create(
            type="report",
            title="Same Data",
            content_path="/path",
            preview="prev",
        )
        asset.delete()

        # Re-create with same attributes (will get a new UUID)
        asset2 = models.Asset.create(
            type="report",
            title="Same Data",
            content_path="/path",
            preview="prev",
        )
        assert asset2 is not None
        assert asset2.title == "Same Data"
        assert asset2.id != asset.id

    def test_metadata_none_is_stored_as_null(self, db):
        """Passing metadata=None stores NULL in the DB, which round-trips
        back to None in Python."""
        asset = models.Asset.create(
            type="report", title="Null Meta", metadata=None
        )
        assert asset.metadata is None

        reloaded = models.Asset.get(asset.id)
        assert reloaded.metadata is None

    def test_starred_false_default(self, db):
        """A freshly created asset has starred=False (INTEGER 0 in DB,
        boolean False in Python)."""
        asset = models.Asset.create(type="report", title="Default Star")
        assert asset.starred is False

    def test_update_empty_metadata_to_none(self, db):
        """Updating metadata to None stores NULL and returns None on
        read."""
        asset = models.Asset.create(
            type="report", title="Meta Nulling", metadata={"x": 1}
        )
        asset.update(metadata=None)
        assert asset.metadata is None

        reloaded = models.Asset.get(asset.id)
        assert reloaded.metadata is None

    def test_update_starred_then_unstar(self, db):
        """starred can be toggled back from True to False."""
        asset = models.Asset.create(type="report", title="Toggle")
        asset.update(starred=True)
        assert asset.starred is True

        asset.update(starred=False)
        assert asset.starred is False

        reloaded = models.Asset.get(asset.id)
        assert reloaded.starred is False
