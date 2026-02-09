"""Shared test fixtures for Rekordbox Creative."""

import pytest

from rekordbox_creative.db.models import (
    DJMetrics,
    SpotifyStyleMetrics,
    Track,
    TrackStructure,
)


@pytest.fixture
def mock_track_a():
    """A 128 BPM, 8A, high-energy four-on-floor track."""
    return Track(
        file_path="/music/track_a.mp3",
        file_hash="abc123",
        filename="track_a.mp3",
        duration_seconds=360.0,
        spotify_style=SpotifyStyleMetrics(
            energy=0.82,
            danceability=0.75,
            acousticness=0.03,
            instrumentalness=0.65,
            valence=0.58,
            liveness=0.12,
        ),
        dj_metrics=DJMetrics(
            bpm=128.0,
            bpm_stability=0.97,
            key="8A",
            key_confidence=0.85,
            mix_in_score=0.90,
            mix_out_score=0.85,
            frequency_weight="bass_heavy",
            groove_type="four_on_floor",
        ),
        structure=TrackStructure(drops=[64.2, 192.5]),
    )


@pytest.fixture
def mock_track_b():
    """A 127 BPM, 9A, medium-energy four-on-floor track — compatible with A."""
    return Track(
        file_path="/music/track_b.mp3",
        file_hash="def456",
        filename="track_b.mp3",
        duration_seconds=340.0,
        spotify_style=SpotifyStyleMetrics(
            energy=0.70,
            danceability=0.72,
            acousticness=0.05,
            instrumentalness=0.80,
            valence=0.50,
            liveness=0.08,
        ),
        dj_metrics=DJMetrics(
            bpm=127.0,
            bpm_stability=0.95,
            key="9A",
            key_confidence=0.90,
            mix_in_score=0.85,
            mix_out_score=0.80,
            frequency_weight="balanced",
            groove_type="four_on_floor",
        ),
        structure=TrackStructure(drops=[60.0, 180.0]),
    )
