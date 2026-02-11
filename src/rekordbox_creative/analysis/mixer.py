"""Audio crossfade generation for transition previews.

Creates a blended preview clip from two tracks using equal-power crossfade,
with optional BPM time-stretching for smooth tempo alignment.
"""

from __future__ import annotations

import logging
import math
import struct

import numpy as np

logger = logging.getLogger(__name__)

# Default crossfade length in seconds (~16 beats at 128 BPM)
DEFAULT_CROSSFADE_SECS = 8.0
# Preview clip duration in seconds (before + crossfade + after)
DEFAULT_PREVIEW_SECS = 30.0
# Sample rate for preview audio
PREVIEW_SR = 44100


def equal_power_crossfade(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    crossfade_samples: int,
) -> np.ndarray:
    """Apply equal-power crossfade between two audio arrays.

    Args:
        audio_a: Tail of first track (mono float32).
        audio_b: Head of second track (mono float32).
        crossfade_samples: Number of samples in the crossfade region.

    Returns:
        Blended audio array.
    """
    cf_len = min(crossfade_samples, len(audio_a), len(audio_b))
    if cf_len <= 0:
        return np.concatenate([audio_a, audio_b])

    # Portions before and after crossfade
    before = audio_a[:-cf_len] if len(audio_a) > cf_len else np.array([], dtype=np.float32)
    after = audio_b[cf_len:] if len(audio_b) > cf_len else np.array([], dtype=np.float32)

    # Equal-power curves
    t = np.linspace(0, 1, cf_len, dtype=np.float32)
    fade_out = np.cos(t * math.pi / 2)
    fade_in = np.sin(t * math.pi / 2)

    crossfade_region = audio_a[-cf_len:] * fade_out + audio_b[:cf_len] * fade_in

    return np.concatenate([before, crossfade_region, after])


def generate_crossfade_preview(
    file_a: str,
    file_b: str,
    mix_point_a: float | None = None,
    mix_point_b: float | None = None,
    crossfade_secs: float = DEFAULT_CROSSFADE_SECS,
    preview_secs: float = DEFAULT_PREVIEW_SECS,
    bpm_a: float | None = None,
    bpm_b: float | None = None,
) -> tuple[np.ndarray, int]:
    """Generate a crossfade preview clip from two audio files.

    Args:
        file_a: Path to the first (outgoing) track.
        file_b: Path to the second (incoming) track.
        mix_point_a: Start of fade-out in track A (seconds from start).
            Defaults to outro_start or last 15s.
        mix_point_b: Start point in track B to begin fade-in (seconds).
            Defaults to intro_end or start.
        crossfade_secs: Duration of crossfade in seconds.
        preview_secs: Total preview clip duration.
        bpm_a: BPM of track A (for tempo matching).
        bpm_b: BPM of track B (for tempo matching).

    Returns:
        (audio_array, sample_rate) — mono float32 numpy array and SR.
    """
    import soundfile as sf

    # Load audio
    y_a, sr_a = sf.read(file_a, dtype="float32", always_2d=False)
    y_b, sr_b = sf.read(file_b, dtype="float32", always_2d=False)

    # Convert stereo to mono if needed
    if y_a.ndim > 1:
        y_a = y_a.mean(axis=1)
    if y_b.ndim > 1:
        y_b = y_b.mean(axis=1)

    # Resample to common rate if needed
    target_sr = PREVIEW_SR
    if sr_a != target_sr:
        y_a = _resample(y_a, sr_a, target_sr)
    if sr_b != target_sr:
        y_b = _resample(y_b, sr_b, target_sr)

    # BPM time-stretch if needed (only if < 8% difference)
    if bpm_a and bpm_b and bpm_a > 0 and bpm_b > 0:
        ratio = bpm_a / bpm_b
        if 0.92 < ratio < 1.08 and abs(ratio - 1.0) > 0.005:
            try:
                import librosa
                y_b = librosa.effects.time_stretch(y_b, rate=ratio)
            except Exception:
                logger.debug("Time stretch skipped: librosa unavailable or failed")

    # Determine mix points
    half_preview = preview_secs / 2
    duration_a = len(y_a) / target_sr
    duration_b = len(y_b) / target_sr

    if mix_point_a is None:
        mix_point_a = max(0, duration_a - half_preview)
    if mix_point_b is None:
        mix_point_b = 0.0

    # Extract preview segments
    start_a = int(max(0, mix_point_a - (half_preview - crossfade_secs / 2)) * target_sr)
    end_a = int(min(len(y_a), (mix_point_a + crossfade_secs) * target_sr))
    segment_a = y_a[start_a:end_a]

    start_b = int(mix_point_b * target_sr)
    end_b = int(min(len(y_b), (mix_point_b + half_preview + crossfade_secs / 2) * target_sr))
    segment_b = y_b[start_b:end_b]

    # Apply crossfade
    cf_samples = int(crossfade_secs * target_sr)
    result = equal_power_crossfade(segment_a, segment_b, cf_samples)

    # Normalize
    peak = np.abs(result).max()
    if peak > 0:
        result = result * (0.9 / peak)

    return result, target_sr


def audio_to_pcm_bytes(audio: np.ndarray, sample_rate: int = PREVIEW_SR) -> bytes:
    """Convert float32 audio array to 16-bit PCM bytes for QAudioSink."""
    # Clip to [-1, 1] and convert to int16
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    return pcm.tobytes()


def _resample(y: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Simple linear interpolation resample."""
    if orig_sr == target_sr:
        return y
    ratio = target_sr / orig_sr
    new_len = int(len(y) * ratio)
    indices = np.linspace(0, len(y) - 1, new_len)
    return np.interp(indices, np.arange(len(y)), y).astype(np.float32)
