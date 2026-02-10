"""Core graph structure — nodes, edges, adjacency.

Wraps NetworkX DiGraph to manage track nodes and compatibility edges.
"""

from __future__ import annotations

import logging
from uuid import UUID

import networkx as nx

from rekordbox_creative.db.models import Edge, SuggestionConfig, Track
from rekordbox_creative.graph.scoring import compute_compatibility

logger = logging.getLogger(__name__)


class TrackGraph:
    """NetworkX DiGraph wrapper for the track compatibility graph.

    Nodes are Track objects keyed by UUID.
    Edges are weighted by compatibility score.
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, track: Track) -> None:
        """Add a track as a node in the graph."""
        self._graph.add_node(track.id, track=track)

    def remove_node(self, track_id: UUID) -> None:
        """Remove a node and all connected edges."""
        if track_id in self._graph:
            self._graph.remove_node(track_id)

    def get_node(self, track_id: UUID) -> Track | None:
        """Get the Track stored at a node, or None."""
        data = self._graph.nodes.get(track_id)
        if data is None:
            return None
        return data.get("track")

    def get_all_nodes(self) -> list[Track]:
        """Return all tracks in the graph."""
        return [data["track"] for _, data in self._graph.nodes(data=True)]

    def has_node(self, track_id: UUID) -> bool:
        """Check if a node exists in the graph."""
        return track_id in self._graph

    @property
    def node_count(self) -> int:
        """Number of nodes in the graph."""
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Number of edges in the graph."""
        return self._graph.number_of_edges()

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, edge: Edge) -> None:
        """Add a pre-computed edge to the graph."""
        self._graph.add_edge(
            edge.source_id,
            edge.target_id,
            edge=edge,
            weight=edge.compatibility_score,
        )

    def get_edge(self, source_id: UUID, target_id: UUID) -> Edge | None:
        """Get edge data between two nodes."""
        data = self._graph.edges.get((source_id, target_id))
        if data is None:
            return None
        return data.get("edge")

    def get_edges_for_node(self, track_id: UUID) -> list[Edge]:
        """Get all edges connected to a node (both directions)."""
        edges: list[Edge] = []
        if track_id not in self._graph:
            return edges
        # Outgoing
        for _, target, data in self._graph.out_edges(track_id, data=True):
            if "edge" in data:
                edges.append(data["edge"])
        # Incoming
        for source, _, data in self._graph.in_edges(track_id, data=True):
            if "edge" in data:
                edges.append(data["edge"])
        return edges

    def get_all_edges(self) -> list[Edge]:
        """Return all edges in the graph."""
        return [
            data["edge"]
            for _, _, data in self._graph.edges(data=True)
            if "edge" in data
        ]

    # ------------------------------------------------------------------
    # Edge computation
    # ------------------------------------------------------------------

    @staticmethod
    def _bpm_compatible(bpm_a: float, bpm_b: float, max_ratio: float = 0.12) -> bool:
        """Quick BPM pre-filter: skip pairs that are obviously too far apart.

        Checks within ±max_ratio, plus half/double time.
        Used to reduce O(n²) edge computation for large libraries (PERF-001).
        """
        if bpm_a <= 0 or bpm_b <= 0:
            return True
        ratio = max(bpm_a, bpm_b) / min(bpm_a, bpm_b)
        # Normal range
        if ratio <= 1.0 + max_ratio:
            return True
        # Half/double time
        if 1.90 <= ratio <= 2.10:
            return True
        return False

    def compute_edges(
        self,
        threshold: float = 0.3,
        config: SuggestionConfig | None = None,
    ) -> list[Edge]:
        """Compute compatibility edges between all node pairs.

        Only stores edges with score >= threshold.
        Uses BPM pre-filtering for large libraries (PERF-001).
        Returns list of newly created edges.
        """
        nodes = self.get_all_nodes()
        new_edges: list[Edge] = []

        for i, track_a in enumerate(nodes):
            for j, track_b in enumerate(nodes):
                if i == j:
                    continue
                # Skip if edge already exists
                if self._graph.has_edge(track_a.id, track_b.id):
                    continue

                # BPM pre-filter (PERF-001): skip obviously incompatible pairs
                if not self._bpm_compatible(
                    track_a.dj_metrics.bpm, track_b.dj_metrics.bpm
                ):
                    continue

                score, scores = compute_compatibility(track_a, track_b, config)
                if score >= threshold:
                    edge = Edge(
                        source_id=track_a.id,
                        target_id=track_b.id,
                        compatibility_score=score,
                        scores=scores,
                    )
                    self.add_edge(edge)
                    new_edges.append(edge)

        return new_edges

    def compute_edges_for_new_tracks(
        self,
        new_tracks: list[Track],
        threshold: float = 0.3,
        config: SuggestionConfig | None = None,
    ) -> list[Edge]:
        """Compute edges only for new tracks against all existing nodes.

        Incremental computation: new_tracks x all_nodes (both directions).
        Uses BPM pre-filtering for large libraries (PERF-001).
        """
        all_nodes = self.get_all_nodes()
        new_ids = {t.id for t in new_tracks}
        new_edges: list[Edge] = []

        for new_track in new_tracks:
            for existing_track in all_nodes:
                if new_track.id == existing_track.id:
                    continue

                # BPM pre-filter (PERF-001)
                if not self._bpm_compatible(
                    new_track.dj_metrics.bpm, existing_track.dj_metrics.bpm
                ):
                    continue

                # new -> existing
                if not self._graph.has_edge(new_track.id, existing_track.id):
                    score, scores = compute_compatibility(
                        new_track, existing_track, config
                    )
                    if score >= threshold:
                        edge = Edge(
                            source_id=new_track.id,
                            target_id=existing_track.id,
                            compatibility_score=score,
                            scores=scores,
                        )
                        self.add_edge(edge)
                        new_edges.append(edge)

                # existing -> new (skip if both are new — handled in first loop)
                if existing_track.id not in new_ids:
                    if not self._graph.has_edge(existing_track.id, new_track.id):
                        score, scores = compute_compatibility(
                            existing_track, new_track, config
                        )
                        if score >= threshold:
                            edge = Edge(
                                source_id=existing_track.id,
                                target_id=new_track.id,
                                compatibility_score=score,
                                scores=scores,
                            )
                            self.add_edge(edge)
                            new_edges.append(edge)

        return new_edges

    # ------------------------------------------------------------------
    # NetworkX access (for layout algorithms etc.)
    # ------------------------------------------------------------------

    @property
    def nx_graph(self) -> nx.DiGraph:
        """Expose the underlying NetworkX graph."""
        return self._graph
