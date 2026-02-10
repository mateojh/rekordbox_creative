"""Audio analysis processing -- wraps audio_analyzer."""

from __future__ import annotations

import hashlib
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def _analyze_single_file(file_path_str: str) -> Track:
    """Standalone function for multiprocessing — must be picklable (module-level).

    Takes a string path, returns a Track model.
    """
    from audio_analyzer import AudioAnalyzer

    from rekordbox_creative.analysis.metadata import MetadataExtractor

    file_path = Path(file_path_str)
    analyzer = AudioAnalyzer()
    result = analyzer.analyze(str(file_path))

    file_hash = compute_file_hash(file_path)

    spotify = result.spotify_style
    dj = result.dj_metrics
    struct = result.structure

    metadata_extractor = MetadataExtractor()
    metadata = metadata_extractor.extract(file_path)

    return Track(
        file_path=str(file_path.resolve()),
        file_hash=file_hash,
        filename=file_path.name,
        duration_seconds=result.duration_seconds,
        sample_rate=result.sample_rate,
        metadata=metadata,
        spotify_style=SpotifyStyleMetrics(
            energy=spotify.energy,
            danceability=spotify.danceability,
            acousticness=spotify.acousticness,
            instrumentalness=spotify.instrumentalness,
            valence=spotify.valence,
            liveness=spotify.liveness,
        ),
        dj_metrics=DJMetrics(
            bpm=dj.bpm,
            bpm_stability=dj.bpm_stability,
            key=dj.key,
            key_confidence=dj.key_confidence,
            mix_in_score=dj.mix_in_score,
            mix_out_score=dj.mix_out_score,
            frequency_weight=dj.frequency_weight,
            groove_type=dj.groove_type,
        ),
        structure=TrackStructure(
            drops=struct.drops,
            breakdowns=struct.breakdowns,
            vocal_segments=struct.vocal_segments,
            build_sections=struct.build_sections,
            intro_end=struct.intro_end,
            outro_start=struct.outro_start,
        ),
    )


class AudioProcessor:
    """Wraps audio_analyzer for single and batch file processing."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database

    def analyze_file(self, file_path: Path) -> Track:
        """Analyze a single audio file using audio_analyzer.

        Returns a Track model populated with analysis results.
        audio_analyzer returns a Pydantic AnalysisResult with attributes:
          .spotify_style, .dj_metrics, .structure, .duration_seconds, .sample_rate
        """
        from audio_analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer()
        result = analyzer.analyze(str(file_path))

        file_hash = compute_file_hash(file_path)

        # Access nested Pydantic models from audio_analyzer result
        spotify = result.spotify_style
        dj = result.dj_metrics
        struct = result.structure

        # Extract ID3/metadata tags
        from rekordbox_creative.analysis.metadata import MetadataExtractor

        metadata_extractor = MetadataExtractor()
        metadata = metadata_extractor.extract(file_path)

        return Track(
            file_path=str(file_path.resolve()),
            file_hash=file_hash,
            filename=file_path.name,
            duration_seconds=result.duration_seconds,
            sample_rate=result.sample_rate,
            metadata=metadata,
            spotify_style=SpotifyStyleMetrics(
                energy=spotify.energy,
                danceability=spotify.danceability,
                acousticness=spotify.acousticness,
                instrumentalness=spotify.instrumentalness,
                valence=spotify.valence,
                liveness=spotify.liveness,
            ),
            dj_metrics=DJMetrics(
                bpm=dj.bpm,
                bpm_stability=dj.bpm_stability,
                key=dj.key,
                key_confidence=dj.key_confidence,
                mix_in_score=dj.mix_in_score,
                mix_out_score=dj.mix_out_score,
                frequency_weight=dj.frequency_weight,
                groove_type=dj.groove_type,
            ),
            structure=TrackStructure(
                drops=struct.drops,
                breakdowns=struct.breakdowns,
                vocal_segments=struct.vocal_segments,
                build_sections=struct.build_sections,
                intro_end=struct.intro_end,
                outro_start=struct.outro_start,
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

    def analyze_batch_parallel(
        self,
        file_paths: list[Path],
        progress_callback: ProgressCallback | None = None,
        max_workers: int | None = None,
    ) -> AnalysisResult:
        """Analyze multiple files in parallel using multiprocessing.

        Uses ProcessPoolExecutor for CPU-bound audio analysis.
        Falls back to sequential if only 1 file or max_workers=1.
        """
        if max_workers is None:
            max_workers = max(1, (os.cpu_count() or 4) - 2)

        total = len(file_paths)
        if total == 0:
            return AnalysisResult(tracks=[], errors=[])

        if total == 1 or max_workers <= 1:
            return self.analyze_batch(file_paths, progress_callback)

        tracks: list[Track] = []
        errors: list[AnalysisError] = []
        completed = 0

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(_analyze_single_file, str(path)): path
                for path in file_paths
            }

            for future in as_completed(future_to_path):
                path = future_to_path[future]
                completed += 1
                if progress_callback:
                    progress_callback(path.name, completed, total)
                try:
                    track = future.result()
                    tracks.append(track)
                    if self.database:
                        self.database.insert_track(track)
                except Exception as exc:
                    logger.warning("Failed to analyze %s: %s", path, exc)
                    errors.append(AnalysisError(path, str(exc)))

        return AnalysisResult(tracks=tracks, errors=errors)
