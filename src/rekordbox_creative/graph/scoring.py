"""Compatibility scoring functions between track pairs.

Implements the 6-component weighted scoring system from ALGORITHM_SPEC.md:
  1. Harmonic score  (weight 0.30) - Camelot wheel key compatibility
  2. BPM score       (weight 0.25) - Tempo proximity with half/double detection
  3. Energy score    (weight 0.15) - Energy level similarity
  4. Groove score    (weight 0.10) - Groove type compatibility
  5. Frequency score (weight 0.10) - Frequency weight compatibility
  6. Mix quality     (weight 0.10) - Directional mix-out/mix-in average

All scoring functions return float in [0.0, 1.0].
Edges are directional: A->B uses mix_out_A and mix_in_B.
"""

from __future__ import annotations

from rekordbox_creative.db.models import EdgeScores, SuggestionConfig, Track

# ---------------------------------------------------------------------------
# Default scoring weights (must match ALGORITHM_SPEC.md)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "harmonic": 0.30,
    "bpm": 0.25,
    "energy": 0.15,
    "groove": 0.10,
    "frequency": 0.10,
    "mix_quality": 0.10,
}

# ---------------------------------------------------------------------------
# 1. Harmonic scoring (Camelot wheel)
# ---------------------------------------------------------------------------


def parse_camelot(key: str) -> tuple[int, str]:
    """Parse Camelot notation. '8A' -> (8, 'A'), '12B' -> (12, 'B')."""
    mode = key[-1]  # 'A' or 'B'
    num = int(key[:-1])
    return num, mode


def camelot_distance(a: int, b: int) -> int:
    """Circular distance on the Camelot wheel (1-12, wrapping).

    12->1 is distance 1, not 11.
    """
    return min(abs(a - b), 12 - abs(a - b))


def harmonic_score(
    key_a: str,
    key_b: str,
    conf_a: float = 1.0,
    conf_b: float = 1.0,
) -> float:
    """Harmonic compatibility score based on Camelot wheel.

    Rules from ALGORITHM_SPEC.md:
    - Same key:                         1.0
    - Adjacent key same mode (+-1):     0.85
    - Parallel key (same num, diff):    0.80
    - Two steps same mode (+-2):        0.50
    - Diagonal (adjacent + mode switch):0.40
    - Everything else:                  0.10

    Key confidence modifier: when min(conf_a, conf_b) < 0.7,
    multiply score by that minimum.
    """
    num_a, mode_a = parse_camelot(key_a)
    num_b, mode_b = parse_camelot(key_b)

    # Same key
    if key_a == key_b:
        score = 1.0
    # Parallel key (same number, different mode: 8A <-> 8B)
    elif num_a == num_b and mode_a != mode_b:
        score = 0.8
    # Same mode checks
    elif mode_a == mode_b:
        dist = camelot_distance(num_a, num_b)
        if dist == 1:
            score = 0.85
        elif dist == 2:
            score = 0.5
        else:
            score = 0.1
    # Different mode checks (diagonal)
    elif mode_a != mode_b:
        dist = camelot_distance(num_a, num_b)
        if dist == 1:
            score = 0.4
        else:
            score = 0.1
    else:
        score = 0.1

    # Key confidence modifier
    min_conf = min(conf_a, conf_b)
    if min_conf < 0.7:
        score *= min_conf

    return score


# ---------------------------------------------------------------------------
# 2. BPM scoring
# ---------------------------------------------------------------------------


def bpm_score(
    bpm_a: float,
    bpm_b: float,
    stability_a: float = 1.0,
    stability_b: float = 1.0,
) -> float:
    """BPM compatibility score.

    Rules from ALGORITHM_SPEC.md:
    - Check half/double time first: if ratio 1.95-2.05, return 0.6
    - Within +-2%:  1.0
    - Within +-4%:  0.8
    - Within +-6%:  0.5
    - Within +-10%: 0.2
    - Beyond:       0.05

    BPM stability modifier: if either stability < 0.8,
    reduce score by 20%.
    """
    ratio = max(bpm_a, bpm_b) / min(bpm_a, bpm_b)

    # Check half/double time
    if 1.95 <= ratio <= 2.05:
        score = 0.6
    else:
        pct_diff = abs(ratio - 1.0)
        if pct_diff <= 0.02:
            score = 1.0
        elif pct_diff <= 0.04:
            score = 0.8
        elif pct_diff <= 0.06:
            score = 0.5
        elif pct_diff <= 0.10:
            score = 0.2
        else:
            score = 0.05

    # Stability modifier
    if stability_a < 0.8 or stability_b < 0.8:
        score *= 0.8

    return score


# ---------------------------------------------------------------------------
# 3. Energy scoring
# ---------------------------------------------------------------------------


def energy_score(
    energy_a: float,
    energy_b: float,
    mode: str = "smooth",
) -> float:
    """Energy compatibility score.

    'smooth' mode (default):
    - +-0.10: 1.0
    - +-0.20: 0.8
    - +-0.35: 0.5
    - beyond: 0.2

    'arc' mode: returns 1.0 - abs(diff) for strategy layer use.
    """
    diff = abs(energy_a - energy_b)

    if mode == "smooth":
        if diff <= 0.10:
            return 1.0
        elif diff <= 0.20:
            return 0.8
        elif diff <= 0.35:
            return 0.5
        else:
            return 0.2
    elif mode == "arc":
        return 1.0 - diff
    else:
        return 1.0 - diff


# ---------------------------------------------------------------------------
# 4. Groove scoring
# ---------------------------------------------------------------------------

GROOVE_COMPATIBILITY: dict[tuple[str, str], float] = {
    # Same type = perfect match
    ("four_on_floor", "four_on_floor"): 1.0,
    ("breakbeat", "breakbeat"): 1.0,
    ("half_time", "half_time"): 1.0,
    ("complex", "complex"): 1.0,
    ("syncopated", "syncopated"): 1.0,
    ("straight", "straight"): 1.0,
    # Good matches
    ("four_on_floor", "straight"): 0.7,
    ("breakbeat", "syncopated"): 0.7,
    ("breakbeat", "complex"): 0.6,
    # Moderate matches
    ("four_on_floor", "half_time"): 0.5,
    ("straight", "half_time"): 0.5,
    ("syncopated", "complex"): 0.5,
    # Poor matches
    ("four_on_floor", "breakbeat"): 0.3,
    ("four_on_floor", "syncopated"): 0.3,
    ("half_time", "breakbeat"): 0.3,
    ("straight", "syncopated"): 0.3,
    ("straight", "breakbeat"): 0.3,
    # Bad matches
    ("four_on_floor", "complex"): 0.2,
    ("half_time", "complex"): 0.2,
    ("half_time", "syncopated"): 0.2,
    ("straight", "complex"): 0.2,
}


def groove_score(groove_a: str, groove_b: str) -> float:
    """Groove type compatibility using lookup table. Symmetric fallback."""
    pair = (groove_a, groove_b)
    return GROOVE_COMPATIBILITY.get(
        pair, GROOVE_COMPATIBILITY.get((groove_b, groove_a), 0.3)
    )


# ---------------------------------------------------------------------------
# 5. Frequency weight scoring
# ---------------------------------------------------------------------------

FREQUENCY_COMPATIBILITY: dict[tuple[str, str], float] = {
    # Same = perfect
    ("bass_heavy", "bass_heavy"): 1.0,
    ("bright", "bright"): 1.0,
    ("mid_focused", "mid_focused"): 1.0,
    ("balanced", "balanced"): 1.0,
    # Balanced transitions well to anything
    ("balanced", "bass_heavy"): 0.7,
    ("balanced", "bright"): 0.7,
    ("balanced", "mid_focused"): 0.7,
    # Mid transitions moderately
    ("mid_focused", "bass_heavy"): 0.5,
    ("mid_focused", "bright"): 0.5,
    # Extremes clash
    ("bass_heavy", "bright"): 0.3,
}


def frequency_score(freq_a: str, freq_b: str) -> float:
    """Frequency weight compatibility. Symmetric fallback."""
    pair = (freq_a, freq_b)
    return FREQUENCY_COMPATIBILITY.get(
        pair, FREQUENCY_COMPATIBILITY.get((freq_b, freq_a), 0.5)
    )


# ---------------------------------------------------------------------------
# 6. Mix quality scoring (directional)
# ---------------------------------------------------------------------------


def mix_quality_score(mix_out_a: float, mix_in_b: float) -> float:
    """Directional mix quality: (mix_out_A + mix_in_B) / 2.0."""
    return (mix_out_a + mix_in_b) / 2.0


# ---------------------------------------------------------------------------
# Aggregate compatibility
# ---------------------------------------------------------------------------


def compute_compatibility(
    track_a: Track,
    track_b: Track,
    config: SuggestionConfig | None = None,
) -> tuple[float, EdgeScores]:
    """Compute full weighted compatibility score between two tracks.

    Returns (aggregate_score, score_breakdown).
    Uses config weights if provided, else defaults.

    This function is directional: A->B uses mix_out_A and mix_in_B.
    """
    scores = EdgeScores(
        harmonic=harmonic_score(
            track_a.dj_metrics.key,
            track_b.dj_metrics.key,
            conf_a=track_a.dj_metrics.key_confidence,
            conf_b=track_b.dj_metrics.key_confidence,
        ),
        bpm=bpm_score(
            track_a.dj_metrics.bpm,
            track_b.dj_metrics.bpm,
            stability_a=track_a.dj_metrics.bpm_stability,
            stability_b=track_b.dj_metrics.bpm_stability,
        ),
        energy=energy_score(
            track_a.spotify_style.energy,
            track_b.spotify_style.energy,
        ),
        groove=groove_score(
            track_a.dj_metrics.groove_type,
            track_b.dj_metrics.groove_type,
        ),
        frequency=frequency_score(
            track_a.dj_metrics.frequency_weight,
            track_b.dj_metrics.frequency_weight,
        ),
        mix_quality=mix_quality_score(
            track_a.dj_metrics.mix_out_score,
            track_b.dj_metrics.mix_in_score,
        ),
    )

    if config is not None:
        weights = config.normalized_weights()
    else:
        weights = DEFAULT_WEIGHTS

    aggregate = (
        scores.harmonic * weights["harmonic"]
        + scores.bpm * weights["bpm"]
        + scores.energy * weights["energy"]
        + scores.groove * weights["groove"]
        + scores.frequency * weights["frequency"]
        + scores.mix_quality * weights["mix_quality"]
    )

    return aggregate, scores
