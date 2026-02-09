"""Tests for SQLite database operations."""

import sqlite3
from uuid import uuid4

import pytest

from rekordbox_creative.db.cache import CacheManager
from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import (
    DJMetrics,
    Edge,
    EdgeScores,
    Playlist,
    SpotifyStyleMetrics,
    Track,
    TrackMetadata,
    TrackStructure,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    """In-memory database for most tests."""
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def db_file(tmp_path):
    """File-based database for persistence tests."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    yield database, db_path
    database.close()


def _make_track(
    file_path: str = "/music/test.mp3",
    file_hash: str = "hash123",
    filename: str = "test.mp3",
    bpm: float = 128.0,
    key: str = "8A",
    energy: float = 0.8,
) -> Track:
    """Helper to create a Track with sensible defaults."""
    return Track(
        file_path=file_path,
        file_hash=file_hash,
        filename=filename,
        duration_seconds=300.0,
        spotify_style=SpotifyStyleMetrics(
            energy=energy, danceability=0.7, acousticness=0.05,
            instrumentalness=0.6, valence=0.5, liveness=0.1,
        ),
        dj_metrics=DJMetrics(
            bpm=bpm, bpm_stability=0.95, key=key,
            key_confidence=0.9, mix_in_score=0.85, mix_out_score=0.80,
            frequency_weight="balanced", groove_type="four_on_floor",
        ),
        structure=TrackStructure(drops=[60.0, 180.0]),
        metadata=TrackMetadata(artist="Test Artist", title="Test Track"),
    )


def _make_edge(source_id, target_id, score=0.8):
    """Helper to create an Edge."""
    return Edge(
        source_id=source_id,
        target_id=target_id,
        compatibility_score=score,
        scores=EdgeScores(
            harmonic=0.85, bpm=0.9, energy=0.7,
            groove=1.0, frequency=0.7, mix_quality=0.8,
        ),
    )


# ---------------------------------------------------------------------------
# Database creation
# ---------------------------------------------------------------------------


class TestDatabaseCreation:
    def test_creates_tables(self, db):
        """All expected tables exist after initialization."""
        cursor = db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert "tracks" in tables
        assert "edges" in tables
        assert "playlists" in tables
        assert "playlist_tracks" in tables
        assert "preferences" in tables

    def test_creates_indexes(self, db):
        """Expected indexes exist."""
        cursor = db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = {row["name"] for row in cursor.fetchall()}
        assert "idx_tracks_bpm" in indexes
        assert "idx_tracks_key" in indexes
        assert "idx_tracks_energy" in indexes
        assert "idx_tracks_file_hash" in indexes
        assert "idx_tracks_cluster" in indexes
        assert "idx_edges_source" in indexes
        assert "idx_edges_target" in indexes
        assert "idx_edges_score" in indexes

    def test_in_memory_database(self, db):
        """In-memory database works."""
        assert db.connection is not None

    def test_file_based_database(self, db_file):
        """File-based database creates the file on disk."""
        database, db_path = db_file
        assert db_path.exists()

    def test_create_tables_idempotent(self, db):
        """Calling create_tables twice doesn't error."""
        db.create_tables()
        db.create_tables()


# ---------------------------------------------------------------------------
# Track CRUD
# ---------------------------------------------------------------------------


class TestTrackCRUD:
    def test_insert_and_get_track(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        retrieved = db.get_track(mock_track_a.id)

        assert retrieved is not None
        assert retrieved.id == mock_track_a.id
        assert retrieved.file_path == mock_track_a.file_path
        assert retrieved.file_hash == mock_track_a.file_hash
        assert retrieved.filename == mock_track_a.filename
        assert retrieved.duration_seconds == mock_track_a.duration_seconds
        assert retrieved.sample_rate == mock_track_a.sample_rate

    def test_insert_and_get_track_spotify_style(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        retrieved = db.get_track(mock_track_a.id)

        assert retrieved.spotify_style.energy == mock_track_a.spotify_style.energy
        assert (
            retrieved.spotify_style.danceability
            == mock_track_a.spotify_style.danceability
        )
        assert (
            retrieved.spotify_style.acousticness
            == mock_track_a.spotify_style.acousticness
        )
        assert (
            retrieved.spotify_style.instrumentalness
            == mock_track_a.spotify_style.instrumentalness
        )
        assert retrieved.spotify_style.valence == mock_track_a.spotify_style.valence
        assert retrieved.spotify_style.liveness == mock_track_a.spotify_style.liveness

    def test_insert_and_get_track_dj_metrics(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        retrieved = db.get_track(mock_track_a.id)

        assert retrieved.dj_metrics.bpm == mock_track_a.dj_metrics.bpm
        assert (
            retrieved.dj_metrics.bpm_stability
            == mock_track_a.dj_metrics.bpm_stability
        )
        assert retrieved.dj_metrics.key == mock_track_a.dj_metrics.key
        assert (
            retrieved.dj_metrics.key_confidence
            == mock_track_a.dj_metrics.key_confidence
        )
        assert (
            retrieved.dj_metrics.mix_in_score
            == mock_track_a.dj_metrics.mix_in_score
        )
        assert (
            retrieved.dj_metrics.mix_out_score
            == mock_track_a.dj_metrics.mix_out_score
        )
        assert (
            retrieved.dj_metrics.frequency_weight
            == mock_track_a.dj_metrics.frequency_weight
        )
        assert retrieved.dj_metrics.groove_type == mock_track_a.dj_metrics.groove_type

    def test_insert_and_get_track_structure(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        retrieved = db.get_track(mock_track_a.id)

        assert retrieved.structure.drops == mock_track_a.structure.drops
        assert retrieved.structure.breakdowns == mock_track_a.structure.breakdowns
        assert (
            retrieved.structure.vocal_segments
            == mock_track_a.structure.vocal_segments
        )

    def test_insert_and_get_track_metadata(self, db):
        track = _make_track()
        db.insert_track(track)
        retrieved = db.get_track(track.id)

        assert retrieved.metadata.artist == "Test Artist"
        assert retrieved.metadata.title == "Test Track"

    def test_insert_and_get_track_graph_state(self, db):
        track = _make_track()
        track.cluster_id = 3
        track.times_used = 5
        db.insert_track(track)
        retrieved = db.get_track(track.id)

        assert retrieved.cluster_id == 3
        assert retrieved.times_used == 5

    def test_get_track_nonexistent(self, db):
        assert db.get_track(uuid4()) is None

    def test_get_track_by_hash(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        retrieved = db.get_track_by_hash("abc123")

        assert retrieved is not None
        assert retrieved.id == mock_track_a.id

    def test_get_track_by_hash_nonexistent(self, db):
        assert db.get_track_by_hash("nonexistent") is None

    def test_get_track_by_path(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        retrieved = db.get_track_by_path("/music/track_a.mp3")

        assert retrieved is not None
        assert retrieved.id == mock_track_a.id

    def test_get_all_tracks_empty(self, db):
        assert db.get_all_tracks() == []

    def test_get_all_tracks(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        tracks = db.get_all_tracks()

        assert len(tracks) == 2
        ids = {t.id for t in tracks}
        assert mock_track_a.id in ids
        assert mock_track_b.id in ids

    def test_update_track(self, db, mock_track_a):
        db.insert_track(mock_track_a)

        # Modify the track
        mock_track_a.cluster_id = 7
        mock_track_a.times_used = 42
        db.update_track(mock_track_a)

        retrieved = db.get_track(mock_track_a.id)
        assert retrieved.cluster_id == 7
        assert retrieved.times_used == 42

    def test_delete_track(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        db.delete_track(mock_track_a.id)

        assert db.get_track(mock_track_a.id) is None

    def test_delete_nonexistent_track_no_error(self, db):
        """Deleting a nonexistent track should not raise."""
        db.delete_track(uuid4())

    def test_duplicate_file_path_raises(self, db):
        t1 = _make_track(file_path="/music/same.mp3", file_hash="h1")
        t2 = _make_track(file_path="/music/same.mp3", file_hash="h2")
        db.insert_track(t1)
        with pytest.raises(sqlite3.IntegrityError):
            db.insert_track(t2)

    def test_different_file_paths_ok(self, db):
        t1 = _make_track(file_path="/music/a.mp3", file_hash="h1")
        t2 = _make_track(file_path="/music/b.mp3", file_hash="h2")
        db.insert_track(t1)
        db.insert_track(t2)
        assert len(db.get_all_tracks()) == 2


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------


class TestEdgeCRUD:
    def test_insert_and_get_edge(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        edge = _make_edge(mock_track_a.id, mock_track_b.id, 0.85)
        db.insert_edge(edge)

        retrieved = db.get_edge(mock_track_a.id, mock_track_b.id)
        assert retrieved is not None
        assert retrieved.id == edge.id
        assert retrieved.compatibility_score == 0.85
        assert retrieved.scores.harmonic == 0.85
        assert retrieved.scores.bpm == 0.9
        assert retrieved.is_user_created is False

    def test_get_edge_nonexistent(self, db, mock_track_a, mock_track_b):
        assert db.get_edge(mock_track_a.id, mock_track_b.id) is None

    def test_get_edges_for_track_as_source(
        self, db, mock_track_a, mock_track_b
    ):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        edge = _make_edge(mock_track_a.id, mock_track_b.id)
        db.insert_edge(edge)

        edges = db.get_edges_for_track(mock_track_a.id)
        assert len(edges) == 1
        assert edges[0].source_id == mock_track_a.id

    def test_get_edges_for_track_as_target(
        self, db, mock_track_a, mock_track_b
    ):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        edge = _make_edge(mock_track_a.id, mock_track_b.id)
        db.insert_edge(edge)

        edges = db.get_edges_for_track(mock_track_b.id)
        assert len(edges) == 1
        assert edges[0].target_id == mock_track_b.id

    def test_get_all_edges_empty(self, db):
        assert db.get_all_edges() == []

    def test_get_all_edges(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        e1 = _make_edge(mock_track_a.id, mock_track_b.id, 0.8)
        e2 = _make_edge(mock_track_b.id, mock_track_a.id, 0.7)
        db.insert_edge(e1)
        db.insert_edge(e2)

        edges = db.get_all_edges()
        assert len(edges) == 2

    def test_delete_edges_for_track(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        db.insert_edge(_make_edge(mock_track_a.id, mock_track_b.id))
        db.insert_edge(_make_edge(mock_track_b.id, mock_track_a.id))

        db.delete_edges_for_track(mock_track_a.id)
        assert db.get_all_edges() == []

    def test_duplicate_edge_raises(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        e1 = _make_edge(mock_track_a.id, mock_track_b.id)
        db.insert_edge(e1)
        e2 = _make_edge(mock_track_a.id, mock_track_b.id)
        with pytest.raises(sqlite3.IntegrityError):
            db.insert_edge(e2)

    def test_reverse_edge_allowed(self, db, mock_track_a, mock_track_b):
        """A->B and B->A are different edges (directional)."""
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        e_forward = _make_edge(mock_track_a.id, mock_track_b.id, 0.8)
        e_reverse = _make_edge(mock_track_b.id, mock_track_a.id, 0.7)
        db.insert_edge(e_forward)
        db.insert_edge(e_reverse)

        assert db.get_edge(mock_track_a.id, mock_track_b.id) is not None
        assert db.get_edge(mock_track_b.id, mock_track_a.id) is not None

    def test_edge_user_created_flag(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        edge = Edge(
            source_id=mock_track_a.id,
            target_id=mock_track_b.id,
            compatibility_score=0.5,
            scores=EdgeScores(
                harmonic=0.5, bpm=0.5, energy=0.5,
                groove=0.5, frequency=0.5, mix_quality=0.5,
            ),
            is_user_created=True,
        )
        db.insert_edge(edge)

        retrieved = db.get_edge(mock_track_a.id, mock_track_b.id)
        assert retrieved.is_user_created is True


# ---------------------------------------------------------------------------
# Playlist CRUD
# ---------------------------------------------------------------------------


class TestPlaylistCRUD:
    def test_insert_and_get_playlist(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)

        pl = Playlist(
            name="Test Set",
            track_ids=[mock_track_a.id, mock_track_b.id],
        )
        db.insert_playlist(pl)
        retrieved = db.get_playlist(pl.id)

        assert retrieved is not None
        assert retrieved.name == "Test Set"
        assert retrieved.track_ids == [mock_track_a.id, mock_track_b.id]

    def test_get_playlist_nonexistent(self, db):
        assert db.get_playlist(uuid4()) is None

    def test_get_all_playlists_empty(self, db):
        assert db.get_all_playlists() == []

    def test_get_all_playlists(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        pl1 = Playlist(name="Set A", track_ids=[mock_track_a.id])
        pl2 = Playlist(name="Set B", track_ids=[mock_track_a.id])
        db.insert_playlist(pl1)
        db.insert_playlist(pl2)

        playlists = db.get_all_playlists()
        assert len(playlists) == 2

    def test_add_track_to_playlist(
        self, db, mock_track_a, mock_track_b
    ):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)

        pl = Playlist(name="Test", track_ids=[mock_track_a.id])
        db.insert_playlist(pl)

        # Add a second track at position 1
        db.add_track_to_playlist(pl.id, mock_track_b.id, 1)

        retrieved = db.get_playlist(pl.id)
        assert len(retrieved.track_ids) == 2
        assert retrieved.track_ids[1] == mock_track_b.id

    def test_get_playlist_tracks(self, db, mock_track_a, mock_track_b):
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)

        pl = Playlist(
            name="Test",
            track_ids=[mock_track_b.id, mock_track_a.id],
        )
        db.insert_playlist(pl)

        tracks = db.get_playlist_tracks(pl.id)
        assert len(tracks) == 2
        # Verify order: B first, then A
        assert tracks[0].id == mock_track_b.id
        assert tracks[1].id == mock_track_a.id

    def test_playlist_preserves_timestamps(
        self, db, mock_track_a
    ):
        db.insert_track(mock_track_a)
        pl = Playlist(name="Timestamped", track_ids=[mock_track_a.id])
        db.insert_playlist(pl)

        retrieved = db.get_playlist(pl.id)
        # Timestamps should round-trip through ISO format
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None

    def test_empty_playlist(self, db):
        pl = Playlist(name="Empty", track_ids=[])
        db.insert_playlist(pl)
        retrieved = db.get_playlist(pl.id)

        assert retrieved is not None
        assert retrieved.track_ids == []


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


class TestPreferences:
    def test_set_and_get_preference(self, db):
        db.set_preference("theme", "dark")
        assert db.get_preference("theme") == "dark"

    def test_get_nonexistent_preference(self, db):
        assert db.get_preference("nonexistent") is None

    def test_overwrite_preference(self, db):
        db.set_preference("volume", "50")
        db.set_preference("volume", "80")
        assert db.get_preference("volume") == "80"

    def test_multiple_preferences(self, db):
        db.set_preference("key1", "val1")
        db.set_preference("key2", "val2")
        assert db.get_preference("key1") == "val1"
        assert db.get_preference("key2") == "val2"


# ---------------------------------------------------------------------------
# Persistence (file-based DB round-trip)
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_track_survives_close_and_reopen(self, tmp_path, mock_track_a):
        """Insert a track, close the DB, reopen, verify data intact."""
        db_path = tmp_path / "persist.db"

        # Session 1: insert
        db1 = Database(db_path)
        db1.insert_track(mock_track_a)
        db1.close()

        # Session 2: reopen and verify
        db2 = Database(db_path)
        retrieved = db2.get_track(mock_track_a.id)
        db2.close()

        assert retrieved is not None
        assert retrieved.id == mock_track_a.id
        assert retrieved.file_path == mock_track_a.file_path
        assert retrieved.file_hash == mock_track_a.file_hash
        assert retrieved.dj_metrics.bpm == mock_track_a.dj_metrics.bpm
        assert retrieved.dj_metrics.key == mock_track_a.dj_metrics.key
        assert retrieved.spotify_style.energy == mock_track_a.spotify_style.energy
        assert retrieved.structure.drops == mock_track_a.structure.drops
        assert retrieved.metadata.artist == mock_track_a.metadata.artist

    def test_edge_survives_close_and_reopen(
        self, tmp_path, mock_track_a, mock_track_b
    ):
        db_path = tmp_path / "persist_edge.db"

        db1 = Database(db_path)
        db1.insert_track(mock_track_a)
        db1.insert_track(mock_track_b)
        edge = _make_edge(mock_track_a.id, mock_track_b.id, 0.9)
        db1.insert_edge(edge)
        db1.close()

        db2 = Database(db_path)
        retrieved = db2.get_edge(mock_track_a.id, mock_track_b.id)
        db2.close()

        assert retrieved is not None
        assert retrieved.compatibility_score == 0.9
        assert retrieved.scores.harmonic == 0.85

    def test_playlist_survives_close_and_reopen(
        self, tmp_path, mock_track_a
    ):
        db_path = tmp_path / "persist_pl.db"

        db1 = Database(db_path)
        db1.insert_track(mock_track_a)
        pl = Playlist(name="Persisted Set", track_ids=[mock_track_a.id])
        db1.insert_playlist(pl)
        db1.close()

        db2 = Database(db_path)
        retrieved = db2.get_playlist(pl.id)
        db2.close()

        assert retrieved is not None
        assert retrieved.name == "Persisted Set"
        assert retrieved.track_ids == [mock_track_a.id]

    def test_preferences_survive_close_and_reopen(self, tmp_path):
        db_path = tmp_path / "persist_pref.db"

        db1 = Database(db_path)
        db1.set_preference("harmonic_weight", "0.40")
        db1.close()

        db2 = Database(db_path)
        assert db2.get_preference("harmonic_weight") == "0.40"
        db2.close()

    def test_multiple_tracks_round_trip(
        self, tmp_path, mock_track_a, mock_track_b
    ):
        """Insert multiple tracks, close, reopen, verify all intact."""
        db_path = tmp_path / "multi.db"

        db1 = Database(db_path)
        db1.insert_track(mock_track_a)
        db1.insert_track(mock_track_b)
        db1.close()

        db2 = Database(db_path)
        tracks = db2.get_all_tracks()
        db2.close()

        assert len(tracks) == 2
        ids = {t.id for t in tracks}
        assert mock_track_a.id in ids
        assert mock_track_b.id in ids


# ---------------------------------------------------------------------------
# CacheManager
# ---------------------------------------------------------------------------


class TestCacheManager:
    def test_is_cached_true(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        cache = CacheManager(db)
        assert cache.is_cached("abc123") is True

    def test_is_cached_false(self, db):
        cache = CacheManager(db)
        assert cache.is_cached("nonexistent") is False

    def test_get_cached_track(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        cache = CacheManager(db)
        retrieved = cache.get_cached_track("abc123")

        assert retrieved is not None
        assert retrieved.id == mock_track_a.id
        assert retrieved.dj_metrics.bpm == 128.0

    def test_get_cached_track_none(self, db):
        cache = CacheManager(db)
        assert cache.get_cached_track("missing") is None

    def test_invalidate_track(self, db, mock_track_a):
        db.insert_track(mock_track_a)
        cache = CacheManager(db)

        cache.invalidate_track("/music/track_a.mp3")

        assert cache.is_cached("abc123") is False
        assert db.get_track(mock_track_a.id) is None

    def test_invalidate_track_nonexistent_no_error(self, db):
        cache = CacheManager(db)
        # Should not raise
        cache.invalidate_track("/music/nonexistent.mp3")

    def test_invalidate_track_cleans_edges(
        self, db, mock_track_a, mock_track_b
    ):
        """Invalidating a track also removes its edges."""
        db.insert_track(mock_track_a)
        db.insert_track(mock_track_b)
        db.insert_edge(_make_edge(mock_track_a.id, mock_track_b.id))

        cache = CacheManager(db)
        cache.invalidate_track("/music/track_a.mp3")

        assert db.get_all_edges() == []
        assert db.get_track(mock_track_a.id) is None
        # Track B should still exist
        assert db.get_track(mock_track_b.id) is not None
