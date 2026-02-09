"""M3U/M3U8 playlist format export.

Exports an ordered list of tracks as an extended M3U playlist file
with duration and title metadata per entry.
"""

from __future__ import annotations

from pathlib import Path

from rekordbox_creative.db.models import Track


def export_m3u(
    tracks: list[Track],
    output_path: Path | str,
    *,
    playlist_name: str = "Rekordbox Creative Set",
) -> Path:
    """Write an extended M3U playlist file.

    Args:
        tracks: Ordered list of tracks to include.
        output_path: File path to write (will be created/overwritten).
        playlist_name: Playlist title comment at top of file.

    Returns:
        The output path as a Path object.
    """
    output_path = Path(output_path)

    lines = ["#EXTM3U", f"# {playlist_name}"]

    for track in tracks:
        duration = int(track.duration_seconds)
        # Use metadata title/artist if available, else filename
        artist = track.metadata.artist or "Unknown Artist"
        title = track.metadata.title or track.filename
        display = f"{artist} - {title}"

        lines.append(f"#EXTINF:{duration},{display}")
        lines.append(track.file_path)

    lines.append("")  # trailing newline
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
