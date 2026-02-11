"""Waveform generation for audio playback visualization.

Generates downsampled waveform data (800 points) from audio files
using librosa, cached in the database as BLOBs.
"""

from __future__ import annotations

import logging
import struct
import sqlite3
from pathlib import Path
from uuid import UUID

import numpy as np

logger = logging.getLogger(__name__)

WAVEFORM_SAMPLES = 800  # ~1 sample per pixel at typical panel width


def generate_waveform(file_path: str | Path, sr: int = 22050) -> tuple[list[float], float]:
    """Generate a downsampled waveform from an audio file.

    Args:
        file_path: Path to the audio file.
        sr: Sample rate for loading.

    Returns:
        Tuple of (samples, duration_seconds) where samples is a list
        of WAVEFORM_SAMPLES floats in [0.0, 1.0] representing amplitude.
    """
    import librosa

    y, _ = librosa.load(str(file_path), sr=sr, mono=True)
    duration = len(y) / sr

    if len(y) == 0:
        return [0.0] * WAVEFORM_SAMPLES, 0.0

    # Downsample by taking max absolute amplitude in each chunk
    chunk_size = max(1, len(y) // WAVEFORM_SAMPLES)
    samples = []
    for i in range(WAVEFORM_SAMPLES):
        start = i * chunk_size
        end = min(start + chunk_size, len(y))
        if start >= len(y):
            samples.append(0.0)
        else:
            chunk = np.abs(y[start:end])
            samples.append(float(np.max(chunk)))

    # Normalize to [0, 1]
    max_val = max(samples) if samples else 1.0
    if max_val > 0:
        samples = [s / max_val for s in samples]

    return samples, duration


def samples_to_blob(samples: list[float]) -> bytes:
    """Pack a list of floats into a compact binary BLOB."""
    return struct.pack(f"{len(samples)}f", *samples)


def blob_to_samples(blob: bytes) -> list[float]:
    """Unpack a binary BLOB into a list of floats."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


class WaveformCache:
    """Cache for generated waveform data, stored in SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, track_id: UUID) -> tuple[list[float], float] | None:
        """Retrieve cached waveform data for a track."""
        row = self._conn.execute(
            "SELECT samples, duration FROM waveforms WHERE track_id = ?",
            (str(track_id),),
        ).fetchone()
        if row is None:
            return None
        samples = blob_to_samples(row["samples"])
        return samples, row["duration"]

    def put(self, track_id: UUID, samples: list[float], duration: float) -> None:
        """Store waveform data for a track."""
        blob = samples_to_blob(samples)
        self._conn.execute(
            """
            INSERT OR REPLACE INTO waveforms (track_id, samples, duration)
            VALUES (?, ?, ?)
            """,
            (str(track_id), blob, duration),
        )
        self._conn.commit()

    def has(self, track_id: UUID) -> bool:
        """Check if waveform data exists for a track."""
        row = self._conn.execute(
            "SELECT 1 FROM waveforms WHERE track_id = ?",
            (str(track_id),),
        ).fetchone()
        return row is not None
