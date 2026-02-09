"""Generic ordered playlist export.

Provides common utilities used by all export formats.
"""

from __future__ import annotations

from uuid import UUID

from rekordbox_creative.db.models import Track


def resolve_tracks(track_ids: list[UUID], all_tracks: list[Track]) -> list[Track]:
    """Resolve a list of track IDs into ordered Track objects.

    Preserves order of track_ids. Skips IDs not found in all_tracks.
    """
    track_map = {t.id: t for t in all_tracks}
    return [track_map[tid] for tid in track_ids if tid in track_map]


def format_duration(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
