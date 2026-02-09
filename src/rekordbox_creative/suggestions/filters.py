"""User-configurable suggestion filters.

Filters reduce the candidate pool before scoring. Each filter
takes a list of tracks and returns the subset that passes.
"""

from __future__ import annotations

from rekordbox_creative.db.models import SuggestionConfig, Track
from rekordbox_creative.graph.scoring import harmonic_score


def apply_filters(
    candidates: list[Track],
    current_track: Track,
    config: SuggestionConfig,
) -> list[Track]:
    """Apply all active filters based on config, return filtered candidates."""
    result = candidates

    # BPM range filter (SUG-008)
    if config.bpm_min is not None:
        result = [t for t in result if t.dj_metrics.bpm >= config.bpm_min]
    if config.bpm_max is not None:
        result = [t for t in result if t.dj_metrics.bpm <= config.bpm_max]

    # Key lock filter (SUG-009)
    if config.key_lock:
        result = [
            t for t in result
            if harmonic_score(current_track.dj_metrics.key, t.dj_metrics.key) >= 0.4
        ]

    # Groove lock filter
    if config.groove_lock:
        result = [
            t for t in result
            if t.dj_metrics.groove_type == current_track.dj_metrics.groove_type
        ]

    # Cluster exclusion
    if config.exclude_cluster_ids:
        result = [
            t for t in result
            if t.cluster_id not in config.exclude_cluster_ids
        ]

    return result
