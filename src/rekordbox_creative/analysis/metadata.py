"""Metadata extraction from audio files using mutagen."""

from __future__ import annotations

import logging
from pathlib import Path

from rekordbox_creative.db.models import TrackMetadata

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extracts ID3/file metadata using mutagen."""

    def extract(self, file_path: Path | str) -> TrackMetadata:
        """Extract metadata from an audio file.

        Returns TrackMetadata with whatever tags are available.
        Handles files with no metadata gracefully.
        """
        file_path = Path(file_path)
        try:
            import mutagen

            audio = mutagen.File(str(file_path), easy=True)
            if audio is None:
                return TrackMetadata()

            return TrackMetadata(
                artist=_first_tag(audio, "artist"),
                title=_first_tag(audio, "title"),
                album=_first_tag(audio, "album"),
                genre=_first_tag(audio, "genre"),
                year=_parse_year(_first_tag(audio, "date")),
                track_number=_parse_int(_first_tag(audio, "tracknumber")),
            )
        except Exception as exc:
            logger.warning(
                "Metadata extraction failed for %s: %s", file_path, exc
            )
            return TrackMetadata()


def _first_tag(audio: object, key: str) -> str | None:
    """Get first value of a tag list, or None."""
    values = audio.get(key)  # type: ignore[union-attr]
    if values and len(values) > 0:
        return str(values[0])
    return None


def _parse_year(value: str | None) -> int | None:
    """Parse a year from a date string (e.g. '2023', '2023-01-15')."""
    if value is None:
        return None
    try:
        return int(value[:4])
    except (ValueError, IndexError):
        return None


def _parse_int(value: str | None) -> int | None:
    """Parse an integer from a string that may contain '/' (e.g. '3/12')."""
    if value is None:
        return None
    try:
        return int(value.split("/")[0])
    except (ValueError, IndexError):
        return None
