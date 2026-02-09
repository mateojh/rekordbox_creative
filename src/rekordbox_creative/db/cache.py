"""Cache manager for track persistence lookups."""

import logging

from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import Track

logger = logging.getLogger(__name__)


class CacheManager:
    """Wraps the Database to provide cache-oriented queries for analysis."""

    def __init__(self, database: Database) -> None:
        self.db = database

    def is_cached(self, file_hash: str) -> bool:
        """Check if a track with this file hash exists in the database."""
        return self.db.get_track_by_hash(file_hash) is not None

    def get_cached_track(self, file_hash: str) -> Track | None:
        """Return the cached track for this file hash, or None."""
        return self.db.get_track_by_hash(file_hash)

    def invalidate_track(self, file_path: str) -> None:
        """Remove a stale entry by file path (e.g. when file was modified)."""
        track = self.db.get_track_by_path(file_path)
        if track is not None:
            # Also clean up any edges referencing this track
            self.db.delete_edges_for_track(track.id)
            self.db.delete_track(track.id)
            logger.info("Invalidated cached track: %s", file_path)
