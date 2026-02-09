"""Vibe island detection using DBSCAN clustering.

Groups tracks into clusters based on feature vectors:
[energy, danceability, valence, bpm_normalized, acousticness, instrumentalness, groove_numeric]
"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from rekordbox_creative.db.models import Cluster, Track

logger = logging.getLogger(__name__)

# Groove type ordinal encoding
GROOVE_ORDINALS: dict[str, float] = {
    "four_on_floor": 0.0,
    "straight": 0.17,
    "half_time": 0.33,
    "breakbeat": 0.50,
    "syncopated": 0.67,
    "complex": 0.83,
}


def track_to_vector(track: Track) -> np.ndarray:
    """Convert a Track to a 7-dimensional feature vector for clustering."""
    return np.array([
        track.spotify_style.energy,
        track.spotify_style.danceability,
        track.spotify_style.valence,
        track.dj_metrics.bpm / 200.0,
        track.spotify_style.acousticness,
        track.spotify_style.instrumentalness,
        GROOVE_ORDINALS.get(track.dj_metrics.groove_type, 0.5),
    ])


def _mode(values: list[str]) -> str:
    """Return the most common value in a list."""
    if not values:
        return "unknown"
    counter = Counter(values)
    return counter.most_common(1)[0][0]


def label_cluster(tracks: list[Track]) -> str:
    """Auto-generate a human-readable cluster label from dominant traits."""
    if not tracks:
        return "Empty Cluster"

    avg_energy = sum(t.spotify_style.energy for t in tracks) / len(tracks)
    avg_bpm = sum(t.dj_metrics.bpm for t in tracks) / len(tracks)
    dominant_groove = _mode([t.dj_metrics.groove_type for t in tracks])
    dominant_freq = _mode([t.dj_metrics.frequency_weight for t in tracks])

    if avg_energy > 0.7:
        energy_label = "High Energy"
    elif avg_energy > 0.4:
        energy_label = "Mid Energy"
    else:
        energy_label = "Low Energy"

    groove_display = dominant_groove.replace("_", " ").title()
    freq_display = dominant_freq.replace("_", " ").title()

    return f"{energy_label} {int(avg_bpm)} BPM {groove_display} {freq_display}"


def cluster_tracks(
    tracks: list[Track],
    eps: float = 0.5,
    min_samples: int = 3,
) -> list[Cluster]:
    """Run DBSCAN clustering on tracks, returning Cluster objects.

    Tracks with cluster_id == -1 (noise) are not included in any cluster.
    Updates each track's cluster_id in place.
    """
    if len(tracks) < min_samples:
        logger.info("Too few tracks (%d) for clustering (min_samples=%d)", len(tracks), min_samples)
        return []

    vectors = np.array([track_to_vector(t) for t in tracks])
    scaled = StandardScaler().fit_transform(vectors)

    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    labels = clustering.fit_predict(scaled)

    # Group tracks by cluster label
    cluster_map: dict[int, list[Track]] = {}
    for track, label in zip(tracks, labels):
        label_int = int(label)
        track.cluster_id = label_int if label_int >= 0 else None
        if label_int >= 0:
            cluster_map.setdefault(label_int, []).append(track)

    # Build Cluster objects
    clusters: list[Cluster] = []
    for cluster_id, cluster_tracks_list in sorted(cluster_map.items()):
        centroid = vectors[[i for i, lbl in enumerate(labels) if lbl == cluster_id]].mean(axis=0)

        cluster = Cluster(
            id=cluster_id,
            label=label_cluster(cluster_tracks_list),
            track_ids=[t.id for t in cluster_tracks_list],
            centroid=centroid.tolist(),
            avg_bpm=sum(t.dj_metrics.bpm for t in cluster_tracks_list) / len(cluster_tracks_list),
            avg_energy=sum(t.spotify_style.energy for t in cluster_tracks_list)
            / len(cluster_tracks_list),
            dominant_key=_mode([t.dj_metrics.key for t in cluster_tracks_list]),
            dominant_groove=_mode([t.dj_metrics.groove_type for t in cluster_tracks_list]),
            dominant_frequency_weight=_mode(
                [t.dj_metrics.frequency_weight for t in cluster_tracks_list]
            ),
            track_count=len(cluster_tracks_list),
        )
        clusters.append(cluster)

    logger.info(
        "Clustered %d tracks into %d clusters (%d noise)",
        len(tracks),
        len(clusters),
        sum(1 for lbl in labels if lbl == -1),
    )
    return clusters
