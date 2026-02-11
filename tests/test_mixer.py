"""Unit tests for the audio crossfade mixer."""

import math

import numpy as np
import pytest

from rekordbox_creative.analysis.mixer import (
    DEFAULT_CROSSFADE_SECS,
    PREVIEW_SR,
    audio_to_pcm_bytes,
    equal_power_crossfade,
    _resample,
)


class TestEqualPowerCrossfade:
    def test_basic_crossfade(self):
        """Two constant signals should blend smoothly."""
        n = 1000
        a = np.ones(n, dtype=np.float32) * 0.8
        b = np.ones(n, dtype=np.float32) * 0.4
        result = equal_power_crossfade(a, b, 500)
        # before(500) + crossfade(500) + after(500) = 1500
        assert len(result) == 1500

    def test_equal_power_at_midpoint(self):
        """At the midpoint of crossfade, both signals contribute equally."""
        n = 1000
        cf = 1000  # Full overlap
        a = np.ones(n, dtype=np.float32)
        b = np.ones(n, dtype=np.float32)
        result = equal_power_crossfade(a, b, cf)
        # At midpoint, cos(pi/4) = sin(pi/4) = sqrt(2)/2
        # So sum should be sqrt(2)/2 + sqrt(2)/2 ≈ 1.414
        mid = len(result) // 2
        expected = math.cos(math.pi / 4) + math.sin(math.pi / 4)
        assert abs(result[mid] - expected) < 0.05

    def test_start_is_mostly_a(self):
        """Beginning of crossfade should be dominated by track A."""
        n = 2000
        a = np.ones(n, dtype=np.float32)
        b = np.zeros(n, dtype=np.float32)
        result = equal_power_crossfade(a, b, 1000)
        # First sample of crossfade region should be nearly 1.0
        assert result[1000] > 0.95  # a's contribution is cos(0) ≈ 1.0

    def test_end_is_mostly_b(self):
        """End of crossfade should be dominated by track B."""
        n = 2000
        a = np.zeros(n, dtype=np.float32)
        b = np.ones(n, dtype=np.float32)
        result = equal_power_crossfade(a, b, 1000)
        # before=1000, crossfade=1000, after=1000 => total=3000
        # Crossfade region starts at index 1000
        # At start of crossfade: a=0*cos(0)=0, b=1*sin(0)=0 -> ~0
        assert result[1000] < 0.05  # Start of crossfade, mostly A (which is 0)
        # At end of crossfade: a=0*cos(pi/2)=0, b=1*sin(pi/2)=1 -> ~1
        assert result[1999] > 0.95

    def test_zero_crossfade(self):
        """Zero crossfade should just concatenate."""
        a = np.ones(100, dtype=np.float32)
        b = np.zeros(100, dtype=np.float32)
        result = equal_power_crossfade(a, b, 0)
        assert len(result) == 200
        assert result[50] == 1.0
        assert result[150] == 0.0

    def test_crossfade_longer_than_inputs(self):
        """Crossfade is clamped to input length."""
        a = np.ones(50, dtype=np.float32)
        b = np.ones(50, dtype=np.float32)
        result = equal_power_crossfade(a, b, 1000)
        # Should clamp to min(1000, 50, 50) = 50
        assert len(result) == 50  # Only crossfade region, no before/after

    def test_energy_preservation(self):
        """Equal-power crossfade should approximately preserve total energy."""
        n = 10000
        cf = 5000
        a = np.ones(n, dtype=np.float32) * 0.7
        b = np.ones(n, dtype=np.float32) * 0.7
        result = equal_power_crossfade(a, b, cf)
        # before=5000 + crossfade=5000 + after=5000 = 15000
        # Crossfade region starts at index 5000
        cf_region = result[5000:10000]
        rms = np.sqrt(np.mean(cf_region**2))
        # Equal-power crossfade of two identical signals: cos^2 + sin^2 = 1
        # so 0.7 * (cos + sin) peaks around 0.7 * sqrt(2) ≈ 0.99
        assert 0.6 < rms < 1.1


class TestResample:
    def test_same_rate(self):
        y = np.ones(100, dtype=np.float32)
        result = _resample(y, 44100, 44100)
        assert len(result) == 100

    def test_downsample(self):
        y = np.ones(44100, dtype=np.float32)
        result = _resample(y, 44100, 22050)
        assert abs(len(result) - 22050) <= 1

    def test_upsample(self):
        y = np.ones(22050, dtype=np.float32)
        result = _resample(y, 22050, 44100)
        assert abs(len(result) - 44100) <= 1


class TestAudioToPCM:
    def test_basic_conversion(self):
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        pcm = audio_to_pcm_bytes(audio)
        # Each sample is 2 bytes (int16)
        assert len(pcm) == 10

    def test_clipping(self):
        """Values beyond [-1, 1] should be clipped."""
        audio = np.array([2.0, -2.0], dtype=np.float32)
        pcm = audio_to_pcm_bytes(audio)
        assert len(pcm) == 4

    def test_silence(self):
        audio = np.zeros(100, dtype=np.float32)
        pcm = audio_to_pcm_bytes(audio)
        assert len(pcm) == 200
        # All zeros
        assert pcm == b'\x00' * 200
