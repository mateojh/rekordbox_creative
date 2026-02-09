"""Layout algorithms — force-directed and scatter map.

Force-directed uses NetworkX spring_layout with compatibility-weighted edges.
Scatter map uses t-SNE for 2D projection of feature vectors.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np
from sklearn.manifold import TSNE

from rekordbox_creative.db.models import NodePosition, Track
from rekordbox_creative.graph.clustering import track_to_vector

logger = logging.getLogger(__name__)


def force_directed_layout(
    graph: nx.DiGraph,
    scale: float = 500.0,
    iterations: int = 50,
    seed: int = 42,
) -> list[NodePosition]:
    """Compute force-directed layout using spring_layout.

    Compatible tracks attract (higher edge weight), incompatible repel.
    Returns NodePosition list with (x, y) coordinates.
    """
    if graph.number_of_nodes() == 0:
        return []

    # spring_layout works on undirected or directed graphs
    # Use edge weight for attraction
    pos = nx.spring_layout(
        graph,
        weight="weight",
        scale=scale,
        iterations=iterations,
        seed=seed,
    )

    return [
        NodePosition(track_id=node_id, x=float(coords[0]), y=float(coords[1]))
        for node_id, coords in pos.items()
    ]


def scatter_layout(
    tracks: list[Track],
    scale: float = 500.0,
    perplexity: float = 30.0,
    random_state: int = 42,
) -> list[NodePosition]:
    """Compute scatter map layout using t-SNE.

    Projects track feature vectors to 2D. Proximity = sonic similarity.
    Deterministic with fixed random_state.
    """
    if len(tracks) == 0:
        return []

    if len(tracks) == 1:
        return [NodePosition(track_id=tracks[0].id, x=0.0, y=0.0)]

    vectors = np.array([track_to_vector(t) for t in tracks])

    # Adjust perplexity if too high for the number of tracks
    effective_perplexity = min(perplexity, max(1.0, len(tracks) - 1.0))

    tsne = TSNE(
        n_components=2,
        perplexity=effective_perplexity,
        random_state=random_state,
        n_iter=1000,
    )
    coords = tsne.fit_transform(vectors)

    # Scale to desired range
    if coords.shape[0] > 1:
        coords_min = coords.min(axis=0)
        coords_max = coords.max(axis=0)
        coord_range = coords_max - coords_min
        coord_range[coord_range == 0] = 1.0
        coords = (coords - coords_min) / coord_range * scale - scale / 2

    return [
        NodePosition(track_id=tracks[i].id, x=float(coords[i, 0]), y=float(coords[i, 1]))
        for i in range(len(tracks))
    ]


def linear_layout(
    tracks: list[Track],
    spacing: float = 100.0,
) -> list[NodePosition]:
    """Simple linear layout for sequence/playlist view.

    Tracks arranged horizontally with even spacing.
    """
    return [
        NodePosition(track_id=track.id, x=i * spacing, y=0.0)
        for i, track in enumerate(tracks)
    ]
