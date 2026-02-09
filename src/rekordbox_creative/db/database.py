"""SQLite database connection and CRUD operations."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

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

logger = logging.getLogger(__name__)


class Database:
    """SQLite database for persisting tracks, edges, playlists, and preferences."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def create_tables(self) -> None:
        """Create all tables and indexes from DATA_MODELS.md schema."""
        cur = self._conn.cursor()

        cur.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id TEXT PRIMARY KEY,
                file_path TEXT UNIQUE NOT NULL,
                file_hash TEXT NOT NULL,
                filename TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                sample_rate INTEGER DEFAULT 22050,

                -- Spotify-style (0-1)
                energy REAL,
                danceability REAL,
                acousticness REAL,
                instrumentalness REAL,
                valence REAL,
                liveness REAL,

                -- DJ metrics
                bpm REAL,
                bpm_stability REAL,
                key_camelot TEXT,
                key_confidence REAL,
                mix_in_score REAL,
                mix_out_score REAL,
                frequency_weight TEXT,
                groove_type TEXT,

                -- Structural (JSON)
                structure_json TEXT,

                -- Metadata (JSON)
                metadata_json TEXT,

                -- Graph state
                cluster_id INTEGER,
                times_used INTEGER DEFAULT 0,
                analyzed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tracks_bpm
                ON tracks(bpm);
            CREATE INDEX IF NOT EXISTS idx_tracks_key
                ON tracks(key_camelot);
            CREATE INDEX IF NOT EXISTS idx_tracks_energy
                ON tracks(energy);
            CREATE INDEX IF NOT EXISTS idx_tracks_file_hash
                ON tracks(file_hash);
            CREATE INDEX IF NOT EXISTS idx_tracks_cluster
                ON tracks(cluster_id);

            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES tracks(id),
                target_id TEXT NOT NULL REFERENCES tracks(id),
                compatibility_score REAL NOT NULL,
                harmonic_score REAL,
                bpm_score REAL,
                energy_score REAL,
                groove_score REAL,
                frequency_score REAL,
                mix_quality_score REAL,
                is_user_created INTEGER DEFAULT 0,
                UNIQUE(source_id, target_id)
            );

            CREATE INDEX IF NOT EXISTS idx_edges_source
                ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target
                ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_score
                ON edges(compatibility_score);

            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                graph_state_json TEXT
            );

            CREATE TABLE IF NOT EXISTS playlist_tracks (
                playlist_id TEXT NOT NULL REFERENCES playlists(id),
                track_id TEXT NOT NULL REFERENCES tracks(id),
                position INTEGER NOT NULL,
                PRIMARY KEY(playlist_id, track_id)
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    @property
    def connection(self) -> sqlite3.Connection:
        """Expose the underlying connection (for testing)."""
        return self._conn

    # ------------------------------------------------------------------
    # Track CRUD
    # ------------------------------------------------------------------

    def insert_track(self, track: Track) -> None:
        """Insert a track into the database."""
        self._conn.execute(
            """
            INSERT INTO tracks (
                id, file_path, file_hash, filename, duration_seconds,
                sample_rate, energy, danceability, acousticness,
                instrumentalness, valence, liveness,
                bpm, bpm_stability, key_camelot, key_confidence,
                mix_in_score, mix_out_score, frequency_weight, groove_type,
                structure_json, metadata_json,
                cluster_id, times_used, analyzed_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?
            )
            """,
            self._track_to_row(track),
        )
        self._conn.commit()

    def get_track(self, track_id: UUID) -> Track | None:
        """Get a track by its UUID."""
        row = self._conn.execute(
            "SELECT * FROM tracks WHERE id = ?", (str(track_id),)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_track(row)

    def get_track_by_hash(self, file_hash: str) -> Track | None:
        """Get a track by its file hash."""
        row = self._conn.execute(
            "SELECT * FROM tracks WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_track(row)

    def get_track_by_path(self, file_path: str) -> Track | None:
        """Get a track by its file path."""
        row = self._conn.execute(
            "SELECT * FROM tracks WHERE file_path = ?", (file_path,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_track(row)

    def get_all_tracks(self) -> list[Track]:
        """Get all tracks in the database."""
        rows = self._conn.execute("SELECT * FROM tracks").fetchall()
        return [self._row_to_track(r) for r in rows]

    def update_track(self, track: Track) -> None:
        """Update an existing track."""
        self._conn.execute(
            """
            UPDATE tracks SET
                file_path = ?, file_hash = ?, filename = ?,
                duration_seconds = ?, sample_rate = ?,
                energy = ?, danceability = ?, acousticness = ?,
                instrumentalness = ?, valence = ?, liveness = ?,
                bpm = ?, bpm_stability = ?, key_camelot = ?,
                key_confidence = ?, mix_in_score = ?, mix_out_score = ?,
                frequency_weight = ?, groove_type = ?,
                structure_json = ?, metadata_json = ?,
                cluster_id = ?, times_used = ?, analyzed_at = ?
            WHERE id = ?
            """,
            (
                track.file_path,
                track.file_hash,
                track.filename,
                track.duration_seconds,
                track.sample_rate,
                track.spotify_style.energy,
                track.spotify_style.danceability,
                track.spotify_style.acousticness,
                track.spotify_style.instrumentalness,
                track.spotify_style.valence,
                track.spotify_style.liveness,
                track.dj_metrics.bpm,
                track.dj_metrics.bpm_stability,
                track.dj_metrics.key,
                track.dj_metrics.key_confidence,
                track.dj_metrics.mix_in_score,
                track.dj_metrics.mix_out_score,
                track.dj_metrics.frequency_weight,
                track.dj_metrics.groove_type,
                track.structure.model_dump_json(),
                track.metadata.model_dump_json(),
                track.cluster_id,
                track.times_used,
                track.analyzed_at.isoformat(),
                str(track.id),
            ),
        )
        self._conn.commit()

    def delete_track(self, track_id: UUID) -> None:
        """Delete a track by its UUID."""
        self._conn.execute(
            "DELETE FROM tracks WHERE id = ?", (str(track_id),)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------

    def insert_edge(self, edge: Edge) -> None:
        """Insert an edge into the database."""
        self._conn.execute(
            """
            INSERT INTO edges (
                id, source_id, target_id, compatibility_score,
                harmonic_score, bpm_score, energy_score,
                groove_score, frequency_score, mix_quality_score,
                is_user_created
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(edge.id),
                str(edge.source_id),
                str(edge.target_id),
                edge.compatibility_score,
                edge.scores.harmonic,
                edge.scores.bpm,
                edge.scores.energy,
                edge.scores.groove,
                edge.scores.frequency,
                edge.scores.mix_quality,
                1 if edge.is_user_created else 0,
            ),
        )
        self._conn.commit()

    def get_edges_for_track(self, track_id: UUID) -> list[Edge]:
        """Get all edges where the track is source or target."""
        rows = self._conn.execute(
            """
            SELECT * FROM edges
            WHERE source_id = ? OR target_id = ?
            """,
            (str(track_id), str(track_id)),
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_all_edges(self) -> list[Edge]:
        """Get all edges in the database."""
        rows = self._conn.execute("SELECT * FROM edges").fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_edge(self, source_id: UUID, target_id: UUID) -> Edge | None:
        """Get a specific directional edge."""
        row = self._conn.execute(
            "SELECT * FROM edges WHERE source_id = ? AND target_id = ?",
            (str(source_id), str(target_id)),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_edge(row)

    def delete_edges_for_track(self, track_id: UUID) -> None:
        """Delete all edges connected to a track."""
        self._conn.execute(
            "DELETE FROM edges WHERE source_id = ? OR target_id = ?",
            (str(track_id), str(track_id)),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Playlist CRUD
    # ------------------------------------------------------------------

    def insert_playlist(self, playlist: Playlist) -> None:
        """Insert a playlist into the database."""
        self._conn.execute(
            """
            INSERT INTO playlists (id, name, created_at, updated_at, graph_state_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(playlist.id),
                playlist.name,
                playlist.created_at.isoformat(),
                playlist.updated_at.isoformat(),
                None,
            ),
        )
        # Insert playlist tracks in order
        for position, track_id in enumerate(playlist.track_ids):
            self._conn.execute(
                """
                INSERT INTO playlist_tracks (playlist_id, track_id, position)
                VALUES (?, ?, ?)
                """,
                (str(playlist.id), str(track_id), position),
            )
        self._conn.commit()

    def get_playlist(self, playlist_id: UUID) -> Playlist | None:
        """Get a playlist by its UUID."""
        row = self._conn.execute(
            "SELECT * FROM playlists WHERE id = ?", (str(playlist_id),)
        ).fetchone()
        if row is None:
            return None

        # Get ordered track IDs
        track_rows = self._conn.execute(
            """
            SELECT track_id FROM playlist_tracks
            WHERE playlist_id = ?
            ORDER BY position
            """,
            (str(playlist_id),),
        ).fetchall()
        track_ids = [UUID(r["track_id"]) for r in track_rows]

        return Playlist(
            id=UUID(row["id"]),
            name=row["name"],
            track_ids=track_ids,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_all_playlists(self) -> list[Playlist]:
        """Get all playlists."""
        rows = self._conn.execute("SELECT id FROM playlists").fetchall()
        playlists = []
        for row in rows:
            pl = self.get_playlist(UUID(row["id"]))
            if pl is not None:
                playlists.append(pl)
        return playlists

    def add_track_to_playlist(
        self, playlist_id: UUID, track_id: UUID, position: int
    ) -> None:
        """Add a track to a playlist at a given position."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (?, ?, ?)
            """,
            (str(playlist_id), str(track_id), position),
        )
        self._conn.commit()

    def get_playlist_tracks(self, playlist_id: UUID) -> list[Track]:
        """Get all tracks in a playlist, ordered by position."""
        rows = self._conn.execute(
            """
            SELECT t.* FROM tracks t
            JOIN playlist_tracks pt ON t.id = pt.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position
            """,
            (str(playlist_id),),
        ).fetchall()
        return [self._row_to_track(r) for r in rows]

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    def set_preference(self, key: str, value: str) -> None:
        """Set a user preference (insert or update)."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO preferences (key, value)
            VALUES (?, ?)
            """,
            (key, value),
        )
        self._conn.commit()

    def get_preference(self, key: str) -> str | None:
        """Get a user preference by key."""
        row = self._conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return row["value"]

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _track_to_row(track: Track) -> tuple:
        """Convert a Track model to a flat SQLite row tuple."""
        return (
            str(track.id),
            track.file_path,
            track.file_hash,
            track.filename,
            track.duration_seconds,
            track.sample_rate,
            track.spotify_style.energy,
            track.spotify_style.danceability,
            track.spotify_style.acousticness,
            track.spotify_style.instrumentalness,
            track.spotify_style.valence,
            track.spotify_style.liveness,
            track.dj_metrics.bpm,
            track.dj_metrics.bpm_stability,
            track.dj_metrics.key,
            track.dj_metrics.key_confidence,
            track.dj_metrics.mix_in_score,
            track.dj_metrics.mix_out_score,
            track.dj_metrics.frequency_weight,
            track.dj_metrics.groove_type,
            track.structure.model_dump_json(),
            track.metadata.model_dump_json(),
            track.cluster_id,
            track.times_used,
            track.analyzed_at.isoformat(),
        )

    @staticmethod
    def _row_to_track(row: sqlite3.Row) -> Track:
        """Reconstruct a Track model from a SQLite row."""
        structure_data = json.loads(row["structure_json"]) if row["structure_json"] else {}
        metadata_data = json.loads(row["metadata_json"]) if row["metadata_json"] else {}

        return Track(
            id=UUID(row["id"]),
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            filename=row["filename"],
            duration_seconds=row["duration_seconds"],
            sample_rate=row["sample_rate"],
            spotify_style=SpotifyStyleMetrics(
                energy=row["energy"],
                danceability=row["danceability"],
                acousticness=row["acousticness"],
                instrumentalness=row["instrumentalness"],
                valence=row["valence"],
                liveness=row["liveness"],
            ),
            dj_metrics=DJMetrics(
                bpm=row["bpm"],
                bpm_stability=row["bpm_stability"],
                key=row["key_camelot"],
                key_confidence=row["key_confidence"],
                mix_in_score=row["mix_in_score"],
                mix_out_score=row["mix_out_score"],
                frequency_weight=row["frequency_weight"],
                groove_type=row["groove_type"],
            ),
            structure=TrackStructure(**structure_data),
            metadata=TrackMetadata(**metadata_data),
            cluster_id=row["cluster_id"],
            times_used=row["times_used"],
            analyzed_at=datetime.fromisoformat(row["analyzed_at"]),
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> Edge:
        """Reconstruct an Edge model from a SQLite row."""
        return Edge(
            id=UUID(row["id"]),
            source_id=UUID(row["source_id"]),
            target_id=UUID(row["target_id"]),
            compatibility_score=row["compatibility_score"],
            scores=EdgeScores(
                harmonic=row["harmonic_score"],
                bpm=row["bpm_score"],
                energy=row["energy_score"],
                groove=row["groove_score"],
                frequency=row["frequency_score"],
                mix_quality=row["mix_quality_score"],
            ),
            is_user_created=bool(row["is_user_created"]),
        )
