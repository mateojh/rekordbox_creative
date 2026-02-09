"""Core suggestion logic.

Implements the suggestion pipeline from ALGORITHM_SPEC.md:
1. Build candidate pool (all tracks not in sequence)
2. Apply user filters
3. Score each candidate against current track
4. Apply strategy modifier
5. Apply sequence context modifier
6. Apply diversity bonus
7. Rank and return top N
"""

from __future__ import annotations

import logging

from rekordbox_creative.db.models import (
    SuggestionConfig,
    SuggestionResult,
    Track,
)
from rekordbox_creative.graph.scoring import compute_compatibility
from rekordbox_creative.suggestions.filters import apply_filters
from rekordbox_creative.suggestions.strategies import get_strategy_modifier

logger = logging.getLogger(__name__)


def sequence_context_modifier(
    candidate: Track,
    last_n_tracks: list[Track],
) -> float:
    """Prevent repetitive suggestions by penalizing recent patterns.

    From ALGORITHM_SPEC.md:
    - Same key as last 2 tracks: 0.8x
    - Same cluster as last 3 tracks: 0.85x
    - Same groove as last 4 tracks: 0.9x
    """
    modifier = 1.0

    if len(last_n_tracks) >= 1:
        recent_keys = [t.dj_metrics.key for t in last_n_tracks[-2:]]
        if candidate.dj_metrics.key in recent_keys:
            modifier *= 0.8

    if len(last_n_tracks) >= 1:
        recent_clusters = [t.cluster_id for t in last_n_tracks[-3:] if t.cluster_id is not None]
        if candidate.cluster_id is not None and candidate.cluster_id in recent_clusters:
            modifier *= 0.85

    if len(last_n_tracks) >= 4:
        recent_grooves = [t.dj_metrics.groove_type for t in last_n_tracks[-4:]]
        if all(g == candidate.dj_metrics.groove_type for g in recent_grooves):
            modifier *= 0.9

    return modifier


def diversity_bonus_score(
    candidate: Track,
    last_n_tracks: list[Track],
    bonus: float = 0.1,
) -> float:
    """Boost tracks from different clusters than recently played.

    Returns bonus amount (0 or bonus value).
    """
    if bonus <= 0 or not last_n_tracks:
        return 0.0

    recent_clusters = {t.cluster_id for t in last_n_tracks[-3:] if t.cluster_id is not None}
    if candidate.cluster_id is not None and candidate.cluster_id not in recent_clusters:
        return bonus
    return 0.0


class SuggestionEngine:
    """Main suggestion engine implementing the full pipeline."""

    def __init__(self, all_tracks: list[Track] | None = None) -> None:
        self._all_tracks = all_tracks or []

    def set_tracks(self, tracks: list[Track]) -> None:
        """Update the track pool."""
        self._all_tracks = tracks

    def suggest(
        self,
        current_track: Track,
        sequence: list[Track] | None = None,
        config: SuggestionConfig | None = None,
    ) -> list[SuggestionResult]:
        """Run the full suggestion pipeline.

        Args:
            current_track: The track to suggest next tracks for.
            sequence: Tracks already in the set (for context modifiers).
            config: User configuration (weights, strategy, filters).

        Returns:
            List of SuggestionResult, sorted by final_score descending.
        """
        if config is None:
            config = SuggestionConfig()
        if sequence is None:
            sequence = []

        # Step 1: Build candidate pool — exclude tracks in sequence
        sequence_ids = {t.id for t in sequence}
        sequence_ids.add(current_track.id)
        candidates = [t for t in self._all_tracks if t.id not in sequence_ids]

        # Step 2: Apply user filters
        candidates = apply_filters(candidates, current_track, config)

        if not candidates:
            return []

        # Get strategy modifier function
        strategy_fn = get_strategy_modifier(config.strategy)

        # Step 3-6: Score each candidate
        results: list[SuggestionResult] = []
        for candidate in candidates:
            # Base compatibility score
            base_score, score_breakdown = compute_compatibility(
                current_track, candidate, config
            )

            # Strategy modifier
            strategy_kwargs = {
                "sequence_position": len(sequence),
                "estimated_set_length": 20,
            }
            strat_mod = strategy_fn(candidate, current_track, **strategy_kwargs)

            # Sequence context modifier
            ctx_mod = sequence_context_modifier(candidate, sequence)

            # Diversity bonus
            div_bonus = diversity_bonus_score(
                candidate, sequence, config.diversity_bonus
            )

            # Final score
            final = base_score * strat_mod * ctx_mod + div_bonus

            results.append(SuggestionResult(
                track_id=candidate.id,
                final_score=final,
                base_compatibility=base_score,
                strategy_modifier=strat_mod,
                context_modifier=ctx_mod,
                diversity_bonus=div_bonus,
                score_breakdown=score_breakdown,
            ))

        # Step 7: Sort and return top N
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results[:config.num_suggestions]
