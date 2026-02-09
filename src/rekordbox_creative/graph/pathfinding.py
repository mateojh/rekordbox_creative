"""Optimal set ordering — greedy nearest-neighbor + 2-opt improvement.

Given a set of tracks and a compatibility function, find the ordering
that maximizes total transition quality.
"""

from __future__ import annotations

import logging

from rekordbox_creative.db.models import SuggestionConfig, Track
from rekordbox_creative.graph.scoring import compute_compatibility

logger = logging.getLogger(__name__)


def _compat(track_a: Track, track_b: Track, config: SuggestionConfig | None = None) -> float:
    """Compute compatibility score between two tracks."""
    score, _ = compute_compatibility(track_a, track_b, config)
    return score


def total_compatibility(
    ordered: list[Track],
    config: SuggestionConfig | None = None,
) -> float:
    """Sum of consecutive compatibility scores in an ordered list."""
    if len(ordered) < 2:
        return 0.0
    return sum(
        _compat(ordered[i], ordered[i + 1], config)
        for i in range(len(ordered) - 1)
    )


def greedy_order(
    tracks: list[Track],
    start: Track | None = None,
    config: SuggestionConfig | None = None,
) -> list[Track]:
    """Greedy nearest-neighbor ordering — O(n^2).

    Starts with the given track (or highest-energy if not specified),
    then greedily picks the best compatible unvisited track.
    """
    if len(tracks) <= 1:
        return list(tracks)

    remaining = set(range(len(tracks)))
    track_map = {i: t for i, t in enumerate(tracks)}

    if start is not None:
        # Find start track in list
        current_idx = next(
            (i for i, t in enumerate(tracks) if t.id == start.id),
            None,
        )
        if current_idx is None:
            current_idx = max(remaining, key=lambda i: track_map[i].spotify_style.energy)
    else:
        current_idx = max(remaining, key=lambda i: track_map[i].spotify_style.energy)

    ordered_indices = [current_idx]
    remaining.remove(current_idx)

    while remaining:
        current_track = track_map[ordered_indices[-1]]
        best_idx = max(
            remaining,
            key=lambda i: _compat(current_track, track_map[i], config),
        )
        ordered_indices.append(best_idx)
        remaining.remove(best_idx)

    return [track_map[i] for i in ordered_indices]


def two_opt_improve(
    ordered: list[Track],
    max_iterations: int = 1000,
    config: SuggestionConfig | None = None,
) -> list[Track]:
    """Improve an ordering by 2-opt segment reversal.

    Tries reversing every sub-segment; accepts if total compatibility improves.
    Returns improved ordering (always >= original quality).
    """
    if len(ordered) < 3:
        return list(ordered)

    result = list(ordered)
    best_score = total_compatibility(result, config)
    improved = True
    iteration = 0

    while improved and iteration < max_iterations:
        improved = False
        for i in range(1, len(result) - 1):
            for j in range(i + 1, len(result)):
                new_order = result[:i] + result[i:j + 1][::-1] + result[j + 1:]
                new_score = total_compatibility(new_order, config)
                if new_score > best_score:
                    result = new_order
                    best_score = new_score
                    improved = True
        iteration += 1

    return result


def optimal_order(
    tracks: list[Track],
    start: Track | None = None,
    config: SuggestionConfig | None = None,
    max_2opt_iterations: int = 1000,
) -> list[Track]:
    """Find optimal ordering: greedy + 2-opt refinement."""
    greedy = greedy_order(tracks, start=start, config=config)
    return two_opt_improve(greedy, max_iterations=max_2opt_iterations, config=config)
