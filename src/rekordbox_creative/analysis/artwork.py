"""Album artwork extraction and thumbnail generation."""

from __future__ import annotations

import hashlib
import io
import logging
import tempfile
from pathlib import Path

import mutagen
from PIL import Image

logger = logging.getLogger(__name__)

THUMB_SIZE = 240  # px, square thumbnail (matches Pioneer/Rekordbox export)


def _get_cache_dir() -> Path:
    """Return a persistent artwork cache directory."""
    cache = Path(tempfile.gettempdir()) / "rekordbox_creative_artwork"
    cache.mkdir(exist_ok=True)
    return cache


def extract_artwork_bytes(file_path: Path | str) -> bytes | None:
    """Extract raw album artwork bytes from an audio file.

    Supports MP3 (ID3 APIC), FLAC, MP4/M4A, and Ogg Vorbis.
    Returns JPEG/PNG bytes or None.
    """
    file_path = Path(file_path)
    try:
        audio = mutagen.File(str(file_path))
        if audio is None:
            return None

        # FLAC — pictures list (check first, most reliable for FLAC)
        if hasattr(audio, "pictures"):
            for pic in audio.pictures:
                if pic.data:
                    return pic.data

        # MP3 — ID3 APIC frames
        if hasattr(audio, "tags") and audio.tags is not None:
            try:
                for key in audio.tags:
                    if isinstance(key, str) and key.startswith("APIC"):
                        frame = audio.tags[key]
                        if hasattr(frame, "data") and frame.data:
                            return frame.data
            except (TypeError, AttributeError):
                pass

        # MP4/M4A — covr atom
        if hasattr(audio, "tags") and audio.tags is not None:
            try:
                covr = audio.tags.get("covr")
                if covr and len(covr) > 0:
                    return bytes(covr[0])
            except (TypeError, AttributeError):
                pass

        # FLAC/Ogg VorbisComment — metadata_block_picture
        if hasattr(audio, "tags") and audio.tags is not None:
            try:
                import base64
                pics = audio.tags.get("metadata_block_picture")
                if pics:
                    from mutagen.flac import Picture
                    pic = Picture(base64.b64decode(pics[0]))
                    if pic.data:
                        return pic.data
            except Exception:
                pass

    except Exception as exc:
        logger.debug("Artwork extraction failed for %s: %s", file_path, exc)

    return None


def generate_thumbnail(raw_bytes: bytes, size: int = THUMB_SIZE) -> bytes:
    """Resize raw image bytes to a square JPEG thumbnail."""
    img = Image.open(io.BytesIO(raw_bytes))
    img = img.convert("RGB")
    img.thumbnail((size, size), Image.Resampling.LANCZOS)

    # Pad to exact square if needed
    if img.size != (size, size):
        square = Image.new("RGB", (size, size), (13, 17, 23))
        offset = ((size - img.size[0]) // 2, (size - img.size[1]) // 2)
        square.paste(img, offset)
        img = square

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def get_artwork_path(file_path: Path | str, track_id: str) -> Path | None:
    """Extract artwork, generate thumbnail, cache to disk, return path.

    Returns the path to the cached thumbnail JPEG, or None if no artwork.
    """
    cache_dir = _get_cache_dir()
    thumb_path = cache_dir / f"{track_id}.jpg"

    # Return cached if exists
    if thumb_path.exists():
        return thumb_path

    raw = extract_artwork_bytes(file_path)
    if raw is None:
        return None

    try:
        thumb = generate_thumbnail(raw)
        thumb_path.write_bytes(thumb)
        return thumb_path
    except Exception as exc:
        logger.debug("Thumbnail generation failed for %s: %s", file_path, exc)
        return None


def get_artwork_data_uri(file_path: Path | str, track_id: str) -> str | None:
    """Extract artwork and return as a base64 data URI for embedding in HTML."""
    import base64

    thumb_path = get_artwork_path(file_path, track_id)
    if thumb_path is None:
        return None

    raw = thumb_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def batch_extract_artwork(
    tracks: list[tuple[str, str]],
) -> dict[str, str]:
    """Extract artwork for multiple tracks.

    Args:
        tracks: list of (file_path, track_id) tuples

    Returns:
        dict mapping track_id to data URI string
    """
    result: dict[str, str] = {}
    for file_path, track_id in tracks:
        uri = get_artwork_data_uri(file_path, track_id)
        if uri:
            result[track_id] = uri
    return result
