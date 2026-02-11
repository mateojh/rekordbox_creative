"""Tag store — CRUD for tags and track-tag junction table."""

from __future__ import annotations

import logging
import sqlite3
from uuid import UUID

logger = logging.getLogger(__name__)

# Predefined starter tags with distinct colors from the cluster palette
STARTER_TAGS: list[tuple[str, str]] = [
    ("Opener", "#22c55e"),
    ("Peak Time", "#ef4444"),
    ("Closer", "#6366f1"),
    ("Vocal", "#f59e0b"),
    ("Instrumental", "#06b6d4"),
    ("Underground", "#8b5cf6"),
    ("Crowd Pleaser", "#ec4899"),
    ("Transition Tool", "#64748b"),
]


class TagStore:
    """CRUD operations for tags and track-tag relationships."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_tables(self) -> None:
        """Create tags and track_tags tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT NOT NULL DEFAULT '#888888'
            );
            CREATE TABLE IF NOT EXISTS track_tags (
                track_id TEXT NOT NULL REFERENCES tracks(id),
                tag_id INTEGER NOT NULL REFERENCES tags(id),
                PRIMARY KEY(track_id, tag_id)
            );
        """)
        self._conn.commit()

    def seed_starter_tags(self) -> None:
        """Insert predefined starter tags (skip if they already exist)."""
        for name, color in STARTER_TAGS:
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)",
                    (name, color),
                )
            except sqlite3.IntegrityError:
                pass
        self._conn.commit()

    def create_tag(self, name: str, color: str = "#888888") -> int:
        """Create a new tag and return its ID."""
        cur = self._conn.execute(
            "INSERT INTO tags (name, color) VALUES (?, ?)",
            (name, color),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def update_tag(self, tag_id: int, name: str | None = None, color: str | None = None) -> None:
        """Update a tag's name and/or color."""
        if name is not None:
            self._conn.execute("UPDATE tags SET name = ? WHERE id = ?", (name, tag_id))
        if color is not None:
            self._conn.execute("UPDATE tags SET color = ? WHERE id = ?", (color, tag_id))
        self._conn.commit()

    def delete_tag(self, tag_id: int) -> None:
        """Delete a tag and all its track associations."""
        self._conn.execute("DELETE FROM track_tags WHERE tag_id = ?", (tag_id,))
        self._conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self._conn.commit()

    def get_all_tags(self) -> list[dict]:
        """Return all tags as list of {id, name, color}."""
        rows = self._conn.execute("SELECT id, name, color FROM tags ORDER BY name").fetchall()
        return [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in rows]

    def get_tag(self, tag_id: int) -> dict | None:
        """Get a single tag by ID."""
        row = self._conn.execute(
            "SELECT id, name, color FROM tags WHERE id = ?", (tag_id,)
        ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "name": row["name"], "color": row["color"]}

    def add_tag_to_track(self, track_id: UUID, tag_id: int) -> None:
        """Associate a tag with a track."""
        self._conn.execute(
            "INSERT OR IGNORE INTO track_tags (track_id, tag_id) VALUES (?, ?)",
            (str(track_id), tag_id),
        )
        self._conn.commit()

    def remove_tag_from_track(self, track_id: UUID, tag_id: int) -> None:
        """Remove a tag association from a track."""
        self._conn.execute(
            "DELETE FROM track_tags WHERE track_id = ? AND tag_id = ?",
            (str(track_id), tag_id),
        )
        self._conn.commit()

    def get_tags_for_track(self, track_id: UUID) -> list[dict]:
        """Get all tags for a specific track."""
        rows = self._conn.execute(
            """
            SELECT t.id, t.name, t.color
            FROM tags t
            JOIN track_tags tt ON t.id = tt.tag_id
            WHERE tt.track_id = ?
            ORDER BY t.name
            """,
            (str(track_id),),
        ).fetchall()
        return [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in rows]

    def get_tracks_by_tag(self, tag_id: int) -> list[str]:
        """Get all track IDs that have a specific tag."""
        rows = self._conn.execute(
            "SELECT track_id FROM track_tags WHERE tag_id = ?",
            (tag_id,),
        ).fetchall()
        return [r["track_id"] for r in rows]

    def get_tracks_by_tags(self, tag_ids: list[int]) -> list[str]:
        """Get track IDs that have ALL specified tags (AND logic)."""
        if not tag_ids:
            return []
        placeholders = ",".join("?" * len(tag_ids))
        rows = self._conn.execute(
            f"""
            SELECT track_id
            FROM track_tags
            WHERE tag_id IN ({placeholders})
            GROUP BY track_id
            HAVING COUNT(DISTINCT tag_id) = ?
            """,
            [*tag_ids, len(tag_ids)],
        ).fetchall()
        return [r["track_id"] for r in rows]
