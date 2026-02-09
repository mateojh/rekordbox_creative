"""Analysis caching -- skip already-analyzed files."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from rekordbox_creative.db.database import Database

logger = logging.getLogger(__name__)


class AnalysisCacheManager:
    """Filters out already-analyzed files using MD5 hash comparison."""

    def __init__(self, database: Database) -> None:
        self.db = database

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute MD5 hash of file content."""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def is_cached(self, file_hash: str) -> bool:
        """Check if a track with this hash already exists in the database."""
        return self.db.get_track_by_hash(file_hash) is not None

    def get_cached_track(self, file_hash: str):
        """Get a cached track by file hash, or None."""
        return self.db.get_track_by_hash(file_hash)

    def filter_uncached(self, file_paths: list[Path]) -> list[Path]:
        """Return only files whose hash is NOT already in the database.

        Only genuinely new or modified files will be returned for analysis.
        Files that cannot be read are included (let the processor handle errors).
        """
        uncached: list[Path] = []
        for path in file_paths:
            try:
                file_hash = self.compute_file_hash(path)
                existing = self.db.get_track_by_hash(file_hash)
                if existing is None:
                    uncached.append(path)
                else:
                    logger.debug("Skipping cached: %s", path.name)
            except OSError as exc:
                logger.warning("Cannot read file %s: %s", path, exc)
                uncached.append(path)  # Let processor handle the error
        return uncached
