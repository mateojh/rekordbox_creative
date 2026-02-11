"""WebGL graph canvas using Sigma.js embedded in QWebEngineView.

Drop-in replacement for the old QGraphicsView-based GraphCanvas.
Exposes the same signal interface so app.py connections are unchanged.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

from PyQt6.QtCore import QPoint, QUrl, pyqtSignal
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView

from rekordbox_creative.db.models import Edge, Track
from rekordbox_creative.graph.layout import NodePosition
from rekordbox_creative.ui.web.bridge import GraphBridge
from rekordbox_creative.ui.web.serializers import (
    serialize_clusters,
    serialize_graph,
    serialize_positions,
)

logger = logging.getLogger(__name__)

# Path to the HTML entry point
_ASSETS_DIR = Path(__file__).parent / "assets"
_INDEX_HTML = _ASSETS_DIR / "index.html"


class WebGraphCanvas(QWebEngineView):
    """Sigma.js-powered graph canvas that mirrors GraphCanvas's signal API.

    Signals (same as old GraphCanvas):
        node_selected(object)        — Track or None
        node_double_clicked(object)  — Track
        node_context_menu(object, object) — Track, QPoint
        edge_created(object, object) — source Track, target Track
        canvas_clicked()
    """

    node_selected = pyqtSignal(object)
    node_double_clicked = pyqtSignal(object)
    node_context_menu = pyqtSignal(object, object)
    edge_created = pyqtSignal(object, object)
    canvas_clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Track lookup for resolving IDs from JS
        self._tracks: dict[UUID, Track] = {}
        self._js_ready = False
        self._pending_calls: list[str] = []

        # Set up the QWebChannel bridge
        self._bridge = GraphBridge(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        # Connect bridge signals to our public signals
        self._bridge.node_clicked.connect(self._on_node_clicked)
        self._bridge.node_double_clicked.connect(self._on_node_dblclicked)
        self._bridge.node_context_menu.connect(self._on_node_context)
        self._bridge.edge_create_requested.connect(self._on_edge_create)
        self._bridge.canvas_clicked.connect(self.canvas_clicked.emit)
        self._bridge.js_ready.connect(self._on_js_ready)

        # Load the HTML page
        url = QUrl.fromLocalFile(str(_INDEX_HTML.resolve()))
        self.setUrl(url)

    # --- Private: resolve track IDs from JS ---

    def _resolve_track(self, track_id_str: str) -> Track | None:
        try:
            uid = UUID(track_id_str)
            return self._tracks.get(uid)
        except ValueError:
            logger.warning("Invalid track ID from JS: %s", track_id_str)
            return None

    def _on_node_clicked(self, track_id_str: str) -> None:
        track = self._resolve_track(track_id_str)
        self.node_selected.emit(track)

    def _on_node_dblclicked(self, track_id_str: str) -> None:
        track = self._resolve_track(track_id_str)
        if track:
            self.node_double_clicked.emit(track)

    def _on_node_context(self, track_id_str: str, sx: int, sy: int) -> None:
        track = self._resolve_track(track_id_str)
        if track:
            self.node_context_menu.emit(track, QPoint(sx, sy))

    def _on_edge_create(self, src_str: str, tgt_str: str) -> None:
        src = self._resolve_track(src_str)
        tgt = self._resolve_track(tgt_str)
        if src and tgt:
            self.edge_created.emit(src, tgt)

    def _on_js_ready(self) -> None:
        """Flush any JS calls that were queued before the page loaded."""
        self._js_ready = True
        logger.info("JS ready — flushing %d pending calls", len(self._pending_calls))
        for js in self._pending_calls:
            self.page().runJavaScript(js)
        self._pending_calls.clear()

    # --- Private: run JS safely ---

    def _run_js(self, js_code: str) -> None:
        """Execute JavaScript, queuing if the page isn't ready yet."""
        if self._js_ready:
            self.page().runJavaScript(js_code)
        else:
            self._pending_calls.append(js_code)

    # --- Public API (mirrors old GraphCanvas) ---

    def set_graph_data(
        self,
        tracks: list[Track],
        edges: list[Edge],
        positions: list[NodePosition],
    ) -> None:
        """Load a complete graph into the Sigma.js renderer."""
        self._tracks = {t.id: t for t in tracks}
        graph_json = serialize_graph(tracks, edges, positions)
        self._run_js(f"window.graphEngine.loadGraph({graph_json});")

    def update_layout(self, positions: list[NodePosition]) -> None:
        """Animate nodes to new positions (e.g., after layout switch)."""
        pos_json = serialize_positions(positions)
        self._run_js(f"window.graphEngine.updatePositions({pos_json});")

    def highlight_suggestions(self, track_ids: list[UUID]) -> None:
        """Highlight a set of suggested tracks on the graph."""
        ids_json = json.dumps([str(tid) for tid in track_ids])
        self._run_js(f"window.graphEngine.highlightNodes({ids_json});")

    def clear_highlights(self) -> None:
        """Reset all visual highlights."""
        self._run_js("window.graphEngine.clearHighlights();")

    def set_node_in_sequence(self, track_id: UUID, position: int) -> None:
        """Mark a node as being in the set sequence with a badge."""
        self._run_js(
            f'window.graphEngine.setNodeInSequence("{track_id}", {position});'
        )

    def clear_sequence_badges(self) -> None:
        """Remove all sequence position badges."""
        self._run_js("window.graphEngine.clearSequenceBadges();")

    def fit_all_nodes(self) -> None:
        """Zoom to fit all nodes in the viewport."""
        self._run_js("window.graphEngine.fitAll();")

    def add_edge(self, edge: Edge) -> None:
        """Add a single edge to the rendered graph."""
        from rekordbox_creative.ui.web.serializers import serialize_edge
        edge_json = json.dumps(serialize_edge(edge))
        self._run_js(f"window.graphEngine.addEdge({edge_json});")

    def set_edge_threshold(self, threshold: float) -> None:
        """Filter visible edges by minimum compatibility score."""
        self._run_js(f"window.graphEngine.setEdgeThreshold({threshold});")

    def draw_cluster_hulls(self, clusters: dict[int, list[UUID]]) -> None:
        """Draw colored background regions behind clusters."""
        clusters_json = serialize_clusters(clusters)
        self._run_js(f"window.graphEngine.drawClusterHulls({clusters_json});")

    def set_camelot_key(self, key: str | None) -> None:
        """Update the Camelot wheel overlay to highlight a key."""
        if key:
            self._run_js(
                f'if(window.camelotWheel) window.camelotWheel.setKey("{key}");'
            )
        else:
            self._run_js("if(window.camelotWheel) window.camelotWheel.clear();")

    def set_energy_sequence(self, tracks: list[Track]) -> None:
        """Update the energy flow sparkline with the current sequence."""
        seq = json.dumps([
            {"label": t.filename, "energy": t.spotify_style.energy, "key": t.dj_metrics.key}
            for t in tracks
        ])
        self._run_js(f"if(window.energyFlow) window.energyFlow.setSequence({seq});")

    def set_node_tags(self, track_id: UUID, tags: list[dict]) -> None:
        """Render colored border ring for tags on a node."""
        tags_json = json.dumps([{"name": t["name"], "color": t["color"]} for t in tags])
        self._run_js(
            f'window.graphEngine.setNodeTags("{track_id}", {tags_json});'
        )

    def set_playing_node(self, track_id: UUID) -> None:
        """Set the currently playing node (adds pulse animation)."""
        self._run_js(f'window.graphEngine.setPlayingNode("{track_id}");')

    def clear_playing_node(self) -> None:
        """Remove the playing node indicator."""
        self._run_js("window.graphEngine.clearPlayingNode();")

    def load_node_artwork(self, artwork_map: dict[str, str]) -> None:
        """Load album artwork onto nodes.

        Sends images in batches to avoid overwhelming runJavaScript.

        Args:
            artwork_map: dict mapping track_id string to base64 data URI
        """
        if not artwork_map:
            return

        # Send in batches of 15 to avoid excessively large JS payloads
        # (each 240x240 artwork is ~20KB base64)
        items = list(artwork_map.items())
        batch_size = 15
        for i in range(0, len(items), batch_size):
            batch = dict(items[i : i + batch_size])
            batch_json = json.dumps(batch)
            self._run_js(
                f"if(window.nodeImageOverlay) window.nodeImageOverlay.loadImages({batch_json});"
            )
