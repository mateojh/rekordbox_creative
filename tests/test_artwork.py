"""Unit tests for album artwork extraction and thumbnail generation."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rekordbox_creative.analysis.artwork import (
    extract_artwork_bytes,
    generate_thumbnail,
    get_artwork_data_uri,
    batch_extract_artwork,
)


def _make_fake_jpeg(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid JPEG for testing."""
    from PIL import Image

    img = Image.new("RGB", (width, height), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50)
    return buf.getvalue()


class TestExtractArtworkBytes:
    def test_returns_none_for_nonexistent(self, tmp_path):
        result = extract_artwork_bytes(tmp_path / "nope.mp3")
        assert result is None

    def test_returns_none_for_no_art(self, tmp_path):
        """A file with no album art returns None."""
        # Create a minimal file that mutagen can open but has no art
        fake = tmp_path / "noart.mp3"
        fake.write_bytes(b"\x00" * 100)
        result = extract_artwork_bytes(fake)
        assert result is None

    def test_extracts_mp3_apic(self, tmp_path):
        """Extracts APIC frame data from MP3-like tags."""
        mock_audio = MagicMock()
        mock_frame = MagicMock()
        mock_frame.data = _make_fake_jpeg()

        # Simulate ID3 tags with APIC frame
        mock_audio.tags = {"APIC:": mock_frame}
        mock_audio.__iter__ = MagicMock(return_value=iter([]))
        mock_audio.pictures = []

        with patch("rekordbox_creative.analysis.artwork.mutagen.File", return_value=mock_audio):
            result = extract_artwork_bytes(tmp_path / "test.mp3")

        assert result is not None
        assert len(result) > 0

    def test_extracts_flac_pictures(self, tmp_path):
        """Extracts picture data from FLAC."""
        mock_audio = MagicMock()
        # Use a MagicMock for tags so it has no APIC keys
        mock_tags = MagicMock()
        mock_tags.__iter__ = MagicMock(return_value=iter([]))
        mock_audio.tags = mock_tags

        mock_pic = MagicMock()
        mock_pic.data = _make_fake_jpeg()
        mock_audio.pictures = [mock_pic]

        with patch("rekordbox_creative.analysis.artwork.mutagen.File", return_value=mock_audio):
            result = extract_artwork_bytes(tmp_path / "test.flac")

        assert result is not None


class TestGenerateThumbnail:
    def test_basic_thumbnail(self):
        raw = _make_fake_jpeg(500, 500)
        thumb = generate_thumbnail(raw, size=64)
        assert isinstance(thumb, bytes)
        assert len(thumb) > 0

        # Verify it's a valid JPEG
        from PIL import Image

        img = Image.open(io.BytesIO(thumb))
        assert img.size == (64, 64)
        assert img.format == "JPEG"

    def test_non_square_input(self):
        raw = _make_fake_jpeg(300, 200)
        thumb = generate_thumbnail(raw, size=64)

        from PIL import Image

        img = Image.open(io.BytesIO(thumb))
        assert img.size == (64, 64)

    def test_small_input(self):
        """Input smaller than thumbnail size should still produce correct output."""
        raw = _make_fake_jpeg(32, 32)
        thumb = generate_thumbnail(raw, size=64)

        from PIL import Image

        img = Image.open(io.BytesIO(thumb))
        assert img.size == (64, 64)


class TestGetArtworkDataUri:
    def test_returns_data_uri(self, tmp_path):
        fake_jpeg = _make_fake_jpeg()
        mock_audio = MagicMock()
        mock_frame = MagicMock()
        mock_frame.data = fake_jpeg
        mock_audio.tags = {"APIC:": mock_frame}
        mock_audio.pictures = []

        with patch("rekordbox_creative.analysis.artwork.mutagen.File", return_value=mock_audio):
            uri = get_artwork_data_uri(tmp_path / "test.mp3", "test-id-123")

        assert uri is not None
        assert uri.startswith("data:image/jpeg;base64,")

    def test_returns_none_when_no_art(self, tmp_path):
        with patch("rekordbox_creative.analysis.artwork.mutagen.File", return_value=None):
            uri = get_artwork_data_uri(tmp_path / "test.mp3", "test-id-456")
        assert uri is None


class TestBatchExtract:
    def test_batch_returns_dict(self, tmp_path):
        fake_jpeg = _make_fake_jpeg()
        mock_audio = MagicMock()
        mock_frame = MagicMock()
        mock_frame.data = fake_jpeg
        mock_audio.tags = {"APIC:": mock_frame}
        mock_audio.pictures = []

        with patch("rekordbox_creative.analysis.artwork.mutagen.File", return_value=mock_audio):
            result = batch_extract_artwork([
                (str(tmp_path / "a.mp3"), "id-a"),
                (str(tmp_path / "b.mp3"), "id-b"),
            ])

        assert isinstance(result, dict)
        assert "id-a" in result
        assert "id-b" in result
        assert result["id-a"].startswith("data:image/jpeg;base64,")
