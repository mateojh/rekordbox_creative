"""Unit tests for waveform generation and caching."""

import sqlite3
import struct
from uuid import uuid4

import pytest

from rekordbox_creative.analysis.waveform import (
    WAVEFORM_SAMPLES,
    WaveformCache,
    blob_to_samples,
    samples_to_blob,
)


class TestSampleSerialization:
    def test_round_trip(self):
        samples = [0.0, 0.25, 0.5, 0.75, 1.0]
        blob = samples_to_blob(samples)
        result = blob_to_samples(blob)
        assert len(result) == 5
        for a, b in zip(samples, result):
            assert abs(a - b) < 1e-6

    def test_empty_samples(self):
        blob = samples_to_blob([])
        result = blob_to_samples(blob)
        assert result == []

    def test_blob_size(self):
        samples = [0.0] * 800
        blob = samples_to_blob(samples)
        assert len(blob) == 800 * 4  # 4 bytes per float

    def test_many_samples(self):
        samples = [i / WAVEFORM_SAMPLES for i in range(WAVEFORM_SAMPLES)]
        blob = samples_to_blob(samples)
        result = blob_to_samples(blob)
        assert len(result) == WAVEFORM_SAMPLES
        for a, b in zip(samples, result):
            assert abs(a - b) < 1e-6


class TestWaveformCache:
    @pytest.fixture
    def cache(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE waveforms (
                track_id TEXT PRIMARY KEY,
                samples BLOB NOT NULL,
                duration REAL NOT NULL
            )
        """)
        conn.commit()
        return WaveformCache(conn)

    def test_put_and_get(self, cache: WaveformCache):
        track_id = uuid4()
        samples = [0.1, 0.5, 0.9, 0.3]
        cache.put(track_id, samples, 120.5)

        result = cache.get(track_id)
        assert result is not None
        got_samples, duration = result
        assert len(got_samples) == 4
        assert abs(duration - 120.5) < 1e-6
        for a, b in zip(samples, got_samples):
            assert abs(a - b) < 1e-6

    def test_get_missing(self, cache: WaveformCache):
        assert cache.get(uuid4()) is None

    def test_has(self, cache: WaveformCache):
        track_id = uuid4()
        assert cache.has(track_id) is False
        cache.put(track_id, [0.5], 60.0)
        assert cache.has(track_id) is True

    def test_overwrite(self, cache: WaveformCache):
        track_id = uuid4()
        cache.put(track_id, [0.1, 0.2], 60.0)
        cache.put(track_id, [0.9, 0.8, 0.7], 90.0)

        result = cache.get(track_id)
        assert result is not None
        got_samples, duration = result
        assert len(got_samples) == 3
        assert abs(duration - 90.0) < 1e-6

    def test_full_waveform_round_trip(self, cache: WaveformCache):
        track_id = uuid4()
        samples = [i / WAVEFORM_SAMPLES for i in range(WAVEFORM_SAMPLES)]
        cache.put(track_id, samples, 360.0)

        result = cache.get(track_id)
        assert result is not None
        got_samples, _ = result
        assert len(got_samples) == WAVEFORM_SAMPLES
