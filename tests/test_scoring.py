"""Tests for compatibility scoring functions.

Exhaustive tests for all 6 sub-scores plus the aggregate compute_compatibility.
Covers edge cases: Camelot wrapping, half/double BPM, key confidence, BPM stability,
symmetric lookup tables, directional mix quality, and custom weight configs.
"""

import pytest

from rekordbox_creative.db.models import (
    DJMetrics,
    SpotifyStyleMetrics,
    SuggestionConfig,
    Track,
    TrackStructure,
)
from rekordbox_creative.graph.scoring import (
    bpm_score,
    camelot_distance,
    compute_compatibility,
    energy_score,
    frequency_score,
    groove_score,
    harmonic_score,
    mix_quality_score,
    parse_camelot,
)

# ===================================================================
# Helpers: parse_camelot and camelot_distance
# ===================================================================


class TestParseCamelot:
    """Tests for parse_camelot utility."""

    def test_parse_single_digit_minor(self):
        assert parse_camelot("8A") == (8, "A")

    def test_parse_single_digit_major(self):
        assert parse_camelot("5B") == (5, "B")

    def test_parse_double_digit_minor(self):
        assert parse_camelot("12A") == (12, "A")

    def test_parse_double_digit_major(self):
        assert parse_camelot("10B") == (10, "B")

    def test_parse_one(self):
        assert parse_camelot("1A") == (1, "A")

    def test_parse_one_major(self):
        assert parse_camelot("1B") == (1, "B")


class TestCamelotDistance:
    """Tests for circular Camelot wheel distance."""

    def test_same_position(self):
        assert camelot_distance(8, 8) == 0

    def test_adjacent(self):
        assert camelot_distance(8, 9) == 1

    def test_adjacent_reverse(self):
        assert camelot_distance(9, 8) == 1

    def test_two_steps(self):
        assert camelot_distance(8, 10) == 2

    def test_wrap_12_to_1(self):
        """12 -> 1 should be distance 1, not 11."""
        assert camelot_distance(12, 1) == 1

    def test_wrap_1_to_12(self):
        """1 -> 12 should be distance 1, not 11."""
        assert camelot_distance(1, 12) == 1

    def test_wrap_11_to_1(self):
        """11 -> 1 should be distance 2 (wrapping through 12)."""
        assert camelot_distance(11, 1) == 2

    def test_wrap_12_to_2(self):
        """12 -> 2 should be distance 2."""
        assert camelot_distance(12, 2) == 2

    def test_half_circle(self):
        """Maximum distance on the 12-position wheel is 6."""
        assert camelot_distance(1, 7) == 6

    def test_opposite_sides(self):
        assert camelot_distance(3, 9) == 6

    def test_five_steps(self):
        assert camelot_distance(1, 6) == 5

    def test_wrap_far_apart(self):
        """10 -> 3: clockwise=5, counter=7. Min is 5."""
        assert camelot_distance(10, 3) == 5


# ===================================================================
# 1. Harmonic score tests
# ===================================================================


class TestHarmonicScore:
    """Tests for Camelot wheel harmonic compatibility."""

    # Same key
    def test_same_key_8a(self):
        assert harmonic_score("8A", "8A") == 1.0

    def test_same_key_5b(self):
        assert harmonic_score("5B", "5B") == 1.0

    def test_same_key_12a(self):
        assert harmonic_score("12A", "12A") == 1.0

    def test_same_key_1b(self):
        assert harmonic_score("1B", "1B") == 1.0

    # Adjacent key (same mode, distance 1)
    def test_adjacent_up(self):
        assert harmonic_score("8A", "9A") == 0.85

    def test_adjacent_down(self):
        assert harmonic_score("8A", "7A") == 0.85

    def test_adjacent_b_mode(self):
        assert harmonic_score("5B", "6B") == 0.85

    def test_adjacent_b_mode_down(self):
        assert harmonic_score("5B", "4B") == 0.85

    # Wrapping adjacent (CRITICAL)
    def test_wrap_adjacent_12a_to_1a(self):
        """12A -> 1A is adjacent (distance 1), NOT distance 11."""
        assert harmonic_score("12A", "1A") == 0.85

    def test_wrap_adjacent_1a_to_12a(self):
        """1A -> 12A is adjacent (distance 1), NOT distance 11."""
        assert harmonic_score("1A", "12A") == 0.85

    def test_wrap_adjacent_12b_to_1b(self):
        assert harmonic_score("12B", "1B") == 0.85

    def test_wrap_adjacent_1b_to_12b(self):
        assert harmonic_score("1B", "12B") == 0.85

    # Parallel key (same number, different mode)
    def test_parallel_8a_8b(self):
        assert harmonic_score("8A", "8B") == 0.80

    def test_parallel_8b_8a(self):
        assert harmonic_score("8B", "8A") == 0.80

    def test_parallel_1a_1b(self):
        assert harmonic_score("1A", "1B") == 0.80

    def test_parallel_12a_12b(self):
        assert harmonic_score("12A", "12B") == 0.80

    # Two steps away (same mode, distance 2)
    def test_two_step_up(self):
        assert harmonic_score("8A", "10A") == 0.50

    def test_two_step_down(self):
        assert harmonic_score("8A", "6A") == 0.50

    def test_two_step_b_mode(self):
        assert harmonic_score("5B", "7B") == 0.50

    # Wrapping two-step (CRITICAL)
    def test_wrap_two_step_11a_to_1a(self):
        """11A -> 1A: distance 2 (wrapping through 12)."""
        assert harmonic_score("11A", "1A") == 0.50

    def test_wrap_two_step_12a_to_2a(self):
        """12A -> 2A: distance 2."""
        assert harmonic_score("12A", "2A") == 0.50

    def test_wrap_two_step_1a_to_11a(self):
        assert harmonic_score("1A", "11A") == 0.50

    def test_wrap_two_step_2a_to_12a(self):
        assert harmonic_score("2A", "12A") == 0.50

    def test_wrap_two_step_11b_to_1b(self):
        assert harmonic_score("11B", "1B") == 0.50

    # Diagonal (adjacent number + mode switch)
    def test_diagonal_8a_9b(self):
        assert harmonic_score("8A", "9B") == 0.40

    def test_diagonal_8a_7b(self):
        assert harmonic_score("8A", "7B") == 0.40

    def test_diagonal_9b_8a(self):
        assert harmonic_score("9B", "8A") == 0.40

    def test_diagonal_5b_4a(self):
        assert harmonic_score("5B", "4A") == 0.40

    def test_diagonal_5b_6a(self):
        assert harmonic_score("5B", "6A") == 0.40

    # Cross-mode wrapping diagonal
    def test_diagonal_wrap_12a_1b(self):
        """12A -> 1B: different mode, distance 1 = diagonal."""
        assert harmonic_score("12A", "1B") == 0.40

    def test_diagonal_wrap_1b_12a(self):
        assert harmonic_score("1B", "12A") == 0.40

    def test_diagonal_wrap_1a_12b(self):
        assert harmonic_score("1A", "12B") == 0.40

    # Incompatible (everything else)
    def test_incompatible_far_same_mode(self):
        """8A -> 3A: distance 5, same mode = incompatible."""
        assert harmonic_score("8A", "3A") == 0.10

    def test_incompatible_far_different_mode(self):
        """8A -> 3B: distance 5, different mode = incompatible."""
        assert harmonic_score("8A", "3B") == 0.10

    def test_incompatible_half_circle(self):
        """8A -> 2A: distance 6."""
        assert harmonic_score("8A", "2A") == 0.10

    def test_incompatible_three_steps_same_mode(self):
        """8A -> 11A: distance 3."""
        assert harmonic_score("8A", "11A") == 0.10

    def test_incompatible_two_steps_diff_mode(self):
        """8A -> 10B: distance 2, different mode = incompatible."""
        assert harmonic_score("8A", "10B") == 0.10

    # Key confidence modifier
    def test_confidence_high_no_effect(self):
        """Both confidences >= 0.7 -> no modifier applied."""
        assert harmonic_score("8A", "8A", conf_a=0.85, conf_b=0.90) == 1.0

    def test_confidence_at_threshold(self):
        """Exactly 0.7 -> no modifier (only < 0.7 triggers)."""
        assert harmonic_score("8A", "8A", conf_a=0.7, conf_b=0.9) == 1.0

    def test_confidence_low_one_side(self):
        """One conf below 0.7 -> multiply by min."""
        result = harmonic_score("8A", "8A", conf_a=0.5, conf_b=0.9)
        assert result == pytest.approx(1.0 * 0.5)

    def test_confidence_low_both_sides(self):
        """Both below 0.7 -> multiply by the lower one."""
        result = harmonic_score("8A", "9A", conf_a=0.4, conf_b=0.6)
        assert result == pytest.approx(0.85 * 0.4)

    def test_confidence_zero(self):
        """Zero confidence -> score becomes 0.0."""
        result = harmonic_score("8A", "8A", conf_a=0.0, conf_b=0.9)
        assert result == pytest.approx(0.0)

    def test_confidence_applied_to_incompatible(self):
        """Low confidence on already-low score."""
        result = harmonic_score("8A", "3A", conf_a=0.5, conf_b=0.9)
        assert result == pytest.approx(0.10 * 0.5)


# ===================================================================
# 2. BPM score tests
# ===================================================================


class TestBpmScore:
    """Tests for BPM compatibility scoring."""

    # Identical BPM
    def test_identical(self):
        assert bpm_score(128, 128) == 1.0

    def test_identical_low(self):
        assert bpm_score(60, 60) == 1.0

    def test_identical_high(self):
        assert bpm_score(200, 200) == 1.0

    # Within 2% -> 1.0
    def test_within_2_percent(self):
        """128 -> 130: ratio=1.015625, pct_diff=0.0156 < 0.02."""
        assert bpm_score(128, 130) == 1.0

    def test_within_2_percent_lower(self):
        """128 -> 126: ratio=128/126=1.0158, pct_diff=0.0158 < 0.02."""
        assert bpm_score(128, 126) == 1.0

    def test_at_2_percent_boundary(self):
        """128 * 1.02 = 130.56. Test 130.56 -> within boundary."""
        assert bpm_score(128, 130.56) == 1.0

    # Within 4% -> 0.8
    def test_within_4_percent(self):
        """128 -> 133: ratio=133/128=1.0390625, pct_diff ~0.039 < 0.04."""
        assert bpm_score(128, 133) == 0.8

    def test_within_4_percent_another(self):
        """100 -> 103: ratio=1.03, pct_diff=0.03."""
        assert bpm_score(100, 103) == 0.8

    # Within 6% -> 0.5
    def test_within_6_percent(self):
        """128 -> 135: ratio=135/128=1.054687, pct_diff ~0.055 < 0.06."""
        assert bpm_score(128, 135) == 0.5

    def test_within_6_percent_lower(self):
        """128 -> 121: ratio=128/121=1.0578, pct_diff ~0.058 < 0.06."""
        assert bpm_score(128, 121) == 0.5

    # Within 10% -> 0.2
    def test_within_10_percent(self):
        """128 -> 140: ratio=140/128=1.09375, pct_diff ~0.094 < 0.10."""
        assert bpm_score(128, 140) == 0.2

    def test_within_10_percent_another(self):
        """100 -> 108: ratio=1.08, pct_diff=0.08."""
        assert bpm_score(100, 108) == 0.2

    # Beyond 10% -> 0.05
    def test_beyond_10_percent(self):
        """128 -> 160: ratio=1.25, pct_diff=0.25."""
        assert bpm_score(128, 160) == 0.05

    def test_far_apart(self):
        """60 -> 200: ratio=3.33."""
        assert bpm_score(60, 200) == 0.05

    # Half time -> 0.6
    def test_half_time(self):
        """128 -> 64: ratio=2.0, within 1.95-2.05."""
        assert bpm_score(128, 64) == 0.6

    def test_half_time_reverse(self):
        """64 -> 128: same ratio."""
        assert bpm_score(64, 128) == 0.6

    # Double time -> 0.6
    def test_double_time(self):
        """128 -> 256: ratio=2.0."""
        assert bpm_score(128, 256) == 0.6

    def test_double_time_reverse(self):
        assert bpm_score(256, 128) == 0.6

    # Near half/double
    def test_near_half_time(self):
        """130 -> 65: ratio=2.0, within 1.95-2.05."""
        assert bpm_score(130, 65) == 0.6

    def test_just_outside_half_time(self):
        """128 -> 62: ratio=128/62=2.0645, outside 1.95-2.05 range.
        pct_diff=1.0645 > 0.10, so score=0.05."""
        assert bpm_score(128, 62) == 0.05

    # Symmetric
    def test_symmetric(self):
        """bpm_score(a, b) should equal bpm_score(b, a)."""
        assert bpm_score(128, 135) == bpm_score(135, 128)

    # BPM stability modifier
    def test_stability_both_high(self):
        """Both stable -> no modifier."""
        assert bpm_score(128, 128, stability_a=0.95, stability_b=0.90) == 1.0

    def test_stability_at_threshold(self):
        """Exactly 0.8 -> no modifier (only < 0.8 triggers)."""
        assert bpm_score(128, 128, stability_a=0.8, stability_b=0.9) == 1.0

    def test_stability_one_low(self):
        """One below 0.8 -> reduce by 20%."""
        result = bpm_score(128, 128, stability_a=0.5, stability_b=0.9)
        assert result == pytest.approx(1.0 * 0.8)

    def test_stability_both_low(self):
        """Both below 0.8 -> still only 20% reduction (not 40%)."""
        result = bpm_score(128, 128, stability_a=0.5, stability_b=0.5)
        assert result == pytest.approx(1.0 * 0.8)

    def test_stability_applied_to_half_time(self):
        """Stability modifier applies to half-time score too."""
        result = bpm_score(128, 64, stability_a=0.5, stability_b=0.9)
        assert result == pytest.approx(0.6 * 0.8)


# ===================================================================
# 3. Energy score tests
# ===================================================================


class TestEnergyScore:
    """Tests for energy compatibility scoring."""

    # Smooth mode (default)
    def test_same_energy(self):
        assert energy_score(0.8, 0.8) == 1.0

    def test_within_010(self):
        """diff=0.08 <= 0.10."""
        assert energy_score(0.8, 0.72) == 1.0

    def test_at_010_boundary(self):
        """diff=0.10 exactly."""
        assert energy_score(0.8, 0.70) == 1.0

    def test_within_020(self):
        """diff=0.15."""
        assert energy_score(0.8, 0.65) == 0.8

    def test_at_020_boundary(self):
        """diff=0.20 exactly."""
        assert energy_score(0.8, 0.60) == 0.8

    def test_within_035(self):
        """diff=0.30."""
        assert energy_score(0.8, 0.50) == 0.5

    def test_at_035_boundary(self):
        """diff=0.35 exactly."""
        assert energy_score(0.8, 0.45) == 0.5

    def test_beyond_035(self):
        """diff=0.50."""
        assert energy_score(0.8, 0.30) == 0.2

    def test_extreme_difference(self):
        """diff=0.80."""
        assert energy_score(1.0, 0.2) == 0.2

    def test_zero_energy(self):
        """diff=0.0."""
        assert energy_score(0.0, 0.0) == 1.0

    def test_max_energy(self):
        assert energy_score(1.0, 1.0) == 1.0

    # Arc mode
    def test_arc_mode_same(self):
        assert energy_score(0.8, 0.8, mode="arc") == pytest.approx(1.0)

    def test_arc_mode_different(self):
        result = energy_score(0.8, 0.5, mode="arc")
        assert result == pytest.approx(0.7)

    def test_arc_mode_max_diff(self):
        result = energy_score(1.0, 0.0, mode="arc")
        assert result == pytest.approx(0.0)


# ===================================================================
# 4. Groove score tests
# ===================================================================


class TestGrooveScore:
    """Tests for groove type compatibility."""

    # Same type = 1.0
    def test_same_four_on_floor(self):
        assert groove_score("four_on_floor", "four_on_floor") == 1.0

    def test_same_breakbeat(self):
        assert groove_score("breakbeat", "breakbeat") == 1.0

    def test_same_half_time(self):
        assert groove_score("half_time", "half_time") == 1.0

    def test_same_complex(self):
        assert groove_score("complex", "complex") == 1.0

    def test_same_syncopated(self):
        assert groove_score("syncopated", "syncopated") == 1.0

    def test_same_straight(self):
        assert groove_score("straight", "straight") == 1.0

    # Good matches
    def test_good_fof_straight(self):
        assert groove_score("four_on_floor", "straight") == 0.7

    def test_good_breakbeat_syncopated(self):
        assert groove_score("breakbeat", "syncopated") == 0.7

    def test_good_breakbeat_complex(self):
        assert groove_score("breakbeat", "complex") == 0.6

    # Symmetric lookups
    def test_symmetric_fof_straight(self):
        assert groove_score("straight", "four_on_floor") == 0.7

    def test_symmetric_breakbeat_syncopated(self):
        assert groove_score("syncopated", "breakbeat") == 0.7

    def test_symmetric_breakbeat_complex(self):
        assert groove_score("complex", "breakbeat") == 0.6

    # Moderate matches
    def test_moderate_fof_half_time(self):
        assert groove_score("four_on_floor", "half_time") == 0.5

    def test_moderate_straight_half_time(self):
        assert groove_score("straight", "half_time") == 0.5

    def test_moderate_syncopated_complex(self):
        assert groove_score("syncopated", "complex") == 0.5

    # Poor matches
    def test_poor_fof_breakbeat(self):
        assert groove_score("four_on_floor", "breakbeat") == 0.3

    def test_poor_fof_syncopated(self):
        assert groove_score("four_on_floor", "syncopated") == 0.3

    def test_poor_half_time_breakbeat(self):
        assert groove_score("half_time", "breakbeat") == 0.3

    def test_poor_straight_syncopated(self):
        assert groove_score("straight", "syncopated") == 0.3

    def test_poor_straight_breakbeat(self):
        assert groove_score("straight", "breakbeat") == 0.3

    # Bad matches
    def test_bad_fof_complex(self):
        assert groove_score("four_on_floor", "complex") == 0.2

    def test_bad_half_time_complex(self):
        assert groove_score("half_time", "complex") == 0.2

    def test_bad_half_time_syncopated(self):
        assert groove_score("half_time", "syncopated") == 0.2

    def test_bad_straight_complex(self):
        assert groove_score("straight", "complex") == 0.2

    # Symmetric bad
    def test_symmetric_bad_complex_fof(self):
        assert groove_score("complex", "four_on_floor") == 0.2

    def test_symmetric_bad_complex_half_time(self):
        assert groove_score("complex", "half_time") == 0.2

    # Unknown pair -> fallback 0.3
    def test_unknown_pair_fallback(self):
        """A pair not in the table at all falls back to 0.3."""
        assert groove_score("unknown_groove", "another_groove") == 0.3


# ===================================================================
# 5. Frequency score tests
# ===================================================================


class TestFrequencyScore:
    """Tests for frequency weight compatibility."""

    # Same = 1.0
    def test_same_bass_heavy(self):
        assert frequency_score("bass_heavy", "bass_heavy") == 1.0

    def test_same_bright(self):
        assert frequency_score("bright", "bright") == 1.0

    def test_same_mid_focused(self):
        assert frequency_score("mid_focused", "mid_focused") == 1.0

    def test_same_balanced(self):
        assert frequency_score("balanced", "balanced") == 1.0

    # Balanced -> anything = 0.7
    def test_balanced_bass(self):
        assert frequency_score("balanced", "bass_heavy") == 0.7

    def test_balanced_bright(self):
        assert frequency_score("balanced", "bright") == 0.7

    def test_balanced_mid(self):
        assert frequency_score("balanced", "mid_focused") == 0.7

    # Symmetric
    def test_symmetric_bass_balanced(self):
        assert frequency_score("bass_heavy", "balanced") == 0.7

    def test_symmetric_bright_balanced(self):
        assert frequency_score("bright", "balanced") == 0.7

    def test_symmetric_mid_balanced(self):
        assert frequency_score("mid_focused", "balanced") == 0.7

    # Mid -> extremes = 0.5
    def test_mid_bass(self):
        assert frequency_score("mid_focused", "bass_heavy") == 0.5

    def test_mid_bright(self):
        assert frequency_score("mid_focused", "bright") == 0.5

    def test_symmetric_bass_mid(self):
        assert frequency_score("bass_heavy", "mid_focused") == 0.5

    def test_symmetric_bright_mid(self):
        assert frequency_score("bright", "mid_focused") == 0.5

    # Extremes clash = 0.3
    def test_bass_bright_clash(self):
        assert frequency_score("bass_heavy", "bright") == 0.3

    def test_symmetric_bright_bass_clash(self):
        assert frequency_score("bright", "bass_heavy") == 0.3

    # Unknown pair -> fallback 0.5
    def test_unknown_pair_fallback(self):
        assert frequency_score("unknown_freq", "another_freq") == 0.5


# ===================================================================
# 6. Mix quality score tests
# ===================================================================


class TestMixQualityScore:
    """Tests for directional mix quality scoring."""

    def test_both_high(self):
        assert mix_quality_score(0.85, 0.90) == pytest.approx(0.875)

    def test_both_perfect(self):
        assert mix_quality_score(1.0, 1.0) == 1.0

    def test_both_zero(self):
        assert mix_quality_score(0.0, 0.0) == 0.0

    def test_one_zero(self):
        assert mix_quality_score(0.0, 1.0) == pytest.approx(0.5)

    def test_asymmetric_values(self):
        """(0.9 + 0.5) / 2 = 0.7."""
        assert mix_quality_score(0.9, 0.5) == pytest.approx(0.7)

    def test_reverse_asymmetric(self):
        """(0.5 + 0.9) / 2 = 0.7. Note: mix_quality_score itself is
        commutative, but compute_compatibility is NOT because A.mix_out
        and B.mix_in differ from B.mix_out and A.mix_in."""
        assert mix_quality_score(0.5, 0.9) == pytest.approx(0.7)

    def test_mid_values(self):
        assert mix_quality_score(0.6, 0.4) == pytest.approx(0.5)


# ===================================================================
# 7. Aggregate compute_compatibility tests
# ===================================================================


class TestComputeCompatibility:
    """Tests for the full weighted compatibility score."""

    def test_returns_tuple(self, mock_track_a, mock_track_b):
        result = compute_compatibility(mock_track_a, mock_track_b)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_score_in_range(self, mock_track_a, mock_track_b):
        score, _ = compute_compatibility(mock_track_a, mock_track_b)
        assert 0.0 <= score <= 1.0

    def test_breakdown_types(self, mock_track_a, mock_track_b):
        _, scores = compute_compatibility(mock_track_a, mock_track_b)
        assert 0.0 <= scores.harmonic <= 1.0
        assert 0.0 <= scores.bpm <= 1.0
        assert 0.0 <= scores.energy <= 1.0
        assert 0.0 <= scores.groove <= 1.0
        assert 0.0 <= scores.frequency <= 1.0
        assert 0.0 <= scores.mix_quality <= 1.0

    def test_matches_manual_calculation(self, mock_track_a, mock_track_b):
        """Verify result matches hand-computed weighted sum.

        Track A: 128 BPM, 8A, energy=0.82, bass_heavy, four_on_floor,
                 mix_out=0.85, key_conf=0.85, bpm_stab=0.97
        Track B: 127 BPM, 9A, energy=0.70, balanced, four_on_floor,
                 mix_in=0.85, key_conf=0.90, bpm_stab=0.95
        """
        score, breakdown = compute_compatibility(mock_track_a, mock_track_b)

        # Harmonic: 8A -> 9A = adjacent = 0.85
        # Both key_confidences >= 0.7, so no modifier
        assert breakdown.harmonic == pytest.approx(0.85)

        # BPM: 128 -> 127 = ratio 128/127 = 1.00787, pct_diff = 0.00787 < 0.02
        # Both stabilities >= 0.8, so no modifier
        assert breakdown.bpm == pytest.approx(1.0)

        # Energy: |0.82 - 0.70| = 0.12, within 0.20 -> 0.8
        assert breakdown.energy == pytest.approx(0.8)

        # Groove: four_on_floor -> four_on_floor = 1.0
        assert breakdown.groove == pytest.approx(1.0)

        # Frequency: bass_heavy -> balanced = 0.7
        assert breakdown.frequency == pytest.approx(0.7)

        # Mix quality: (mix_out_A=0.85 + mix_in_B=0.85) / 2 = 0.85
        assert breakdown.mix_quality == pytest.approx(0.85)

        # Aggregate: 0.85*0.30 + 1.0*0.25 + 0.8*0.15 + 1.0*0.10 + 0.7*0.10
        #            + 0.85*0.10
        # = 0.255 + 0.25 + 0.12 + 0.10 + 0.07 + 0.085 = 0.88
        expected = (
            0.85 * 0.30
            + 1.0 * 0.25
            + 0.8 * 0.15
            + 1.0 * 0.10
            + 0.7 * 0.10
            + 0.85 * 0.10
        )
        assert score == pytest.approx(expected)

    def test_directional_a_to_b_vs_b_to_a(self, mock_track_a, mock_track_b):
        """A->B should differ from B->A because mix_out/mix_in differ.

        A: mix_out=0.85, mix_in=0.90
        B: mix_out=0.80, mix_in=0.85

        A->B mix_quality: (0.85 + 0.85) / 2 = 0.85
        B->A mix_quality: (0.80 + 0.90) / 2 = 0.85

        Hmm, these happen to be equal. Let's still verify the overall
        scores can differ — the frequency sub-score is symmetric, etc.
        Create a test with different mix values to prove directionality.
        """
        score_ab, breakdown_ab = compute_compatibility(
            mock_track_a, mock_track_b
        )
        score_ba, breakdown_ba = compute_compatibility(
            mock_track_b, mock_track_a
        )

        # Mix quality direction check:
        # A->B: (A.mix_out=0.85 + B.mix_in=0.85) / 2 = 0.85
        assert breakdown_ab.mix_quality == pytest.approx(0.85)
        # B->A: (B.mix_out=0.80 + A.mix_in=0.90) / 2 = 0.85
        assert breakdown_ba.mix_quality == pytest.approx(0.85)
        # These happen to be equal, but the function IS directional.

    def test_directional_with_asymmetric_mix(self):
        """Create tracks with very different mix_in vs mix_out to prove
        directionality."""
        track_x = Track(
            file_path="/music/x.mp3",
            file_hash="xxx",
            filename="x.mp3",
            duration_seconds=300.0,
            spotify_style=SpotifyStyleMetrics(
                energy=0.5, danceability=0.5, acousticness=0.5,
                instrumentalness=0.5, valence=0.5, liveness=0.5,
            ),
            dj_metrics=DJMetrics(
                bpm=128.0, bpm_stability=0.95, key="8A",
                key_confidence=0.9, mix_in_score=0.2,
                mix_out_score=0.9, frequency_weight="balanced",
                groove_type="four_on_floor",
            ),
            structure=TrackStructure(),
        )
        track_y = Track(
            file_path="/music/y.mp3",
            file_hash="yyy",
            filename="y.mp3",
            duration_seconds=300.0,
            spotify_style=SpotifyStyleMetrics(
                energy=0.5, danceability=0.5, acousticness=0.5,
                instrumentalness=0.5, valence=0.5, liveness=0.5,
            ),
            dj_metrics=DJMetrics(
                bpm=128.0, bpm_stability=0.95, key="8A",
                key_confidence=0.9, mix_in_score=0.9,
                mix_out_score=0.2, frequency_weight="balanced",
                groove_type="four_on_floor",
            ),
            structure=TrackStructure(),
        )

        score_xy, breakdown_xy = compute_compatibility(track_x, track_y)
        score_yx, breakdown_yx = compute_compatibility(track_y, track_x)

        # X->Y: (X.mix_out=0.9 + Y.mix_in=0.9) / 2 = 0.9
        assert breakdown_xy.mix_quality == pytest.approx(0.9)
        # Y->X: (Y.mix_out=0.2 + X.mix_in=0.2) / 2 = 0.2
        assert breakdown_yx.mix_quality == pytest.approx(0.2)

        # Overall scores should differ
        assert score_xy != pytest.approx(score_yx)

    def test_perfect_match(self):
        """Two identical tracks should score 1.0."""
        track = Track(
            file_path="/music/perfect.mp3",
            file_hash="perf",
            filename="perfect.mp3",
            duration_seconds=300.0,
            spotify_style=SpotifyStyleMetrics(
                energy=0.8, danceability=0.7, acousticness=0.1,
                instrumentalness=0.6, valence=0.5, liveness=0.1,
            ),
            dj_metrics=DJMetrics(
                bpm=128.0, bpm_stability=0.95, key="8A",
                key_confidence=0.9, mix_in_score=1.0,
                mix_out_score=1.0, frequency_weight="balanced",
                groove_type="four_on_floor",
            ),
            structure=TrackStructure(),
        )
        score, breakdown = compute_compatibility(track, track)

        assert breakdown.harmonic == 1.0
        assert breakdown.bpm == 1.0
        assert breakdown.energy == 1.0
        assert breakdown.groove == 1.0
        assert breakdown.frequency == 1.0
        assert breakdown.mix_quality == 1.0
        assert score == pytest.approx(1.0)

    def test_custom_weights(self, mock_track_a, mock_track_b):
        """Custom weights should change the aggregate score."""
        default_score, _ = compute_compatibility(
            mock_track_a, mock_track_b
        )

        # Heavy harmonic emphasis
        config = SuggestionConfig(
            harmonic_weight=0.80,
            bpm_weight=0.04,
            energy_weight=0.04,
            groove_weight=0.04,
            frequency_weight=0.04,
            mix_quality_weight=0.04,
        )
        custom_score, _ = compute_compatibility(
            mock_track_a, mock_track_b, config=config
        )

        # Scores should be different
        assert default_score != pytest.approx(custom_score)

    def test_custom_weights_normalized(self, mock_track_a, mock_track_b):
        """Weights that don't sum to 1.0 are normalized first."""
        config = SuggestionConfig(
            harmonic_weight=0.60,  # Double everything
            bpm_weight=0.50,
            energy_weight=0.30,
            groove_weight=0.20,
            frequency_weight=0.20,
            mix_quality_weight=0.20,
        )
        weights = config.normalized_weights()
        total = sum(weights.values())
        assert total == pytest.approx(1.0)

        score, _ = compute_compatibility(
            mock_track_a, mock_track_b, config=config
        )
        assert 0.0 <= score <= 1.0

    def test_self_compatibility_is_one(self, mock_track_a):
        """A track compared to itself should score very high (may not be
        exactly 1.0 due to mix_quality averaging, but energy/bpm/etc. all 1.0)."""
        score, breakdown = compute_compatibility(mock_track_a, mock_track_a)
        assert breakdown.harmonic == 1.0
        assert breakdown.bpm == 1.0
        assert breakdown.energy == 1.0
        assert breakdown.groove == 1.0
        assert breakdown.frequency == 1.0
        # mix_quality: (0.85 + 0.90) / 2 = 0.875 (not 1.0)
        assert breakdown.mix_quality == pytest.approx(0.875)
        assert 0.0 <= score <= 1.0


# ===================================================================
# Lookup table completeness tests
# ===================================================================


class TestLookupTableCompleteness:
    """Verify lookup tables have no gaps for known type combinations."""

    GROOVE_TYPES = [
        "four_on_floor", "breakbeat", "half_time",
        "complex", "syncopated", "straight",
    ]
    FREQ_TYPES = ["bass_heavy", "bright", "mid_focused", "balanced"]

    def test_all_groove_pairs_have_value(self):
        """Every pair of known groove types should return a float, not raise."""
        for a in self.GROOVE_TYPES:
            for b in self.GROOVE_TYPES:
                result = groove_score(a, b)
                assert isinstance(result, float), f"groove_score({a}, {b})"
                assert 0.0 <= result <= 1.0, f"groove_score({a}, {b}) = {result}"

    def test_groove_table_is_symmetric(self):
        """groove_score(a, b) == groove_score(b, a) for all known types."""
        for a in self.GROOVE_TYPES:
            for b in self.GROOVE_TYPES:
                assert groove_score(a, b) == groove_score(b, a), (
                    f"groove_score({a}, {b}) != groove_score({b}, {a})"
                )

    def test_all_frequency_pairs_have_value(self):
        """Every pair of known frequency types should return a float."""
        for a in self.FREQ_TYPES:
            for b in self.FREQ_TYPES:
                result = frequency_score(a, b)
                assert isinstance(result, float), f"freq_score({a}, {b})"
                assert 0.0 <= result <= 1.0, f"freq_score({a}, {b}) = {result}"

    def test_frequency_table_is_symmetric(self):
        """frequency_score(a, b) == frequency_score(b, a) for all types."""
        for a in self.FREQ_TYPES:
            for b in self.FREQ_TYPES:
                assert frequency_score(a, b) == frequency_score(b, a), (
                    f"freq_score({a}, {b}) != freq_score({b}, {a})"
                )
