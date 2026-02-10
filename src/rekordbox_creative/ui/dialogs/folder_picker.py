"""Folder picker dialog for selecting a music folder."""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog, QWidget


def pick_music_folder(parent: QWidget | None = None, last_folder: str | None = None) -> str | None:
    """Open a folder picker and return the selected path, or None if cancelled."""
    start_dir = last_folder or ""
    folder = QFileDialog.getExistingDirectory(
        parent,
        "Select Music Folder",
        start_dir,
        QFileDialog.Option.ShowDirsOnly,
    )
    return folder if folder else None
