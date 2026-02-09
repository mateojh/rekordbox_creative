"""Tests for suggestion engine, strategies, and filters."""

import pytest

from rekordbox_creative.db.models import (
    DJMetrics,
    SpotifyStyleMetrics,
    SuggestionConfig,
    SuggestionStrategy,
    Track,
    TrackStructure,
)
from rekordbox_creative.suggestions.engine import (
    SuggestionEngine,
    diversity_bonus_score,
    sequence_context_modifier,
)
from rekordbox_creative.suggestions.filters import apply_filters
from rekordbox_creative.suggestions.strategies import (
    contrast_modifier,
    discovery_modifier,
    energy_arc_modifier,
    get_strategy_modifier,
    groove_lock_modifier,
    harmonic_flow_modifier,
)


def _make_track(
    bpm=128.0,
    key="8A",
    energy=0.8,
    groove_type="four_on_floor",
    frequency_weight="balanced",
    file_path="/t.mp3",
    cluster_id=None,
    times_used=0,
    mix_in_score=0.85,
    mix_out_score=0.80,
    **kw,
) -> Track:
    return Track(
        file_path=file_path,
        file_hash=kw.get("file_hash", f"hash_{id(bpm)}_{file_path}"),
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
            mix_in_score=mix_in_score,
            mix_out_score=mix_out_score,
            frequency_weight=frequency_weight,
            groove_type=groove_type,
        ),
        structure=TrackStructure(),
        cluster_id=cluster_id,
        times_used=times_used,
    )


@pytest.fixture
def track_pool():
    """A pool of diverse tracks for suggestion testing."""
    return [
        _make_track(bpm=128.0, key="8A", energy=0.8, file_path="/p1.mp3", file_hash="p1",
                     groove_type="four_on_floor", frequency_weight="bass_heavy", cluster_id=0),
        _make_track(bpm=127.0, key="9A", energy=0.75, file_path="/p2.mp3", file_hash="p2",
                     groove_type="four_on_floor", frequency_weight="balanced", cluster_id=0),
        _make_track(bpm=130.0, key="8B", energy=0.85, file_path="/p3.mp3", file_hash="p3",
                     groove_type="four_on_floor", frequency_weight="bass_heavy", cluster_id=0),
        _make_track(bpm=125.0, key="7A", energy=0.7, file_path="/p4.mp3", file_hash="p4",
                     groove_type="breakbeat", frequency_weight="bright", cluster_id=1),
        _make_track(bpm=132.0, key="10A", energy=0.9, file_path="/p5.mp3", file_hash="p5",
                     groove_type="four_on_floor", frequency_weight="balanced", cluster_id=1),
        _make_track(bpm=90.0, key="3A", energy=0.3, file_path="/p6.mp3", file_hash="p6",
                     groove_type="half_time", frequency_weight="mid_focused", cluster_id=2),
        _make_track(bpm=135.0, key="11B", energy=0.95, file_path="/p7.mp3", file_hash="p7",
                     groove_type="syncopated", frequency_weight="bright", cluster_id=2),
        _make_track(bpm=126.0, key="8A", energy=0.78, file_path="/p8.mp3", file_hash="p8",
                     groove_type="four_on_floor", frequency_weight="balanced", cluster_id=0,
                     times_used=0),
        _make_track(bpm=129.0, key="9B", energy=0.82, file_path="/p9.mp3", file_hash="p9",
                     groove_type="four_on_floor", frequency_weight="balanced", cluster_id=1,
                     times_used=5),
        _make_track(bpm=128.5, key="7B", energy=0.77, file_path="/p10.mp3", file_hash="p10",
                     groove_type="straight", frequency_weight="balanced", cluster_id=1,
                     times_used=1),
    ]


@pytest.fixture
def current_track():
    return _make_track(
        bpm=128.0, key="8A", energy=0.8, file_path="/current.mp3", file_hash="current",
        groove_type="four_on_floor", frequency_weight="bass_heavy", cluster_id=0,
    )


# ===========================================================================
# Strategy modifier tests
# ===========================================================================


class TestHarmonicFlowModifier:
    def test_always_returns_one(self, mock_track_a, mock_track_b):
        assert harmonic_flow_modifier(mock_track_a, mock_track_b) == 1.0


class TestEnergyArcModifier:
    def test_early_set_moderate_target(self, mock_track_a, mock_track_b):
        mod = energy_arc_modifier(mock_track_a, mock_track_b, sequence_position=2,
                                  estimated_set_length=20)
        assert 0.5 <= mod <= 1.0

    def test_mid_set_high_target(self, mock_track_a, mock_track_b):
        mod = energy_arc_modifier(mock_track_a, mock_track_b, sequence_position=10,
                                  estimated_set_length=20)
        assert 0.5 <= mod <= 1.0

    def test_late_set_cooldown(self, mock_track_a, mock_track_b):
        mod = energy_arc_modifier(mock_track_a, mock_track_b, sequence_position=18,
                                  estimated_set_length=20)
        assert 0.5 <= mod <= 1.0

    def test_zero_set_length(self, mock_track_a, mock_track_b):
        assert energy_arc_modifier(mock_track_a, mock_track_b, estimated_set_length=0) == 1.0

    def test_returns_float(self, mock_track_a, mock_track_b):
        mod = energy_arc_modifier(mock_track_a, mock_track_b)
        assert isinstance(mod, float)


class TestDiscoveryModifier:
    def test_never_used_gets_boost(self):
        t = _make_track(times_used=0, file_path="/d1.mp3", file_hash="d1")
        assert discovery_modifier(t, t) == 1.3

    def test_rarely_used_gets_smaller_boost(self):
        t = _make_track(times_used=2, file_path="/d2.mp3", file_hash="d2")
        assert discovery_modifier(t, t) == 1.15

    def test_frequently_used_no_boost(self):
        t = _make_track(times_used=5, file_path="/d3.mp3", file_hash="d3")
        assert discovery_modifier(t, t) == 1.0

    def test_boundary_three(self):
        t = _make_track(times_used=3, file_path="/d4.mp3", file_hash="d4")
        assert discovery_modifier(t, t) == 1.0


class TestGrooveLockModifier:
    def test_same_groove_boost(self):
        a = _make_track(groove_type="four_on_floor", file_path="/gl1.mp3", file_hash="gl1")
        b = _make_track(groove_type="four_on_floor", file_path="/gl2.mp3", file_hash="gl2")
        assert groove_lock_modifier(a, b) == 1.2

    def test_different_groove_penalty(self):
        a = _make_track(groove_type="breakbeat", file_path="/gl3.mp3", file_hash="gl3")
        b = _make_track(groove_type="four_on_floor", file_path="/gl4.mp3", file_hash="gl4")
        assert groove_lock_modifier(a, b) == 0.6


class TestContrastModifier:
    def test_high_energy_diff_boost(self):
        a = _make_track(energy=0.9, file_path="/c1.mp3", file_hash="c1")
        b = _make_track(energy=0.3, file_path="/c2.mp3", file_hash="c2")
        mod = contrast_modifier(a, b)
        assert mod >= 1.2

    def test_same_energy_no_boost(self):
        a = _make_track(energy=0.7, file_path="/c3.mp3", file_hash="c3")
        b = _make_track(energy=0.7, file_path="/c4.mp3", file_hash="c4")
        mod = contrast_modifier(a, b)
        assert mod == 1.0 or mod == pytest.approx(1.1)  # freq might differ

    def test_different_frequency_boost(self):
        a = _make_track(frequency_weight="bass_heavy", file_path="/c5.mp3", file_hash="c5")
        b = _make_track(frequency_weight="bright", file_path="/c6.mp3", file_hash="c6")
        mod = contrast_modifier(a, b)
        assert mod >= 1.1

    def test_both_differences(self):
        a = _make_track(energy=0.9, frequency_weight="bass_heavy",
                        file_path="/c7.mp3", file_hash="c7")
        b = _make_track(energy=0.3, frequency_weight="bright",
                        file_path="/c8.mp3", file_hash="c8")
        mod = contrast_modifier(a, b)
        assert mod == pytest.approx(1.2 * 1.1)


class TestGetStrategyModifier:
    def test_harmonic_flow(self):
        fn = get_strategy_modifier(SuggestionStrategy.HARMONIC_FLOW)
        assert fn is harmonic_flow_modifier

    def test_energy_arc(self):
        fn = get_strategy_modifier(SuggestionStrategy.ENERGY_ARC)
        assert fn is energy_arc_modifier

    def test_discovery(self):
        fn = get_strategy_modifier(SuggestionStrategy.DISCOVERY)
        assert fn is discovery_modifier

    def test_groove_lock(self):
        fn = get_strategy_modifier(SuggestionStrategy.GROOVE_LOCK)
        assert fn is groove_lock_modifier

    def test_contrast(self):
        fn = get_strategy_modifier(SuggestionStrategy.CONTRAST)
        assert fn is contrast_modifier


# ===========================================================================
# Filter tests
# ===========================================================================


class TestApplyFilters:
    def test_no_filters_returns_all(self, track_pool, current_track):
        config = SuggestionConfig()
        result = apply_filters(track_pool, current_track, config)
        assert len(result) == len(track_pool)

    def test_bpm_min_filter(self, track_pool, current_track):
        config = SuggestionConfig(bpm_min=126.0)
        result = apply_filters(track_pool, current_track, config)
        assert all(t.dj_metrics.bpm >= 126.0 for t in result)

    def test_bpm_max_filter(self, track_pool, current_track):
        config = SuggestionConfig(bpm_max=130.0)
        result = apply_filters(track_pool, current_track, config)
        assert all(t.dj_metrics.bpm <= 130.0 for t in result)

    def test_bpm_range_filter(self, track_pool, current_track):
        config = SuggestionConfig(bpm_min=125.0, bpm_max=132.0)
        result = apply_filters(track_pool, current_track, config)
        assert all(125.0 <= t.dj_metrics.bpm <= 132.0 for t in result)
        # The 90 BPM track should be filtered out
        assert not any(t.dj_metrics.bpm < 125.0 for t in result)

    def test_key_lock_filter(self, track_pool, current_track):
        config = SuggestionConfig(key_lock=True)
        result = apply_filters(track_pool, current_track, config)
        # All remaining tracks should have harmonic compatibility >= 0.4 with 8A
        assert len(result) < len(track_pool)

    def test_groove_lock_filter(self, track_pool, current_track):
        config = SuggestionConfig(groove_lock=True)
        result = apply_filters(track_pool, current_track, config)
        assert all(t.dj_metrics.groove_type == "four_on_floor" for t in result)

    def test_exclude_cluster_ids(self, track_pool, current_track):
        config = SuggestionConfig(exclude_cluster_ids=[2])
        result = apply_filters(track_pool, current_track, config)
        assert not any(t.cluster_id == 2 for t in result)

    def test_combined_filters(self, track_pool, current_track):
        config = SuggestionConfig(bpm_min=125.0, bpm_max=135.0, groove_lock=True)
        result = apply_filters(track_pool, current_track, config)
        for t in result:
            assert 125.0 <= t.dj_metrics.bpm <= 135.0
            assert t.dj_metrics.groove_type == "four_on_floor"


# ===========================================================================
# Context modifier tests
# ===========================================================================


class TestSequenceContextModifier:
    def test_no_history(self):
        t = _make_track(file_path="/scm.mp3", file_hash="scm")
        assert sequence_context_modifier(t, []) == 1.0

    def test_same_key_penalty(self):
        recent = [
            _make_track(key="8A", file_path="/r1.mp3", file_hash="r1"),
            _make_track(key="8A", file_path="/r2.mp3", file_hash="r2"),
        ]
        candidate = _make_track(key="8A", file_path="/cand.mp3", file_hash="cand")
        mod = sequence_context_modifier(candidate, recent)
        assert mod < 1.0
        assert mod == pytest.approx(0.8)

    def test_different_key_no_penalty(self):
        recent = [
            _make_track(key="9A", file_path="/r3.mp3", file_hash="r3"),
            _make_track(key="10A", file_path="/r4.mp3", file_hash="r4"),
        ]
        candidate = _make_track(key="8A", file_path="/cand2.mp3", file_hash="cand2")
        mod = sequence_context_modifier(candidate, recent)
        assert mod >= 0.85  # cluster might match

    def test_same_cluster_penalty(self):
        recent = [
            _make_track(cluster_id=1, file_path="/rc1.mp3", file_hash="rc1"),
            _make_track(cluster_id=1, file_path="/rc2.mp3", file_hash="rc2"),
            _make_track(cluster_id=1, file_path="/rc3.mp3", file_hash="rc3"),
        ]
        candidate = _make_track(
            key="9A", cluster_id=1, file_path="/candc.mp3", file_hash="candc"
        )
        mod = sequence_context_modifier(candidate, recent)
        assert mod < 1.0

    def test_same_groove_4_tracks_penalty(self):
        recent = [
            _make_track(groove_type="four_on_floor", key=f"{i}A",
                        file_path=f"/rg{i}.mp3", file_hash=f"rg{i}")
            for i in range(1, 5)
        ]
        candidate = _make_track(
            groove_type="four_on_floor", key="6A",
            file_path="/candg.mp3", file_hash="candg",
        )
        mod = sequence_context_modifier(candidate, recent)
        assert mod <= 0.9


# ===========================================================================
# Diversity bonus tests
# ===========================================================================


class TestDiversityBonus:
    def test_no_history(self):
        t = _make_track(file_path="/db1.mp3", file_hash="db1")
        assert diversity_bonus_score(t, []) == 0.0

    def test_different_cluster_gets_bonus(self):
        recent = [_make_track(cluster_id=0, file_path=f"/dbr{i}.mp3", file_hash=f"dbr{i}")
                  for i in range(3)]
        candidate = _make_track(cluster_id=1, file_path="/dbc.mp3", file_hash="dbc")
        bonus = diversity_bonus_score(candidate, recent, bonus=0.1)
        assert bonus == pytest.approx(0.1)

    def test_same_cluster_no_bonus(self):
        recent = [_make_track(cluster_id=0, file_path=f"/dbs{i}.mp3", file_hash=f"dbs{i}")
                  for i in range(3)]
        candidate = _make_track(cluster_id=0, file_path="/dbsc.mp3", file_hash="dbsc")
        bonus = diversity_bonus_score(candidate, recent, bonus=0.1)
        assert bonus == 0.0

    def test_none_cluster_no_bonus(self):
        recent = [_make_track(cluster_id=0, file_path=f"/dbn{i}.mp3", file_hash=f"dbn{i}")
                  for i in range(3)]
        candidate = _make_track(cluster_id=None, file_path="/dbnc.mp3", file_hash="dbnc")
        bonus = diversity_bonus_score(candidate, recent, bonus=0.1)
        assert bonus == 0.0

    def test_zero_bonus_disabled(self):
        recent = [_make_track(cluster_id=0, file_path=f"/dbz{i}.mp3", file_hash=f"dbz{i}")
                  for i in range(3)]
        candidate = _make_track(cluster_id=1, file_path="/dbzc.mp3", file_hash="dbzc")
        assert diversity_bonus_score(candidate, recent, bonus=0.0) == 0.0


# ===========================================================================
# SuggestionEngine tests
# ===========================================================================


class TestSuggestionEngine:
    def test_basic_suggestions(self, track_pool, current_track):
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track)
        assert len(results) > 0
        assert len(results) <= 8  # default num_suggestions

    def test_suggestions_sorted_descending(self, track_pool, current_track):
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track)
        scores = [r.final_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_current_track_excluded(self, track_pool, current_track):
        engine = SuggestionEngine(track_pool + [current_track])
        results = engine.suggest(current_track)
        assert not any(r.track_id == current_track.id for r in results)

    def test_sequence_tracks_excluded(self, track_pool, current_track):
        engine = SuggestionEngine(track_pool)
        sequence = [track_pool[0], track_pool[1]]
        results = engine.suggest(current_track, sequence=sequence)
        seq_ids = {t.id for t in sequence}
        assert not any(r.track_id in seq_ids for r in results)

    def test_num_suggestions_respected(self, track_pool, current_track):
        config = SuggestionConfig(num_suggestions=3)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert len(results) <= 3

    def test_result_fields(self, track_pool, current_track):
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track)
        for r in results:
            assert r.final_score > 0
            assert r.base_compatibility >= 0
            assert r.strategy_modifier > 0
            assert r.context_modifier > 0
            assert r.diversity_bonus >= 0
            assert r.score_breakdown is not None

    def test_empty_pool(self, current_track):
        engine = SuggestionEngine([])
        results = engine.suggest(current_track)
        assert results == []

    def test_all_filtered_out(self, track_pool, current_track):
        config = SuggestionConfig(bpm_min=200.0, bpm_max=250.0)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert results == []

    def test_energy_arc_strategy(self, track_pool, current_track):
        config = SuggestionConfig(strategy=SuggestionStrategy.ENERGY_ARC)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert len(results) > 0

    def test_discovery_strategy(self, track_pool, current_track):
        config = SuggestionConfig(strategy=SuggestionStrategy.DISCOVERY)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert len(results) > 0

    def test_groove_lock_strategy(self, track_pool, current_track):
        config = SuggestionConfig(strategy=SuggestionStrategy.GROOVE_LOCK)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert len(results) > 0

    def test_contrast_strategy(self, track_pool, current_track):
        config = SuggestionConfig(strategy=SuggestionStrategy.CONTRAST)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert len(results) > 0

    def test_custom_weights(self, track_pool, current_track):
        config = SuggestionConfig(harmonic_weight=0.5, bpm_weight=0.1)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert len(results) > 0

    def test_set_tracks(self, track_pool, current_track):
        engine = SuggestionEngine()
        engine.set_tracks(track_pool)
        results = engine.suggest(current_track)
        assert len(results) > 0

    def test_sequence_aware_suggestions(self, track_pool, current_track):
        """Suggestions should change when sequence grows."""
        engine = SuggestionEngine(track_pool)
        engine.suggest(current_track)
        results_with_seq = engine.suggest(current_track, sequence=track_pool[:3])
        # With sequence, some tracks are excluded
        with_seq_ids = {r.track_id for r in results_with_seq}
        # The excluded tracks should not appear
        for t in track_pool[:3]:
            assert t.id not in with_seq_ids

    def test_bpm_filter_in_suggestions(self, track_pool, current_track):
        config = SuggestionConfig(bpm_min=125.0, bpm_max=130.0)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        # All suggested tracks should be in BPM range
        result_ids = {r.track_id for r in results}
        for t in track_pool:
            if t.id in result_ids:
                assert 125.0 <= t.dj_metrics.bpm <= 130.0

    def test_key_lock_in_suggestions(self, track_pool, current_track):
        config = SuggestionConfig(key_lock=True)
        engine = SuggestionEngine(track_pool)
        results = engine.suggest(current_track, config=config)
        assert len(results) > 0  # Some tracks should be compatible with 8A
