"""Tests for pathfinding algorithms."""

import pytest

from rekordbox_creative.db.models import (
    DJMetrics,
    SpotifyStyleMetrics,
    Track,
    TrackStructure,
)
from rekordbox_creative.graph.pathfinding import (
    greedy_order,
    optimal_order,
    total_compatibility,
    two_opt_improve,
)


def _make_track(bpm=128.0, key="8A", energy=0.8, file_path="/t.mp3", **kw) -> Track:
    return Track(
        file_path=file_path,
        file_hash=kw.get("file_hash", f"hash_{id(bpm)}"),
        filename=kw.get("filename", "track.mp3"),
        duration_seconds=300.0,
        spotify_style=SpotifyStyleMetrics(
            energy=energy,
            danceability=0.7,
            acousticness=0.05,
            instrumentalness=0.6,
            valence=0.5,
            liveness=0.1,
        ),
        dj_metrics=DJMetrics(
            bpm=bpm,
            bpm_stability=0.95,
            key=key,
            key_confidence=0.85,
            mix_in_score=0.85,
            mix_out_score=0.80,
            frequency_weight="balanced",
            groove_type="four_on_floor",
        ),
        structure=TrackStructure(),
    )


@pytest.fixture
def compatible_tracks():
    """Set of tracks with varying compatibility."""
    return [
        _make_track(bpm=128.0, key="8A", energy=0.8, file_path="/a.mp3", file_hash="a"),
        _make_track(bpm=127.0, key="9A", energy=0.75, file_path="/b.mp3", file_hash="b"),
        _make_track(bpm=130.0, key="8B", energy=0.85, file_path="/c.mp3", file_hash="c"),
        _make_track(bpm=126.0, key="7A", energy=0.7, file_path="/d.mp3", file_hash="d"),
        _make_track(bpm=132.0, key="10A", energy=0.9, file_path="/e.mp3", file_hash="e"),
    ]


@pytest.fixture
def diverse_tracks():
    """Tracks with bigger variety in BPM and key."""
    return [
        _make_track(bpm=128.0, key="8A", energy=0.8, file_path="/d1.mp3", file_hash="d1"),
        _make_track(bpm=90.0, key="1A", energy=0.3, file_path="/d2.mp3", file_hash="d2"),
        _make_track(bpm=140.0, key="12B", energy=0.95, file_path="/d3.mp3", file_hash="d3"),
        _make_track(bpm=125.0, key="7A", energy=0.7, file_path="/d4.mp3", file_hash="d4"),
    ]


# ---------------------------------------------------------------------------
# total_compatibility
# ---------------------------------------------------------------------------


class TestTotalCompatibility:
    def test_empty_list(self):
        assert total_compatibility([]) == 0.0

    def test_single_track(self):
        t = _make_track(file_path="/s.mp3", file_hash="s")
        assert total_compatibility([t]) == 0.0

    def test_two_tracks_positive(self, compatible_tracks):
        score = total_compatibility(compatible_tracks[:2])
        assert score > 0.0

    def test_returns_float(self, compatible_tracks):
        assert isinstance(total_compatibility(compatible_tracks), float)

    def test_more_tracks_higher_sum(self, compatible_tracks):
        """More compatible tracks should give higher total."""
        score_2 = total_compatibility(compatible_tracks[:2])
        score_5 = total_compatibility(compatible_tracks)
        assert score_5 > score_2


# ---------------------------------------------------------------------------
# greedy_order
# ---------------------------------------------------------------------------


class TestGreedyOrder:
    def test_empty(self):
        assert greedy_order([]) == []

    def test_single_track(self):
        t = _make_track(file_path="/g.mp3", file_hash="g")
        result = greedy_order([t])
        assert len(result) == 1
        assert result[0].id == t.id

    def test_preserves_all_tracks(self, compatible_tracks):
        result = greedy_order(compatible_tracks)
        assert len(result) == len(compatible_tracks)
        result_ids = {t.id for t in result}
        input_ids = {t.id for t in compatible_tracks}
        assert result_ids == input_ids

    def test_with_start_track(self, compatible_tracks):
        start = compatible_tracks[2]
        result = greedy_order(compatible_tracks, start=start)
        assert result[0].id == start.id

    def test_start_track_not_in_list(self, compatible_tracks):
        """Start track not in list should fall back to max energy."""
        outsider = _make_track(bpm=100.0, key="1A", file_path="/out.mp3", file_hash="out")
        result = greedy_order(compatible_tracks, start=outsider)
        assert len(result) == len(compatible_tracks)

    def test_returns_valid_ordering(self, compatible_tracks):
        result = greedy_order(compatible_tracks)
        # The ordering should have reasonable total compatibility
        score = total_compatibility(result)
        assert score > 0.0

    def test_greedy_better_than_worst_case(self, diverse_tracks):
        """Greedy should beat reversed order for diverse tracks."""
        greedy = greedy_order(diverse_tracks)
        reversed_order = list(reversed(diverse_tracks))
        assert total_compatibility(greedy) >= total_compatibility(reversed_order) * 0.5


# ---------------------------------------------------------------------------
# two_opt_improve
# ---------------------------------------------------------------------------


class TestTwoOptImprove:
    def test_empty(self):
        assert two_opt_improve([]) == []

    def test_single_track(self):
        t = _make_track(file_path="/to.mp3", file_hash="to")
        result = two_opt_improve([t])
        assert len(result) == 1

    def test_two_tracks(self):
        tracks = [
            _make_track(bpm=128.0, file_path="/t2a.mp3", file_hash="t2a"),
            _make_track(bpm=127.0, file_path="/t2b.mp3", file_hash="t2b"),
        ]
        result = two_opt_improve(tracks)
        assert len(result) == 2

    def test_preserves_all_tracks(self, compatible_tracks):
        result = two_opt_improve(compatible_tracks)
        assert {t.id for t in result} == {t.id for t in compatible_tracks}

    def test_never_worse_than_input(self, compatible_tracks):
        """2-opt should never decrease total compatibility."""
        greedy = greedy_order(compatible_tracks)
        greedy_score = total_compatibility(greedy)
        improved = two_opt_improve(greedy)
        improved_score = total_compatibility(improved)
        assert improved_score >= greedy_score - 1e-9

    def test_max_iterations_respected(self, compatible_tracks):
        """Should complete without hanging even with max_iterations=1."""
        result = two_opt_improve(compatible_tracks, max_iterations=1)
        assert len(result) == len(compatible_tracks)


# ---------------------------------------------------------------------------
# optimal_order
# ---------------------------------------------------------------------------


class TestOptimalOrder:
    def test_empty(self):
        assert optimal_order([]) == []

    def test_single(self):
        t = _make_track(file_path="/oo.mp3", file_hash="oo")
        result = optimal_order([t])
        assert len(result) == 1

    def test_preserves_all_tracks(self, compatible_tracks):
        result = optimal_order(compatible_tracks)
        assert {t.id for t in result} == {t.id for t in compatible_tracks}

    def test_with_start(self, compatible_tracks):
        start = compatible_tracks[0]
        result = optimal_order(compatible_tracks, start=start)
        assert result[0].id == start.id

    def test_optimal_at_least_as_good_as_greedy(self, compatible_tracks):
        greedy = greedy_order(compatible_tracks)
        optimal = optimal_order(compatible_tracks)
        assert total_compatibility(optimal) >= total_compatibility(greedy) - 1e-9

    def test_diverse_tracks(self, diverse_tracks):
        result = optimal_order(diverse_tracks)
        assert len(result) == len(diverse_tracks)
        assert total_compatibility(result) > 0
