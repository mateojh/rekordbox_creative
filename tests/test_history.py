"""Unit tests for set history persistence."""

import sqlite3

import pytest

from uuid import UUID, uuid4

from rekordbox_creative.db.history import HistoryStore


@pytest.fixture
def conn():
    """In-memory SQLite with required tables."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=OFF")  # Simplify testing (no tracks table needed)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY,
            file_path TEXT,
            file_hash TEXT,
            filename TEXT,
            duration_seconds REAL,
            sample_rate INTEGER DEFAULT 22050,
            energy REAL, danceability REAL, acousticness REAL,
            instrumentalness REAL, valence REAL, liveness REAL,
            bpm REAL, bpm_stability REAL,
            key_camelot TEXT, key_confidence REAL,
            mix_in_score REAL, mix_out_score REAL,
            frequency_weight TEXT, groove_type TEXT,
            structure_json TEXT, metadata_json TEXT,
            cluster_id INTEGER, times_used INTEGER DEFAULT 0,
            analyzed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS set_history (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            duration_minutes REAL,
            track_count INTEGER,
            avg_compatibility REAL,
            energy_profile TEXT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS set_history_tracks (
            history_id TEXT NOT NULL REFERENCES set_history(id),
            position INTEGER NOT NULL,
            track_id TEXT NOT NULL,
            transition_score REAL,
            PRIMARY KEY(history_id, position)
        );
    """)
    # Insert a few dummy tracks for key distribution test
    for key in ["8A", "8A", "9A", "7A", "8B"]:
        tid = str(uuid4())
        c.execute(
            "INSERT INTO tracks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, f"/music/{tid}.mp3", "hash", "f.mp3", 300.0, 22050,
             0.8, 0.7, 0.1, 0.6, 0.5, 0.1,
             128.0, 0.95, key, 0.9,
             0.8, 0.8, "balanced", "four_on_floor",
             "{}", "{}",
             None, 0, "2025-01-01T00:00:00"),
        )
    c.commit()
    yield c
    c.close()


@pytest.fixture
def store(conn):
    return HistoryStore(conn)


@pytest.fixture
def track_ids(conn):
    """Return the IDs of the dummy tracks."""
    rows = conn.execute("SELECT id FROM tracks").fetchall()
    return [UUID(r[0]) for r in rows]


class TestHistoryCRUD:
    def test_save_and_get_all(self, store, track_ids):
        hid = store.save_set(
            "Friday Night",
            track_ids[:3],
            [None, 0.85, 0.72],
            duration_minutes=15.0,
            avg_compatibility=0.78,
        )
        sets = store.get_all_sets()
        assert len(sets) == 1
        assert sets[0]["name"] == "Friday Night"
        assert sets[0]["track_count"] == 3
        assert sets[0]["avg_compatibility"] == 0.78

    def test_get_track_ids(self, store, track_ids):
        hid = store.save_set("Test", track_ids[:2], [None, 0.9])
        result = store.get_set_track_ids(hid)
        assert len(result) == 2
        assert result[0] == track_ids[0]
        assert result[1] == track_ids[1]

    def test_get_transitions(self, store, track_ids):
        hid = store.save_set("Test", track_ids[:3], [None, 0.85, 0.72])
        scores = store.get_set_transitions(hid)
        assert scores[0] is None
        assert abs(scores[1] - 0.85) < 1e-6
        assert abs(scores[2] - 0.72) < 1e-6

    def test_delete_set(self, store, track_ids):
        hid = store.save_set("ToDelete", track_ids[:2], [None, 0.9])
        assert len(store.get_all_sets()) == 1
        store.delete_set(hid)
        assert len(store.get_all_sets()) == 0

    def test_update_notes(self, store, track_ids):
        hid = store.save_set("Test", track_ids[:1], [None])
        store.update_notes(hid, "Great set!")
        sets = store.get_all_sets()
        assert sets[0]["notes"] == "Great set!"

    def test_multiple_sets_ordered_newest_first(self, store, track_ids):
        store.save_set("First", track_ids[:1], [None])
        store.save_set("Second", track_ids[:2], [None, 0.8])
        sets = store.get_all_sets()
        assert len(sets) == 2
        # Second was saved later, should be first
        assert sets[0]["name"] == "Second"

    def test_empty_history(self, store):
        assert store.get_all_sets() == []

    def test_save_with_energy_profile(self, store, track_ids):
        hid = store.save_set(
            "Generated Set",
            track_ids[:3],
            [None, 0.9, 0.85],
            energy_profile="warm_up_peak_cool",
        )
        sets = store.get_all_sets()
        assert sets[0]["energy_profile"] == "warm_up_peak_cool"


class TestAnalytics:
    def test_most_used_tracks(self, store, track_ids):
        store.save_set("Set1", track_ids[:3], [None, 0.8, 0.7])
        store.save_set("Set2", track_ids[:2], [None, 0.9])
        most = store.get_most_used_tracks(5)
        # track_ids[0] and [1] appear in both sets
        assert len(most) >= 2
        assert most[0]["count"] >= 2

    def test_key_distribution(self, store, track_ids):
        store.save_set("Set1", track_ids[:5], [None, 0.8, 0.7, 0.6, 0.5])
        dist = store.get_key_distribution()
        assert isinstance(dist, dict)
        assert sum(dist.values()) == 5

    def test_avg_compatibility_over_time(self, store, track_ids):
        store.save_set("S1", track_ids[:1], [None], avg_compatibility=0.75)
        store.save_set("S2", track_ids[:1], [None], avg_compatibility=0.85)
        trend = store.get_avg_compatibility_over_time()
        assert len(trend) == 2
        assert trend[0][1] == 0.75
        assert trend[1][1] == 0.85

    def test_most_used_empty(self, store):
        assert store.get_most_used_tracks() == []
