"""Pluggable suggestion strategies.

Each strategy returns a modifier (float multiplier) that adjusts
the base compatibility score for a candidate track.
"""

from __future__ import annotations

from rekordbox_creative.db.models import SuggestionStrategy, Track


def harmonic_flow_modifier(candidate: Track, current: Track, **kwargs) -> float:
    """Default strategy — no modification to base scores."""
    return 1.0


def energy_arc_modifier(
    candidate: Track,
    current: Track,
    sequence_position: int = 0,
    estimated_set_length: int = 20,
    **kwargs,
) -> float:
    """Target energy based on set position (build → peak → cool down).

    From ALGORITHM_SPEC.md:
    - < 0.3 progress: build up (0.5 → 0.65)
    - 0.3-0.7: peak (0.7 → 0.91)
    - > 0.7: cool down (0.9 → 0.45)
    """
    if estimated_set_length <= 0:
        return 1.0

    set_progress = min(1.0, sequence_position / max(1, estimated_set_length))

    if set_progress < 0.3:
        target_energy = 0.5 + (set_progress * 0.5)
    elif set_progress < 0.7:
        target_energy = 0.7 + (set_progress * 0.3)
    else:
        target_energy = 0.9 - ((set_progress - 0.7) * 1.5)

    target_energy = max(0.0, min(1.0, target_energy))
    energy_fit = 1.0 - abs(candidate.spotify_style.energy - target_energy)
    return 0.5 + (0.5 * energy_fit)


def discovery_modifier(candidate: Track, current: Track, **kwargs) -> float:
    """Boost tracks never or rarely added to playlists.

    From ALGORITHM_SPEC.md:
    - times_used == 0: 1.3x
    - times_used < 3: 1.15x
    - else: 1.0x
    """
    if candidate.times_used == 0:
        return 1.3
    elif candidate.times_used < 3:
        return 1.15
    else:
        return 1.0


def groove_lock_modifier(candidate: Track, current: Track, **kwargs) -> float:
    """Strongly prefer same groove type.

    From ALGORITHM_SPEC.md:
    - Same groove: 1.2x
    - Different groove: 0.6x
    """
    if candidate.dj_metrics.groove_type == current.dj_metrics.groove_type:
        return 1.2
    else:
        return 0.6


def contrast_modifier(candidate: Track, current: Track, **kwargs) -> float:
    """Reward energy and frequency differences.

    From ALGORITHM_SPEC.md:
    - energy_diff > 0.3: 1.2x
    - different frequency weight: *= 1.1
    """
    modifier = 1.0
    energy_diff = abs(candidate.spotify_style.energy - current.spotify_style.energy)
    if energy_diff > 0.3:
        modifier = 1.2
    if candidate.dj_metrics.frequency_weight != current.dj_metrics.frequency_weight:
        modifier *= 1.1
    return modifier


STRATEGY_MODIFIERS = {
    SuggestionStrategy.HARMONIC_FLOW: harmonic_flow_modifier,
    SuggestionStrategy.ENERGY_ARC: energy_arc_modifier,
    SuggestionStrategy.DISCOVERY: discovery_modifier,
    SuggestionStrategy.GROOVE_LOCK: groove_lock_modifier,
    SuggestionStrategy.CONTRAST: contrast_modifier,
}


def get_strategy_modifier(strategy: SuggestionStrategy):
    """Return the modifier function for a given strategy."""
    return STRATEGY_MODIFIERS.get(strategy, harmonic_flow_modifier)
