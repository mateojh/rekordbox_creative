"""Audio analysis processing -- wraps audio_analyzer."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable

from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import (
    DJMetrics,
    SpotifyStyleMetrics,
    Track,
    TrackStructure,
)

logger = logging.getLogger(__name__)


class AnalysisError:
    """Record of a failed analysis attempt."""

    def __init__(self, file_path: Path, error: str) -> None:
        self.file_path = file_path
        self.error = error

    def __repr__(self) -> str:
        return f"AnalysisError(file_path={self.file_path!r}, error={self.error!r})"


class AnalysisResult:
    """Result of a batch analysis: successfully analyzed tracks + errors."""

    def __init__(
        self, tracks: list[Track], errors: list[AnalysisError]
    ) -> None:
        self.tracks = tracks
        self.errors = errors

    def __repr__(self) -> str:
        return (
            f"AnalysisResult(tracks={len(self.tracks)}, "
            f"errors={len(self.errors)})"
        )


# callback(filename, current_index, total)
ProgressCallback = Callable[[str, int, int], None]


def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of file content."""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


class AudioProcessor:
    """Wraps audio_analyzer for single and batch file processing."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database

    def analyze_file(self, file_path: Path) -> Track:
        """Analyze a single audio file using audio_analyzer.

        Returns a Track model populated with analysis results.
        """
        from audio_analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer()
        result = analyzer.analyze(str(file_path))

        file_hash = compute_file_hash(file_path)

        # Map audio_analyzer output to Track model
        spotify = result.get("spotify_style", {})
        dj = result.get("dj_metrics", {})
        struct = result.get("structure", {})

        return Track(
            file_path=str(file_path.resolve()),
            file_hash=file_hash,
            filename=file_path.name,
            duration_seconds=result.get("duration", 0.0),
            spotify_style=SpotifyStyleMetrics(
                energy=spotify.get("energy", 0.5),
                danceability=spotify.get("danceability", 0.5),
                acousticness=spotify.get("acousticness", 0.5),
                instrumentalness=spotify.get("instrumentalness", 0.5),
                valence=spotify.get("valence", 0.5),
                liveness=spotify.get("liveness", 0.5),
            ),
            dj_metrics=DJMetrics(
                bpm=dj.get("bpm", 120.0),
                bpm_stability=dj.get("bpm_stability", 0.5),
                key=dj.get("key", "1A"),
                key_confidence=dj.get("key_confidence", 0.5),
                mix_in_score=dj.get("mix_in_score", 0.5),
                mix_out_score=dj.get("mix_out_score", 0.5),
                frequency_weight=dj.get("frequency_weight", "balanced"),
                groove_type=dj.get("groove_type", "four_on_floor"),
            ),
            structure=TrackStructure(
                drops=struct.get("drops", []),
                breakdowns=struct.get("breakdowns", []),
                vocal_segments=struct.get("vocal_segments", []),
                build_sections=struct.get("build_sections", []),
                intro_end=struct.get("intro_end"),
                outro_start=struct.get("outro_start"),
            ),
        )

    def analyze_batch(
        self,
        file_paths: list[Path],
        progress_callback: ProgressCallback | None = None,
    ) -> AnalysisResult:
        """Analyze multiple files with continue-on-error behaviour.

        Never aborts the batch due to a single file failure.
        Calls progress_callback(filename, current_index, total) for each file.
        """
        tracks: list[Track] = []
        errors: list[AnalysisError] = []
        total = len(file_paths)

        for i, path in enumerate(file_paths):
            if progress_callback:
                progress_callback(path.name, i + 1, total)
            try:
                track = self.analyze_file(path)
                tracks.append(track)
                if self.database:
                    self.database.insert_track(track)
            except Exception as exc:
                logger.warning("Failed to analyze %s: %s", path, exc)
                errors.append(AnalysisError(path, str(exc)))

        return AnalysisResult(tracks=tracks, errors=errors)
