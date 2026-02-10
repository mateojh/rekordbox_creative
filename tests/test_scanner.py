"""Tests for audio scanning and analysis pipeline.

Covers SCAN-001 (Folder Selection), SCAN-002 (Batch Analysis),
SCAN-003 (Analysis Caching), SCAN-004 (Metadata Extraction),
and SCAN-005 (Error Resilience).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rekordbox_creative.analysis.cache_manager import AnalysisCacheManager
from rekordbox_creative.analysis.metadata import (
    MetadataExtractor,
    _parse_int,
    _parse_year,
)
from rekordbox_creative.analysis.processor import (
    AnalysisError,
    AnalysisResult,
    AudioProcessor,
    compute_file_hash,
)
from rekordbox_creative.analysis.scanner import (
    SUPPORTED_EXTENSIONS,
    AudioScanner,
)
from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import TrackMetadata

# ===================================================================
# Helper: create dummy audio files in a temp directory
# ===================================================================

def _create_file(path: Path, content: bytes = b"dummy") -> Path:
    """Create a file with given content and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ===================================================================
# SCAN-001: Folder Selection / AudioScanner
# ===================================================================

class TestAudioScanner:
    """Tests for AudioScanner.scan()."""

    def test_scan_finds_audio_files(self, tmp_path: Path) -> None:
        """Only audio files with supported extensions are returned."""
        _create_file(tmp_path / "track.mp3")
        _create_file(tmp_path / "track.wav")
        _create_file(tmp_path / "readme.txt")
        _create_file(tmp_path / "image.png")

        scanner = AudioScanner(tmp_path)
        results = scanner.scan()

        names = [p.name for p in results]
        assert "track.mp3" in names
        assert "track.wav" in names
        assert "readme.txt" not in names
        assert "image.png" not in names
        assert len(results) == 2

    def test_scan_recursive(self, tmp_path: Path) -> None:
        """Files in nested subdirectories are discovered."""
        _create_file(tmp_path / "level1" / "a.mp3")
        _create_file(tmp_path / "level1" / "level2" / "b.flac")
        _create_file(tmp_path / "c.ogg")

        scanner = AudioScanner(tmp_path)
        results = scanner.scan()

        names = [p.name for p in results]
        assert "a.mp3" in names
        assert "b.flac" in names
        assert "c.ogg" in names
        assert len(results) == 3

    def test_scan_empty_folder(self, tmp_path: Path) -> None:
        """Empty folder returns empty list."""
        scanner = AudioScanner(tmp_path)
        results = scanner.scan()
        assert results == []

    def test_scan_nonexistent_folder(self) -> None:
        """Non-existent folder raises FileNotFoundError."""
        scanner = AudioScanner(Path("/nonexistent/folder/abc123"))
        with pytest.raises(FileNotFoundError):
            scanner.scan()

    def test_scan_not_a_directory(self, tmp_path: Path) -> None:
        """Passing a file path raises NotADirectoryError."""
        f = _create_file(tmp_path / "file.mp3")
        scanner = AudioScanner(f)
        with pytest.raises(NotADirectoryError):
            scanner.scan()

    def test_scan_case_insensitive_extensions(self, tmp_path: Path) -> None:
        """Extensions like .MP3 and .Flac are matched case-insensitively."""
        _create_file(tmp_path / "upper.MP3")
        _create_file(tmp_path / "mixed.Flac")
        _create_file(tmp_path / "lower.wav")

        scanner = AudioScanner(tmp_path)
        results = scanner.scan()

        names = [p.name for p in results]
        assert "upper.MP3" in names
        assert "mixed.Flac" in names
        assert "lower.wav" in names
        assert len(results) == 3

    def test_scan_all_supported_extensions(self, tmp_path: Path) -> None:
        """Every supported extension is discovered."""
        for ext in SUPPORTED_EXTENSIONS:
            _create_file(tmp_path / f"track{ext}")

        scanner = AudioScanner(tmp_path)
        results = scanner.scan()
        assert len(results) == len(SUPPORTED_EXTENSIONS)

    def test_scan_returns_absolute_paths(self, tmp_path: Path) -> None:
        """All returned paths are absolute."""
        _create_file(tmp_path / "track.mp3")
        scanner = AudioScanner(tmp_path)
        results = scanner.scan()
        for p in results:
            assert p.is_absolute()

    def test_scan_returns_sorted_paths(self, tmp_path: Path) -> None:
        """Results are sorted by path."""
        _create_file(tmp_path / "z_track.mp3")
        _create_file(tmp_path / "a_track.mp3")
        _create_file(tmp_path / "m_track.mp3")

        scanner = AudioScanner(tmp_path)
        results = scanner.scan()
        assert results == sorted(results)

    def test_scan_accepts_string_path(self, tmp_path: Path) -> None:
        """Scanner accepts a string path, not just pathlib.Path."""
        _create_file(tmp_path / "track.mp3")
        scanner = AudioScanner(str(tmp_path))
        results = scanner.scan()
        assert len(results) == 1

    def test_scan_ignores_hidden_files(self, tmp_path: Path) -> None:
        """Hidden files with audio extensions are still found (no special filter)."""
        _create_file(tmp_path / ".hidden.mp3")
        _create_file(tmp_path / "visible.mp3")

        scanner = AudioScanner(tmp_path)
        results = scanner.scan()
        # Both should be found -- hidden files are valid audio files
        assert len(results) == 2

    def test_scan_no_audio_files(self, tmp_path: Path) -> None:
        """Folder with files but no audio returns empty list."""
        _create_file(tmp_path / "readme.txt")
        _create_file(tmp_path / "data.json")
        _create_file(tmp_path / "image.jpg")

        scanner = AudioScanner(tmp_path)
        results = scanner.scan()
        assert results == []


# ===================================================================
# SCAN-002: Batch Analysis / AudioProcessor (mocked)
# ===================================================================

def _make_mock_analysis_result():
    """Return a realistic audio_analyzer output (Pydantic-like with attribute access)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        duration_seconds=300.0,
        sample_rate=22050,
        spotify_style=SimpleNamespace(
            energy=0.75,
            danceability=0.80,
            acousticness=0.10,
            instrumentalness=0.60,
            valence=0.55,
            liveness=0.15,
        ),
        dj_metrics=SimpleNamespace(
            bpm=128.0,
            bpm_stability=0.95,
            key="8A",
            key_confidence=0.88,
            mix_in_score=0.85,
            mix_out_score=0.80,
            frequency_weight="bass_heavy",
            groove_type="four_on_floor",
        ),
        structure=SimpleNamespace(
            drops=[64.0, 192.0],
            breakdowns=[[96.0, 128.0]],
            vocal_segments=[[32.0, 64.0]],
            build_sections=[[48.0, 64.0]],
            intro_end=16.0,
            outro_start=280.0,
        ),
    )


class TestAudioProcessor:
    """Tests for AudioProcessor."""

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_analyze_file_produces_valid_track(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """Single file analysis returns a valid Track model."""
        mock_instance = MagicMock()
        mock_instance.analyze.return_value = _make_mock_analysis_result()
        mock_analyzer_cls.return_value = mock_instance
        mock_hash.return_value = "fakehash123"

        audio_file = _create_file(tmp_path / "song.mp3", b"fake audio")
        processor = AudioProcessor()
        track = processor.analyze_file(audio_file)

        assert track.filename == "song.mp3"
        assert track.file_hash == "fakehash123"
        assert track.duration_seconds == 300.0
        assert track.dj_metrics.bpm == 128.0
        assert track.dj_metrics.key == "8A"
        assert track.spotify_style.energy == 0.75
        assert track.structure.drops == [64.0, 192.0]

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_analyze_file_minimal_values(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """Analyzer returning minimal values produces a valid Track."""
        from types import SimpleNamespace

        mock_instance = MagicMock()
        mock_instance.analyze.return_value = SimpleNamespace(
            duration_seconds=0.0,
            sample_rate=22050,
            spotify_style=SimpleNamespace(
                energy=0.5, danceability=0.5, acousticness=0.0,
                instrumentalness=0.0, valence=0.5, liveness=0.0,
            ),
            dj_metrics=SimpleNamespace(
                bpm=120.0, bpm_stability=0.5, key="1A", key_confidence=0.5,
                mix_in_score=0.5, mix_out_score=0.5,
                frequency_weight="balanced", groove_type="straight",
            ),
            structure=SimpleNamespace(
                drops=[], breakdowns=[], vocal_segments=[],
                build_sections=[], intro_end=None, outro_start=None,
            ),
        )
        mock_analyzer_cls.return_value = mock_instance
        mock_hash.return_value = "hash000"

        audio_file = _create_file(tmp_path / "empty.mp3", b"data")
        processor = AudioProcessor()
        track = processor.analyze_file(audio_file)

        assert track.dj_metrics.bpm == 120.0
        assert track.dj_metrics.key == "1A"
        assert track.spotify_style.energy == 0.5
        assert track.duration_seconds == 0.0

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_analyze_batch_multiple_files(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """Batch analysis processes multiple files and returns all tracks."""
        mock_instance = MagicMock()
        mock_instance.analyze.return_value = _make_mock_analysis_result()
        mock_analyzer_cls.return_value = mock_instance
        mock_hash.return_value = "batchhash"

        files = []
        for i in range(5):
            f = _create_file(tmp_path / f"track_{i}.mp3", f"audio{i}".encode())
            files.append(f)

        processor = AudioProcessor()
        result = processor.analyze_batch(files)

        assert len(result.tracks) == 5
        assert len(result.errors) == 0

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_analyze_batch_progress_callback(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """Progress callback is called with correct arguments for each file."""
        mock_instance = MagicMock()
        mock_instance.analyze.return_value = _make_mock_analysis_result()
        mock_analyzer_cls.return_value = mock_instance
        mock_hash.return_value = "cbhash"

        files = [
            _create_file(tmp_path / "a.mp3", b"a"),
            _create_file(tmp_path / "b.mp3", b"b"),
            _create_file(tmp_path / "c.mp3", b"c"),
        ]

        callback_calls: list[tuple[str, int, int]] = []

        def progress_cb(filename: str, current: int, total: int) -> None:
            callback_calls.append((filename, current, total))

        processor = AudioProcessor()
        processor.analyze_batch(files, progress_callback=progress_cb)

        assert len(callback_calls) == 3
        assert callback_calls[0] == ("a.mp3", 1, 3)
        assert callback_calls[1] == ("b.mp3", 2, 3)
        assert callback_calls[2] == ("c.mp3", 3, 3)

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_analyze_batch_stores_to_database(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """When a database is provided, tracks are inserted."""
        mock_instance = MagicMock()
        mock_instance.analyze.return_value = _make_mock_analysis_result()
        mock_analyzer_cls.return_value = mock_instance

        # Use unique hashes so DB unique constraint is not violated
        call_count = 0

        def unique_hash(path: Path) -> str:
            nonlocal call_count
            call_count += 1
            return f"hash_{call_count}"

        mock_hash.side_effect = unique_hash

        db = Database(":memory:")
        files = [
            _create_file(tmp_path / "x.mp3", b"x"),
            _create_file(tmp_path / "y.mp3", b"y"),
        ]

        processor = AudioProcessor(database=db)
        result = processor.analyze_batch(files)

        assert len(result.tracks) == 2
        all_tracks = db.get_all_tracks()
        assert len(all_tracks) == 2


# ===================================================================
# SCAN-005: Error Resilience
# ===================================================================

class TestErrorResilience:
    """Batch analysis continues when individual files fail."""

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_one_bad_file_does_not_stop_batch(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """Corrupted file generates an error but other files still succeed."""
        good_result = _make_mock_analysis_result()

        f_good1 = _create_file(tmp_path / "good1.mp3", b"g1")
        f_bad = _create_file(tmp_path / "bad.mp3", b"bad")
        f_good2 = _create_file(tmp_path / "good2.mp3", b"g2")

        call_idx = 0

        def side_effect_analyze(path: str) -> dict:
            nonlocal call_idx
            call_idx += 1
            if Path(path).name == "bad.mp3":
                raise RuntimeError("Corrupt file!")
            return good_result

        mock_instance = MagicMock()
        mock_instance.analyze.side_effect = side_effect_analyze
        mock_analyzer_cls.return_value = mock_instance
        mock_hash.return_value = "somehash"

        processor = AudioProcessor()
        result = processor.analyze_batch([f_good1, f_bad, f_good2])

        assert len(result.tracks) == 2
        assert len(result.errors) == 1
        assert result.errors[0].file_path == f_bad
        assert "Corrupt" in result.errors[0].error

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_all_files_fail_returns_empty_tracks(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """When every file fails, we get 0 tracks and N errors."""
        mock_instance = MagicMock()
        mock_instance.analyze.side_effect = RuntimeError("all broken")
        mock_analyzer_cls.return_value = mock_instance
        mock_hash.return_value = "h"

        files = [
            _create_file(tmp_path / f"bad{i}.mp3", b"x")
            for i in range(3)
        ]

        processor = AudioProcessor()
        result = processor.analyze_batch(files)

        assert len(result.tracks) == 0
        assert len(result.errors) == 3

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_error_contains_filename_and_message(
        self, mock_analyzer_cls: MagicMock, mock_hash: MagicMock, tmp_path: Path
    ) -> None:
        """AnalysisError records the file path and error message."""
        mock_instance = MagicMock()
        mock_instance.analyze.side_effect = ValueError("bad format")
        mock_analyzer_cls.return_value = mock_instance
        mock_hash.return_value = "h"

        f = _create_file(tmp_path / "broken.mp3", b"x")
        processor = AudioProcessor()
        result = processor.analyze_batch([f])

        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.file_path == f
        assert "bad format" in err.error

    def test_analysis_result_repr(self) -> None:
        """AnalysisResult has a useful repr."""
        result = AnalysisResult(tracks=[], errors=[])
        assert "tracks=0" in repr(result)
        assert "errors=0" in repr(result)

    def test_analysis_error_repr(self, tmp_path: Path) -> None:
        """AnalysisError has a useful repr."""
        err = AnalysisError(tmp_path / "f.mp3", "oops")
        assert "oops" in repr(err)


# ===================================================================
# File hash computation
# ===================================================================

class TestFileHash:
    """Tests for compute_file_hash."""

    def test_hash_deterministic(self, tmp_path: Path) -> None:
        """Same content always produces the same hash."""
        f = _create_file(tmp_path / "file.bin", b"hello world")
        h1 = compute_file_hash(f)
        h2 = compute_file_hash(f)
        assert h1 == h2

    def test_hash_differs_for_different_content(self, tmp_path: Path) -> None:
        """Different content produces different hashes."""
        f1 = _create_file(tmp_path / "a.bin", b"content_a")
        f2 = _create_file(tmp_path / "b.bin", b"content_b")
        assert compute_file_hash(f1) != compute_file_hash(f2)

    def test_hash_same_content_different_names(self, tmp_path: Path) -> None:
        """Hash depends on content, not filename."""
        content = b"identical_content_12345"
        f1 = _create_file(tmp_path / "name1.mp3", content)
        f2 = _create_file(tmp_path / "name2.mp3", content)
        assert compute_file_hash(f1) == compute_file_hash(f2)

    def test_hash_is_md5_hex(self, tmp_path: Path) -> None:
        """Hash is a 32-char hex string (MD5)."""
        f = _create_file(tmp_path / "file.bin", b"data")
        h = compute_file_hash(f)
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)


# ===================================================================
# SCAN-004: Metadata Extraction
# ===================================================================

class TestMetadataExtractor:
    """Tests for MetadataExtractor using mocked mutagen."""

    @patch("rekordbox_creative.analysis.metadata.mutagen")
    def test_extract_full_metadata(self, mock_mutagen: MagicMock) -> None:
        """All available tags are extracted correctly."""
        mock_audio = {
            "artist": ["Test Artist"],
            "title": ["Test Title"],
            "album": ["Test Album"],
            "genre": ["Electronic"],
            "date": ["2023"],
            "tracknumber": ["5/12"],
        }
        mock_mutagen.File.return_value = mock_audio

        extractor = MetadataExtractor()
        meta = extractor.extract(Path("/fake/track.mp3"))

        assert meta.artist == "Test Artist"
        assert meta.title == "Test Title"
        assert meta.album == "Test Album"
        assert meta.genre == "Electronic"
        assert meta.year == 2023
        assert meta.track_number == 5

    @patch("rekordbox_creative.analysis.metadata.mutagen")
    def test_extract_no_metadata(self, mock_mutagen: MagicMock) -> None:
        """File with no metadata returns empty TrackMetadata."""
        mock_mutagen.File.return_value = None

        extractor = MetadataExtractor()
        meta = extractor.extract(Path("/fake/notags.mp3"))

        assert meta == TrackMetadata()

    @patch("rekordbox_creative.analysis.metadata.mutagen")
    def test_extract_partial_metadata(self, mock_mutagen: MagicMock) -> None:
        """Only some tags present returns partial TrackMetadata."""
        mock_audio = {
            "artist": ["Partial Artist"],
            "title": ["Partial Title"],
        }
        mock_mutagen.File.return_value = mock_audio

        extractor = MetadataExtractor()
        meta = extractor.extract(Path("/fake/partial.mp3"))

        assert meta.artist == "Partial Artist"
        assert meta.title == "Partial Title"
        assert meta.album is None
        assert meta.genre is None
        assert meta.year is None

    @patch("rekordbox_creative.analysis.metadata.mutagen")
    def test_extract_handles_exception(self, mock_mutagen: MagicMock) -> None:
        """Mutagen exceptions return empty TrackMetadata gracefully."""
        mock_mutagen.File.side_effect = Exception("read error")

        extractor = MetadataExtractor()
        meta = extractor.extract(Path("/fake/error.mp3"))

        assert meta == TrackMetadata()

    @patch("rekordbox_creative.analysis.metadata.mutagen")
    def test_extract_date_with_full_iso(self, mock_mutagen: MagicMock) -> None:
        """Date in ISO format like '2023-05-15' extracts year correctly."""
        mock_audio = {"date": ["2023-05-15"]}
        mock_mutagen.File.return_value = mock_audio

        extractor = MetadataExtractor()
        meta = extractor.extract(Path("/fake/dated.mp3"))

        assert meta.year == 2023

    @patch("rekordbox_creative.analysis.metadata.mutagen")
    def test_extract_accepts_string_path(self, mock_mutagen: MagicMock) -> None:
        """MetadataExtractor accepts string paths too."""
        mock_mutagen.File.return_value = {"title": ["String Path"]}

        extractor = MetadataExtractor()
        meta = extractor.extract("/fake/string_path.mp3")

        assert meta.title == "String Path"


class TestMetadataHelpers:
    """Tests for the _parse_year and _parse_int helper functions."""

    def test_parse_year_none(self) -> None:
        assert _parse_year(None) is None

    def test_parse_year_four_digit(self) -> None:
        assert _parse_year("2023") == 2023

    def test_parse_year_iso_date(self) -> None:
        assert _parse_year("2023-05-15") == 2023

    def test_parse_year_invalid(self) -> None:
        assert _parse_year("nope") is None

    def test_parse_year_empty(self) -> None:
        assert _parse_year("") is None

    def test_parse_int_none(self) -> None:
        assert _parse_int(None) is None

    def test_parse_int_simple(self) -> None:
        assert _parse_int("5") == 5

    def test_parse_int_with_slash(self) -> None:
        assert _parse_int("3/12") == 3

    def test_parse_int_invalid(self) -> None:
        assert _parse_int("abc") is None


# ===================================================================
# SCAN-003: Analysis Caching
# ===================================================================

class TestAnalysisCacheManager:
    """Tests for AnalysisCacheManager."""

    def test_filter_uncached_all_new(self, tmp_path: Path) -> None:
        """When nothing is cached, all files pass through."""
        db = Database(":memory:")
        cache = AnalysisCacheManager(db)

        f1 = _create_file(tmp_path / "new1.mp3", b"content1")
        f2 = _create_file(tmp_path / "new2.mp3", b"content2")

        uncached = cache.filter_uncached([f1, f2])
        assert len(uncached) == 2
        assert f1 in uncached
        assert f2 in uncached

    def test_filter_uncached_skips_cached(
        self, tmp_path: Path, mock_track_a
    ) -> None:
        """Files whose hash already exists in DB are filtered out."""
        db = Database(":memory:")

        # Insert a track with a known hash
        content = b"known_content_abc"
        f_cached = _create_file(tmp_path / "cached.mp3", content)
        known_hash = AnalysisCacheManager.compute_file_hash(f_cached)

        # Update mock_track_a to have this hash and insert into DB
        mock_track_a.file_hash = known_hash
        db.insert_track(mock_track_a)

        f_new = _create_file(tmp_path / "new.mp3", b"different_content")

        cache = AnalysisCacheManager(db)
        uncached = cache.filter_uncached([f_cached, f_new])

        assert len(uncached) == 1
        assert f_new in uncached

    def test_filter_uncached_modified_file(
        self, tmp_path: Path, mock_track_a
    ) -> None:
        """Modified file (different hash) is not filtered out."""
        db = Database(":memory:")

        # Insert a track with the original hash
        mock_track_a.file_hash = "original_hash_value"
        db.insert_track(mock_track_a)

        # File on disk has different content than the DB hash
        f = _create_file(tmp_path / "modified.mp3", b"completely_new_content")

        cache = AnalysisCacheManager(db)
        uncached = cache.filter_uncached([f])

        # Should pass through because its hash won't match "original_hash_value"
        assert len(uncached) == 1

    def test_compute_file_hash_deterministic(self, tmp_path: Path) -> None:
        """Same content always produces the same hash."""
        f = _create_file(tmp_path / "test.bin", b"hello world hash")
        h1 = AnalysisCacheManager.compute_file_hash(f)
        h2 = AnalysisCacheManager.compute_file_hash(f)
        assert h1 == h2

    def test_compute_file_hash_different_content(
        self, tmp_path: Path
    ) -> None:
        """Different content produces different hashes."""
        f1 = _create_file(tmp_path / "a.bin", b"aaa")
        f2 = _create_file(tmp_path / "b.bin", b"bbb")
        assert (
            AnalysisCacheManager.compute_file_hash(f1)
            != AnalysisCacheManager.compute_file_hash(f2)
        )

    def test_is_cached_true(self, tmp_path: Path, mock_track_a) -> None:
        """is_cached returns True when hash exists in DB."""
        db = Database(":memory:")
        db.insert_track(mock_track_a)

        cache = AnalysisCacheManager(db)
        assert cache.is_cached(mock_track_a.file_hash) is True

    def test_is_cached_false(self) -> None:
        """is_cached returns False when hash does not exist."""
        db = Database(":memory:")
        cache = AnalysisCacheManager(db)
        assert cache.is_cached("nonexistent_hash") is False

    def test_get_cached_track(self, mock_track_a) -> None:
        """get_cached_track returns the track when it exists."""
        db = Database(":memory:")
        db.insert_track(mock_track_a)

        cache = AnalysisCacheManager(db)
        result = cache.get_cached_track(mock_track_a.file_hash)
        assert result is not None
        assert result.file_hash == mock_track_a.file_hash

    def test_get_cached_track_miss(self) -> None:
        """get_cached_track returns None for unknown hash."""
        db = Database(":memory:")
        cache = AnalysisCacheManager(db)
        assert cache.get_cached_track("nope") is None

    def test_filter_uncached_empty_list(self) -> None:
        """Empty file list returns empty result."""
        db = Database(":memory:")
        cache = AnalysisCacheManager(db)
        assert cache.filter_uncached([]) == []


# ===================================================================
# Integration: Scanner + CacheManager pipeline
# ===================================================================

class TestScannerCachePipeline:
    """Integration tests for the scan-then-cache-filter workflow."""

    @patch("rekordbox_creative.analysis.processor.compute_file_hash")
    @patch("audio_analyzer.AudioAnalyzer")
    def test_full_scan_analyze_rescan_pipeline(
        self,
        mock_analyzer_cls: MagicMock,
        mock_hash: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Scan -> analyze -> rescan: only new files are re-analyzed."""
        mock_instance = MagicMock()
        mock_instance.analyze.return_value = _make_mock_analysis_result()
        mock_analyzer_cls.return_value = mock_instance

        # Each file gets a unique hash based on its name
        def hash_by_name(path: Path) -> str:
            import hashlib
            return hashlib.md5(path.name.encode()).hexdigest()

        mock_hash.side_effect = hash_by_name

        # Create initial files
        _create_file(tmp_path / "track1.mp3", b"audio1")
        _create_file(tmp_path / "track2.mp3", b"audio2")

        # First scan + analyze
        scanner = AudioScanner(tmp_path)
        files = scanner.scan()
        assert len(files) == 2

        db = Database(":memory:")
        processor = AudioProcessor(database=db)
        result1 = processor.analyze_batch(files)
        assert len(result1.tracks) == 2

        # Now patch compute_file_hash on CacheManager too
        with patch.object(
            AnalysisCacheManager,
            "compute_file_hash",
            side_effect=hash_by_name,
        ):
            # Add a new file
            _create_file(tmp_path / "track3.mp3", b"audio3")

            # Rescan
            files2 = scanner.scan()
            assert len(files2) == 3

            # Filter through cache
            cache = AnalysisCacheManager(db)
            uncached = cache.filter_uncached(files2)

            # Only track3 should need analysis
            assert len(uncached) == 1
            assert uncached[0].name == "track3.mp3"
