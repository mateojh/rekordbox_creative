"""Export dialog for saving playlists in various formats."""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog, QWidget

_FILTERS = {
    "m3u": "M3U Playlist (*.m3u)",
    "xml": "Rekordbox XML (*.xml)",
    "csv": "CSV File (*.csv)",
}


def pick_export_path(
    parent: QWidget | None = None,
    fmt: str = "m3u",
    default_name: str = "playlist",
) -> str | None:
    """Open a save dialog and return the chosen path, or None if cancelled."""
    ext_filter = _FILTERS.get(fmt, "All Files (*)")
    ext = fmt if fmt != "xml" else "xml"
    path, _ = QFileDialog.getSaveFileName(
        parent,
        f"Export as {fmt.upper()}",
        f"{default_name}.{ext}",
        ext_filter,
    )
    return path if path else None
