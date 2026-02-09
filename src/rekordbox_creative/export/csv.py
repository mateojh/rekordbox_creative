"""CSV export with all analysis data.

Exports the full track library (or a subset) as CSV with all metrics
for external analysis in spreadsheets or data tools.
"""

from __future__ import annotations

import csv
from pathlib import Path

from rekordbox_creative.db.models import Track

# Column order for the CSV export
CSV_COLUMNS = [
    "id",
    "filename",
    "file_path",
    "duration_seconds",
    "artist",
    "title",
    "album",
    "genre",
    "bpm",
    "bpm_stability",
    "key",
    "key_confidence",
    "energy",
    "danceability",
    "valence",
    "acousticness",
    "instrumentalness",
    "liveness",
    "mix_in_score",
    "mix_out_score",
    "frequency_weight",
    "groove_type",
    "cluster_id",
    "times_used",
]


def _track_to_row(track: Track) -> dict[str, str | float | int | None]:
    """Convert a Track to a flat dict for CSV writing."""
    return {
        "id": str(track.id),
        "filename": track.filename,
        "file_path": track.file_path,
        "duration_seconds": track.duration_seconds,
        "artist": track.metadata.artist or "",
        "title": track.metadata.title or "",
        "album": track.metadata.album or "",
        "genre": track.metadata.genre or "",
        "bpm": track.dj_metrics.bpm,
        "bpm_stability": track.dj_metrics.bpm_stability,
        "key": track.dj_metrics.key,
        "key_confidence": track.dj_metrics.key_confidence,
        "energy": track.spotify_style.energy,
        "danceability": track.spotify_style.danceability,
        "valence": track.spotify_style.valence,
        "acousticness": track.spotify_style.acousticness,
        "instrumentalness": track.spotify_style.instrumentalness,
        "liveness": track.spotify_style.liveness,
        "mix_in_score": track.dj_metrics.mix_in_score,
        "mix_out_score": track.dj_metrics.mix_out_score,
        "frequency_weight": track.dj_metrics.frequency_weight,
        "groove_type": track.dj_metrics.groove_type,
        "cluster_id": track.cluster_id if track.cluster_id is not None else "",
        "times_used": track.times_used,
    }


def export_csv(
    tracks: list[Track],
    output_path: Path | str,
) -> Path:
    """Write track analysis data as a CSV file.

    Args:
        tracks: List of tracks to export.
        output_path: File path to write (will be created/overwritten).

    Returns:
        The output path as a Path object.
    """
    output_path = Path(output_path)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for track in tracks:
            writer.writerow(_track_to_row(track))

    return output_path
