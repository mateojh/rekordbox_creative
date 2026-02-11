"""Set history persistence — save, load, and query past DJ sets."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class HistoryStore:
    """CRUD operations for set history stored in SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_set(
        self,
        name: str,
        track_ids: list[UUID],
        transition_scores: list[float | None],
        *,
        duration_minutes: float = 0.0,
        avg_compatibility: float = 0.0,
        energy_profile: str = "",
        notes: str = "",
    ) -> str:
        """Save a set to history.

        Args:
            name: Display name for the set.
            track_ids: Ordered list of track UUIDs.
            transition_scores: Compatibility score for each transition
                (first element is None for the opening track).
            duration_minutes: Total set duration in minutes.
            avg_compatibility: Average transition score.
            energy_profile: Energy profile used (if generated).
            notes: User notes.

        Returns:
            The history entry ID.
        """
        history_id = str(uuid4())
        now = datetime.now().isoformat()

        self._conn.execute(
            """
            INSERT INTO set_history
                (id, name, created_at, duration_minutes, track_count,
                 avg_compatibility, energy_profile, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history_id,
                name,
                now,
                duration_minutes,
                len(track_ids),
                avg_compatibility,
                energy_profile,
                notes,
            ),
        )

        for position, track_id in enumerate(track_ids):
            score = transition_scores[position] if position < len(transition_scores) else None
            self._conn.execute(
                """
                INSERT INTO set_history_tracks
                    (history_id, position, track_id, transition_score)
                VALUES (?, ?, ?, ?)
                """,
                (history_id, position, str(track_id), score),
            )

        self._conn.commit()
        return history_id

    def get_all_sets(self) -> list[dict]:
        """Return summary info for all saved sets, newest first."""
        rows = self._conn.execute(
            """
            SELECT id, name, created_at, duration_minutes, track_count,
                   avg_compatibility, energy_profile, notes
            FROM set_history
            ORDER BY created_at DESC
            """
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "name": row[1],
                "created_at": row[2],
                "duration_minutes": row[3],
                "track_count": row[4],
                "avg_compatibility": row[5],
                "energy_profile": row[6],
                "notes": row[7],
            })
        return results

    def get_set_track_ids(self, history_id: str) -> list[UUID]:
        """Return ordered track IDs for a saved set."""
        rows = self._conn.execute(
            """
            SELECT track_id FROM set_history_tracks
            WHERE history_id = ?
            ORDER BY position
            """,
            (history_id,),
        ).fetchall()
        return [UUID(r[0]) for r in rows]

    def get_set_transitions(self, history_id: str) -> list[float | None]:
        """Return transition scores for a saved set."""
        rows = self._conn.execute(
            """
            SELECT transition_score FROM set_history_tracks
            WHERE history_id = ?
            ORDER BY position
            """,
            (history_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def delete_set(self, history_id: str) -> None:
        """Delete a set from history."""
        self._conn.execute(
            "DELETE FROM set_history_tracks WHERE history_id = ?",
            (history_id,),
        )
        self._conn.execute(
            "DELETE FROM set_history WHERE id = ?",
            (history_id,),
        )
        self._conn.commit()

    def update_notes(self, history_id: str, notes: str) -> None:
        """Update notes for a saved set."""
        self._conn.execute(
            "UPDATE set_history SET notes = ? WHERE id = ?",
            (notes, history_id),
        )
        self._conn.commit()

    def get_most_used_tracks(self, limit: int = 10) -> list[dict]:
        """Return track IDs sorted by frequency across all sets."""
        rows = self._conn.execute(
            """
            SELECT track_id, COUNT(*) as use_count
            FROM set_history_tracks
            GROUP BY track_id
            ORDER BY use_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [{"track_id": UUID(r[0]), "count": r[1]} for r in rows]

    def get_key_distribution(self) -> dict[str, int]:
        """Return key usage counts across all sets (requires JOIN with tracks)."""
        rows = self._conn.execute(
            """
            SELECT t.key_camelot, COUNT(*) as cnt
            FROM set_history_tracks sht
            JOIN tracks t ON sht.track_id = t.id
            GROUP BY t.key_camelot
            ORDER BY cnt DESC
            """
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def get_avg_compatibility_over_time(self) -> list[tuple[str, float]]:
        """Return (date, avg_compat) pairs for trend charting."""
        rows = self._conn.execute(
            """
            SELECT created_at, avg_compatibility
            FROM set_history
            ORDER BY created_at
            """
        ).fetchall()
        return [(r[0], r[1]) for r in rows]
