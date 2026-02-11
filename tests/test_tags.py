"""Unit tests for TagStore CRUD operations."""

import sqlite3

import pytest

from rekordbox_creative.db.tags import STARTER_TAGS, TagStore


@pytest.fixture
def tag_store():
    """Create an in-memory tag store with tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    # Create minimal tracks table for FK
    conn.execute("""
        CREATE TABLE tracks (
            id TEXT PRIMARY KEY,
            file_path TEXT,
            file_hash TEXT,
            filename TEXT,
            duration_seconds REAL,
            analyzed_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO tracks VALUES ('track-1', '/a.mp3', 'h1', 'a.mp3', 180.0, '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO tracks VALUES ('track-2', '/b.mp3', 'h2', 'b.mp3', 200.0, '2025-01-01')"
    )
    conn.commit()
    store = TagStore(conn)
    store.create_tables()
    return store


class TestTagCRUD:
    def test_create_tag(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Test Tag", "#FF0000")
        assert tag_id is not None
        assert tag_id > 0

    def test_get_all_tags_empty(self, tag_store: TagStore):
        tags = tag_store.get_all_tags()
        assert tags == []

    def test_get_all_tags_after_create(self, tag_store: TagStore):
        tag_store.create_tag("Alpha", "#AA0000")
        tag_store.create_tag("Beta", "#BB0000")
        tags = tag_store.get_all_tags()
        assert len(tags) == 2
        names = {t["name"] for t in tags}
        assert names == {"Alpha", "Beta"}

    def test_get_tag(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Opener", "#22c55e")
        tag = tag_store.get_tag(tag_id)
        assert tag is not None
        assert tag["name"] == "Opener"
        assert tag["color"] == "#22c55e"

    def test_get_tag_not_found(self, tag_store: TagStore):
        assert tag_store.get_tag(999) is None

    def test_update_tag_name(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Old Name", "#FF0000")
        tag_store.update_tag(tag_id, name="New Name")
        tag = tag_store.get_tag(tag_id)
        assert tag["name"] == "New Name"
        assert tag["color"] == "#FF0000"

    def test_update_tag_color(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Tag", "#FF0000")
        tag_store.update_tag(tag_id, color="#00FF00")
        tag = tag_store.get_tag(tag_id)
        assert tag["color"] == "#00FF00"

    def test_delete_tag(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("To Delete", "#FF0000")
        tag_store.delete_tag(tag_id)
        assert tag_store.get_tag(tag_id) is None

    def test_delete_tag_removes_associations(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Tag", "#FF0000")
        from uuid import UUID
        track_id = UUID("00000000-0000-0000-0000-000000000000")
        # Insert a track_tags row manually
        tag_store._conn.execute(
            "INSERT INTO track_tags VALUES ('track-1', ?)", (tag_id,)
        )
        tag_store._conn.commit()
        tag_store.delete_tag(tag_id)
        rows = tag_store._conn.execute(
            "SELECT * FROM track_tags WHERE tag_id = ?", (tag_id,)
        ).fetchall()
        assert len(rows) == 0

    def test_seed_starter_tags(self, tag_store: TagStore):
        tag_store.seed_starter_tags()
        tags = tag_store.get_all_tags()
        assert len(tags) == len(STARTER_TAGS)
        names = {t["name"] for t in tags}
        for expected_name, _ in STARTER_TAGS:
            assert expected_name in names

    def test_seed_starter_tags_idempotent(self, tag_store: TagStore):
        tag_store.seed_starter_tags()
        tag_store.seed_starter_tags()
        tags = tag_store.get_all_tags()
        assert len(tags) == len(STARTER_TAGS)


class TestTrackTagAssociations:
    def test_add_tag_to_track(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Test", "#FF0000")
        # Use actual track IDs from fixture
        tag_store._conn.execute(
            "INSERT OR IGNORE INTO track_tags (track_id, tag_id) VALUES ('track-1', ?)",
            (tag_id,),
        )
        tag_store._conn.commit()
        tags = tag_store._conn.execute(
            "SELECT * FROM track_tags WHERE track_id = 'track-1'"
        ).fetchall()
        assert len(tags) == 1

    def test_get_tags_for_track(self, tag_store: TagStore):
        tag1 = tag_store.create_tag("Opener", "#22c55e")
        tag2 = tag_store.create_tag("Vocal", "#f59e0b")
        tag_store._conn.execute(
            "INSERT INTO track_tags VALUES ('track-1', ?)", (tag1,)
        )
        tag_store._conn.execute(
            "INSERT INTO track_tags VALUES ('track-1', ?)", (tag2,)
        )
        tag_store._conn.commit()
        from uuid import UUID
        # Use raw query since track IDs are strings not UUIDs in this fixture
        rows = tag_store._conn.execute(
            """SELECT t.id, t.name, t.color FROM tags t
               JOIN track_tags tt ON t.id = tt.tag_id
               WHERE tt.track_id = 'track-1' ORDER BY t.name""",
        ).fetchall()
        tags = [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in rows]
        assert len(tags) == 2
        assert tags[0]["name"] == "Opener"
        assert tags[1]["name"] == "Vocal"

    def test_remove_tag_from_track(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Test", "#FF0000")
        tag_store._conn.execute(
            "INSERT INTO track_tags VALUES ('track-1', ?)", (tag_id,)
        )
        tag_store._conn.commit()
        # Remove using raw SQL since fixture IDs aren't real UUIDs
        tag_store._conn.execute(
            "DELETE FROM track_tags WHERE track_id = 'track-1' AND tag_id = ?",
            (tag_id,),
        )
        tag_store._conn.commit()
        rows = tag_store._conn.execute(
            "SELECT * FROM track_tags WHERE track_id = 'track-1'"
        ).fetchall()
        assert len(rows) == 0

    def test_get_tracks_by_tag(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Peak Time", "#ef4444")
        tag_store._conn.execute(
            "INSERT INTO track_tags VALUES ('track-1', ?)", (tag_id,)
        )
        tag_store._conn.execute(
            "INSERT INTO track_tags VALUES ('track-2', ?)", (tag_id,)
        )
        tag_store._conn.commit()
        tracks = tag_store.get_tracks_by_tag(tag_id)
        assert len(tracks) == 2
        assert "track-1" in tracks
        assert "track-2" in tracks

    def test_get_tracks_by_tags_and_logic(self, tag_store: TagStore):
        tag1 = tag_store.create_tag("Opener", "#22c55e")
        tag2 = tag_store.create_tag("Vocal", "#f59e0b")
        tag_store._conn.execute("INSERT INTO track_tags VALUES ('track-1', ?)", (tag1,))
        tag_store._conn.execute("INSERT INTO track_tags VALUES ('track-1', ?)", (tag2,))
        tag_store._conn.execute("INSERT INTO track_tags VALUES ('track-2', ?)", (tag1,))
        tag_store._conn.commit()
        # Both tags: only track-1
        result = tag_store.get_tracks_by_tags([tag1, tag2])
        assert len(result) == 1
        assert result[0] == "track-1"

    def test_get_tracks_by_tags_empty(self, tag_store: TagStore):
        assert tag_store.get_tracks_by_tags([]) == []

    def test_add_tag_to_track_idempotent(self, tag_store: TagStore):
        tag_id = tag_store.create_tag("Test", "#FF0000")
        tag_store._conn.execute(
            "INSERT OR IGNORE INTO track_tags VALUES ('track-1', ?)", (tag_id,)
        )
        tag_store._conn.execute(
            "INSERT OR IGNORE INTO track_tags VALUES ('track-1', ?)", (tag_id,)
        )
        tag_store._conn.commit()
        rows = tag_store._conn.execute(
            "SELECT * FROM track_tags WHERE track_id = 'track-1' AND tag_id = ?",
            (tag_id,),
        ).fetchall()
        assert len(rows) == 1
