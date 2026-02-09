"""Audio file discovery and folder scanning."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}


class AudioScanner:
    """Discovers audio files in a directory recursively."""

    def __init__(self, folder_path: Path | str) -> None:
        self.folder_path = Path(folder_path)

    def scan(self) -> list[Path]:
        """Recursively discover audio files, filter by extension.

        Returns sorted list of absolute paths.
        Raises FileNotFoundError if folder doesn't exist.
        Raises NotADirectoryError if path is not a directory.
        """
        if not self.folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {self.folder_path}")
        if not self.folder_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.folder_path}")

        files: list[Path] = []
        for path in self.folder_path.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path.resolve())
        return sorted(files)
