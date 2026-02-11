"""Unit tests for the smart set generator."""

import pytest

from rekordbox_creative.db.models import (
    DJMetrics,
    EnergyProfile,
    SetBuilderConfig,
    SpotifyStyleMetrics,
    Track,
    TrackStructure,
)
from rekordbox_creative.suggestions.set_generator import (
    SetGenerator,
    _camelot_distance,
    _interpolate_energy,
    ENERGY_CURVES,
)


def _make_track(bpm: float, key: str, energy: float, duration: float = 300.0) -> Track:
    """Create a minimal track for testing."""
    return Track(
        file_path=f"/music/{bpm}_{key}_{energy}.mp3",
        file_hash=f"hash_{bpm}_{key}_{energy}",
        filename=f"{bpm}_{key}_{energy}.mp3",
        duration_seconds=duration,
        spotify_style=SpotifyStyleMetrics(
            energy=energy, danceability=0.7, acousticness=0.1,
            instrumentalness=0.6, valence=0.5, liveness=0.1,
        ),
        dj_metrics=DJMetrics(
            bpm=bpm, bpm_stability=0.95, key=key, key_confidence=0.9,
            mix_in_score=0.8, mix_out_score=0.8,
            frequency_weight="balanced", groove_type="four_on_floor",
        ),
        structure=TrackStructure(),
    )


class TestCamelotDistance:
    def test_same_key(self):
        assert _camelot_distance("8A", "8A") == 0

    def test_adjacent(self):
        assert _camelot_distance("8A", "9A") == 1
        assert _camelot_distance("8A", "7A") == 1

    def test_wrapping(self):
        assert _camelot_distance("12A", "1A") == 1
        assert _camelot_distance("1A", "12A") == 1

    def test_parallel(self):
        assert _camelot_distance("8A", "8B") == 1

    def test_two_steps(self):
        assert _camelot_distance("8A", "10A") == 2

    def test_distant(self):
        assert _camelot_distance("8A", "2A") == 6


class TestInterpolateEnergy:
    def test_at_start(self):
        curve = [(0.0, 0.4), (1.0, 0.9)]
        assert abs(_interpolate_energy(curve, 0.0) - 0.4) < 1e-6

    def test_at_end(self):
        curve = [(0.0, 0.4), (1.0, 0.9)]
        assert abs(_interpolate_energy(curve, 1.0) - 0.9) < 1e-6

    def test_midpoint(self):
        curve = [(0.0, 0.4), (1.0, 0.8)]
        assert abs(_interpolate_energy(curve, 0.5) - 0.6) < 1e-6

    def test_before_start(self):
        curve = [(0.2, 0.5), (1.0, 0.9)]
        assert abs(_interpolate_energy(curve, 0.0) - 0.5) < 1e-6

    def test_after_end(self):
        curve = [(0.0, 0.4), (0.8, 0.9)]
        assert abs(_interpolate_energy(curve, 1.0) - 0.9) < 1e-6

    def test_empty_curve(self):
        assert abs(_interpolate_energy([], 0.5) - 0.5) < 1e-6

    def test_multi_segment(self):
        curve = [(0.0, 0.4), (0.5, 0.9), (1.0, 0.5)]
        # At 0.25 should be between 0.4 and 0.9
        val = _interpolate_energy(curve, 0.25)
        assert 0.5 < val < 0.8


class TestSetGenerator:
    @pytest.fixture
    def tracks(self):
        """Create a pool of 15 tracks with varying energy/BPM/key."""
        return [
            _make_track(128.0, "8A", 0.3, 300),
            _make_track(128.0, "8A", 0.5, 300),
            _make_track(128.0, "9A", 0.6, 300),
            _make_track(128.0, "9A", 0.7, 300),
            _make_track(130.0, "8B", 0.75, 300),
            _make_track(130.0, "8A", 0.8, 300),
            _make_track(130.0, "9A", 0.85, 300),
            _make_track(132.0, "10A", 0.9, 300),
            _make_track(126.0, "7A", 0.4, 300),
            _make_track(126.0, "7A", 0.55, 300),
            _make_track(125.0, "6A", 0.35, 300),
            _make_track(132.0, "10A", 0.45, 300),
            _make_track(128.0, "8A", 0.65, 300),
            _make_track(130.0, "9B", 0.7, 300),
            _make_track(128.0, "8B", 0.5, 300),
        ]

    def test_generates_nonempty_set(self, tracks):
        gen = SetGenerator()
        config = SetBuilderConfig(target_minutes=10)
        result = gen.generate(config, tracks)
        assert len(result) > 0

    def test_respects_target_length(self, tracks):
        gen = SetGenerator()
        config = SetBuilderConfig(target_minutes=10)
        result = gen.generate(config, tracks)
        total = sum(t.duration_seconds for t in result)
        # Should be at least close to target (10 min = 600s)
        # With 300s tracks and 8s overlap, each adds ~292s
        assert total > 400  # At least a few tracks

    def test_no_duplicates(self, tracks):
        gen = SetGenerator()
        config = SetBuilderConfig(target_minutes=30)
        result = gen.generate(config, tracks)
        ids = [t.id for t in result]
        assert len(ids) == len(set(ids))

    def test_respects_start_track(self, tracks):
        gen = SetGenerator()
        start = tracks[5]  # 130 BPM, 8A, 0.8 energy
        config = SetBuilderConfig(
            start_track_id=start.id,
            target_minutes=10,
        )
        result = gen.generate(config, tracks)
        assert len(result) > 0
        assert result[0].id == start.id

    def test_empty_tracks(self):
        gen = SetGenerator()
        config = SetBuilderConfig(target_minutes=60)
        result = gen.generate(config, [])
        assert result == []

    def test_single_track(self):
        gen = SetGenerator()
        track = _make_track(128.0, "8A", 0.7, 300)
        config = SetBuilderConfig(target_minutes=1)
        result = gen.generate(config, [track])
        assert len(result) == 1

    def test_high_energy_profile(self, tracks):
        gen = SetGenerator()
        config = SetBuilderConfig(
            target_minutes=10,
            energy_profile=EnergyProfile.HIGH_ENERGY,
        )
        result = gen.generate(config, tracks)
        assert len(result) > 0
        # High energy profile should favor higher energy tracks
        avg_energy = sum(t.spotify_style.energy for t in result) / len(result)
        assert avg_energy > 0.5  # Should be above moderate

    def test_chill_profile(self, tracks):
        gen = SetGenerator()
        config = SetBuilderConfig(
            target_minutes=10,
            energy_profile=EnergyProfile.CHILL_LOUNGE,
        )
        result = gen.generate(config, tracks)
        assert len(result) > 0

    def test_warm_up_peak_cool(self, tracks):
        gen = SetGenerator()
        config = SetBuilderConfig(
            target_minutes=30,
            energy_profile=EnergyProfile.WARM_UP_PEAK_COOL,
        )
        result = gen.generate(config, tracks)
        assert len(result) >= 3

    def test_all_profiles_valid(self):
        """Verify all energy profiles have valid curve data."""
        for profile in EnergyProfile:
            if profile == EnergyProfile.CUSTOM:
                continue
            assert profile in ENERGY_CURVES
            curve = ENERGY_CURVES[profile]
            assert len(curve) >= 2
            for pos, energy in curve:
                assert 0.0 <= pos <= 1.0
                assert 0.0 <= energy <= 1.0
