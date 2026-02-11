"""Smart set generator — builds optimized DJ sets with energy curve targeting.

Given a configuration (start track, length, energy profile), constructs
an ordered sequence that follows harmonic compatibility, energy flow,
and BPM continuity rules.
"""

from __future__ import annotations

import logging
from uuid import UUID

from rekordbox_creative.db.models import (
    EnergyProfile,
    SetBuilderConfig,
    SuggestionConfig,
    Track,
)
from rekordbox_creative.graph.scoring import compute_compatibility

logger = logging.getLogger(__name__)

# Energy curve control points: list of (set_position_0_to_1, target_energy_0_to_1)
ENERGY_CURVES: dict[EnergyProfile, list[tuple[float, float]]] = {
    EnergyProfile.WARM_UP_PEAK_COOL: [
        (0.0, 0.4), (0.3, 0.65), (0.7, 0.9), (1.0, 0.5),
    ],
    EnergyProfile.HIGH_ENERGY: [
        (0.0, 0.7), (0.5, 0.85), (1.0, 0.75),
    ],
    EnergyProfile.CHILL_LOUNGE: [
        (0.0, 0.3), (0.5, 0.45), (1.0, 0.35),
    ],
    EnergyProfile.ROLLERCOASTER: [
        (0.0, 0.4), (0.25, 0.9), (0.5, 0.5), (0.75, 0.85), (1.0, 0.4),
    ],
}

# Camelot wheel distance helper
def _camelot_distance(key_a: str, key_b: str) -> int:
    """Return Camelot distance (0=same, 1=adjacent, etc.)."""
    try:
        num_a, mode_a = int(key_a[:-1]), key_a[-1]
        num_b, mode_b = int(key_b[:-1]), key_b[-1]
    except (ValueError, IndexError):
        return 99
    if key_a == key_b:
        return 0
    if num_a == num_b and mode_a != mode_b:
        return 1  # parallel
    if mode_a == mode_b:
        d = min(abs(num_a - num_b), 12 - abs(num_a - num_b))
        return d
    # Cross-mode
    d = min(abs(num_a - num_b), 12 - abs(num_a - num_b))
    return d + 1


def _interpolate_energy(curve: list[tuple[float, float]], position: float) -> float:
    """Linearly interpolate target energy from control points."""
    if not curve:
        return 0.5
    if position <= curve[0][0]:
        return curve[0][1]
    if position >= curve[-1][0]:
        return curve[-1][1]

    for i in range(len(curve) - 1):
        x0, y0 = curve[i]
        x1, y1 = curve[i + 1]
        if x0 <= position <= x1:
            t = (position - x0) / (x1 - x0) if x1 != x0 else 0
            return y0 + t * (y1 - y0)
    return curve[-1][1]


class SetGenerator:
    """Generates optimized DJ sets following energy profiles."""

    def generate(
        self,
        config: SetBuilderConfig,
        all_tracks: list[Track],
        suggestion_config: SuggestionConfig | None = None,
    ) -> list[Track]:
        """Build a set following the energy profile.

        Args:
            config: Set builder configuration.
            all_tracks: Pool of available tracks.
            suggestion_config: Optional scoring weights.

        Returns:
            Ordered list of tracks forming the set.
        """
        if not all_tracks:
            return []

        # Get energy curve
        if config.energy_profile == EnergyProfile.CUSTOM and config.custom_energy_points:
            curve = config.custom_energy_points
        else:
            curve = ENERGY_CURVES.get(
                config.energy_profile,
                ENERGY_CURVES[EnergyProfile.WARM_UP_PEAK_COOL],
            )

        # Find start track
        available = list(all_tracks)
        start = None
        if config.start_track_id:
            for t in available:
                if t.id == config.start_track_id:
                    start = t
                    break

        if not start:
            # Pick track closest to the target energy at position 0
            target_e = _interpolate_energy(curve, 0.0)
            start = min(
                available,
                key=lambda t: abs(t.spotify_style.energy - target_e),
            )

        sequence = [start]
        used_ids: set[UUID] = {start.id}
        total_duration = start.duration_seconds
        target_seconds = config.target_minutes * 60
        crossfade_overlap = 8.0  # ~16 beats at 128 BPM

        while total_duration < target_seconds and len(used_ids) < len(available):
            current = sequence[-1]
            set_progress = total_duration / target_seconds

            # Target energy at this position
            target_energy = _interpolate_energy(curve, set_progress)

            # Score candidates
            candidates = [t for t in available if t.id not in used_ids]
            if not candidates:
                break

            best_track = None
            best_score = -1.0

            for candidate in candidates:
                # BPM guardrail
                bpm_ratio = max(current.dj_metrics.bpm, candidate.dj_metrics.bpm) / \
                    min(current.dj_metrics.bpm, candidate.dj_metrics.bpm)
                if abs(bpm_ratio - 1.0) > config.bpm_tolerance:
                    continue

                # Key guardrail: prefer compatible keys
                key_dist = _camelot_distance(
                    current.dj_metrics.key, candidate.dj_metrics.key
                )

                # Compatibility score
                compat, _ = compute_compatibility(
                    current, candidate, suggestion_config
                )

                # Energy fit score (how close to target)
                energy_diff = abs(candidate.spotify_style.energy - target_energy)
                energy_fit = max(0.0, 1.0 - energy_diff * 2.0)

                # Key penalty: penalize distant keys
                key_bonus = 1.0 if key_dist <= 1 else (0.7 if key_dist == 2 else 0.4)

                # Combined score
                score = compat * 0.4 + energy_fit * 0.4 + key_bonus * 0.2

                if score > best_score:
                    best_score = score
                    best_track = candidate

            if best_track is None:
                # No BPM-compatible candidate; relax constraint
                remaining = [t for t in available if t.id not in used_ids]
                if not remaining:
                    break
                # Pick best by energy fit alone
                best_track = min(
                    remaining,
                    key=lambda t: abs(t.spotify_style.energy - target_energy),
                )

            sequence.append(best_track)
            used_ids.add(best_track.id)
            total_duration += best_track.duration_seconds - crossfade_overlap

        # Optional: 2-opt refinement
        if len(sequence) >= 4:
            try:
                from rekordbox_creative.graph.pathfinding import optimal_order
                sequence = optimal_order(
                    sequence,
                    start=sequence[0],
                    config=suggestion_config,
                    max_2opt_iterations=500,
                )
            except Exception:
                logger.exception("2-opt refinement failed, using greedy order")

        return sequence
