"""Node graph canvas — pan, zoom, drag.

Uses QGraphicsView/QGraphicsScene for the interactive node graph.
Supports viewport culling, level-of-detail rendering, and smooth pan/zoom.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from uuid import UUID

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene, QGraphicsView

from rekordbox_creative.db.models import Edge, Track
from rekordbox_creative.ui.edges import EdgeLine
from rekordbox_creative.ui.nodes import TrackNode

logger = logging.getLogger(__name__)

# Max edges to render per node (keeps top-N strongest connections)
MAX_EDGES_PER_NODE = 6


class GraphScene(QGraphicsScene):
    """Scene containing all track nodes and edges."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#16213E")))

        # Lookup maps
        self._nodes: dict[UUID, TrackNode] = {}
        self._edges: dict[tuple[UUID, UUID], EdgeLine] = {}
        # Adjacency map for fast edge-per-node lookup
        self._adj: dict[UUID, list[tuple[UUID, UUID]]] = defaultdict(list)

    def node_moved(self, node: TrackNode) -> None:
        """Called when a node is dragged — update connected edges only."""
        tid = node.track_id
        for key in self._adj.get(tid, []):
            edge_line = self._edges.get(key)
            if edge_line:
                edge_line.update_position()

    def add_track_node(self, track: Track, x: float = 0, y: float = 0) -> TrackNode:
        """Add a track node to the scene."""
        if track.id in self._nodes:
            return self._nodes[track.id]
        node = TrackNode(track)
        node.setPos(x, y)
        self.addItem(node)
        self._nodes[track.id] = node
        return node

    def remove_track_node(self, track_id: UUID) -> None:
        """Remove a track node and its edges."""
        node = self._nodes.pop(track_id, None)
        if node is None:
            return
        # Remove connected edges via adjacency map
        for key in list(self._adj.get(track_id, [])):
            edge_line = self._edges.pop(key, None)
            if edge_line:
                self.removeItem(edge_line)
            # Clean up adjacency on the other side
            other = key[1] if key[0] == track_id else key[0]
            adj_list = self._adj.get(other, [])
            if key in adj_list:
                adj_list.remove(key)
        self._adj.pop(track_id, None)
        self.removeItem(node)

    def add_edge_line(self, edge: Edge) -> EdgeLine | None:
        """Add an edge between two existing nodes."""
        key = (edge.source_id, edge.target_id)
        if key in self._edges:
            return self._edges[key]
        src = self._nodes.get(edge.source_id)
        tgt = self._nodes.get(edge.target_id)
        if src is None or tgt is None:
            return None
        edge_line = EdgeLine(edge, src, tgt)
        self.addItem(edge_line)
        self._edges[key] = edge_line
        self._adj[edge.source_id].append(key)
        self._adj[edge.target_id].append(key)
        return edge_line

    def add_edges_batch(self, edges: list[Edge], max_per_node: int = MAX_EDGES_PER_NODE) -> int:
        """Add edges in batch, limiting to top-N per node for performance.

        Returns the number of edges actually added.
        """
        # Sort by score descending so we take the best edges first
        sorted_edges = sorted(edges, key=lambda e: e.compatibility_score, reverse=True)

        # Count edges per node to enforce the cap
        node_edge_count: dict[UUID, int] = defaultdict(int)
        added = 0

        for edge in sorted_edges:
            src, tgt = edge.source_id, edge.target_id
            if node_edge_count[src] >= max_per_node and node_edge_count[tgt] >= max_per_node:
                continue  # Both nodes already have enough edges
            key = (src, tgt)
            if key in self._edges:
                continue
            src_node = self._nodes.get(src)
            tgt_node = self._nodes.get(tgt)
            if src_node is None or tgt_node is None:
                continue

            edge_line = EdgeLine(edge, src_node, tgt_node)
            self.addItem(edge_line)
            self._edges[key] = edge_line
            self._adj[src].append(key)
            self._adj[tgt].append(key)
            node_edge_count[src] += 1
            node_edge_count[tgt] += 1
            added += 1

        return added

    def clear_all(self) -> None:
        """Remove all nodes and edges."""
        self._nodes.clear()
        self._edges.clear()
        self._adj.clear()
        self.clear()

    def get_node(self, track_id: UUID) -> TrackNode | None:
        return self._nodes.get(track_id)

    def get_all_nodes(self) -> list[TrackNode]:
        return list(self._nodes.values())

    def highlight_edges_for_node(self, track_id: UUID | None) -> None:
        """Highlight edges connected to the selected node, dim others."""
        connected_keys = set(self._adj.get(track_id, [])) if track_id else set()
        for key, edge_line in self._edges.items():
            connected = key in connected_keys
            edge_line.set_highlighted(connected)
            # Enable hover only on highlighted edges
            edge_line.setAcceptHoverEvents(connected)

    def highlight_suggestion_nodes(self, track_ids: list[UUID]) -> None:
        """Add visual glow to suggested track nodes."""
        id_set = set(track_ids)
        for tid, node in self._nodes.items():
            if tid in id_set:
                node.setOpacity(1.0)
            else:
                node.setOpacity(0.7 if id_set else 1.0)

    def clear_highlights(self) -> None:
        """Reset all highlights."""
        for node in self._nodes.values():
            node.setOpacity(1.0)
        for edge_line in self._edges.values():
            edge_line.set_highlighted(False)
            edge_line.setAcceptHoverEvents(False)

    def draw_cluster_hulls(
        self, clusters: dict[int, list[UUID]], colors: dict[int, str] | None = None
    ) -> None:
        """Draw colored hull backgrounds behind clustered nodes (UI-016)."""
        # Remove old hulls (tagged with data key)
        for item in list(self.items()):
            if isinstance(item, QGraphicsEllipseItem) and item.zValue() == 0:
                self.removeItem(item)

        cluster_colors = [
            "#FF444440", "#44CC4440", "#4488FF40", "#FF992240",
            "#AA44FF40", "#22BBAA40", "#FFCC1140", "#FF44AA40",
        ]

        for idx, (cluster_id, track_ids) in enumerate(clusters.items()):
            if cluster_id < 0:
                continue  # Skip noise

            positions = []
            for tid in track_ids:
                node = self._nodes.get(tid)
                if node:
                    positions.append(node.scenePos())

            if len(positions) < 2:
                continue

            # Compute bounding circle
            cx = sum(p.x() for p in positions) / len(positions)
            cy = sum(p.y() for p in positions) / len(positions)
            max_dist = max(
                ((p.x() - cx) ** 2 + (p.y() - cy) ** 2) ** 0.5 for p in positions
            )
            radius = max_dist + 80

            color_hex = cluster_colors[idx % len(cluster_colors)]
            if colors and cluster_id in colors:
                color_hex = colors[cluster_id]

            hull = QGraphicsEllipseItem(cx - radius, cy - radius, radius * 2, radius * 2)
            hull.setBrush(QBrush(QColor(color_hex)))
            hull.setPen(QPen(QColor(color_hex[:7] + "60"), 1))
            hull.setZValue(0)  # Behind edges and nodes
            self.addItem(hull)


class GraphCanvas(QGraphicsView):
    """Interactive graph canvas with pan, zoom, and node selection.

    Implements UI-002 (Node Graph Canvas), UI-013 (Viewport Culling).
    """

    node_selected = pyqtSignal(object)  # Track or None
    node_double_clicked = pyqtSignal(object)  # Track
    node_context_menu = pyqtSignal(object, object)  # Track, QPoint (screen pos)
    edge_created = pyqtSignal(object, object)  # source Track, target Track
    canvas_clicked = pyqtSignal()  # Empty area click

    def __init__(self, parent=None) -> None:
        self._scene = GraphScene()
        super().__init__(self._scene, parent)

        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor("#16213E")))
        # Optimization: disable index for large scenes
        self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)

        # Pan state
        self._panning = False
        self._pan_start = QPointF()

        # Edge creation drag state (UI-007)
        self._edge_dragging = False
        self._edge_source: TrackNode | None = None
        self._drag_line = None

        # Zoom limits
        self._zoom = 1.0
        self._zoom_min = 0.05
        self._zoom_max = 5.0

        # Scene rect — sized for typical libraries
        self._scene.setSceneRect(-5000, -5000, 10000, 10000)

    @property
    def graph_scene(self) -> GraphScene:
        return self._scene

    def fit_all_nodes(self) -> None:
        """Zoom/pan to fit all nodes in view."""
        nodes = self._scene.get_all_nodes()
        if not nodes:
            return
        rect = QRectF()
        for node in nodes:
            rect = rect.united(node.sceneBoundingRect())
        rect.adjust(-100, -100, 100, 100)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom with scroll wheel."""
        factor = 1.15
        if event.angleDelta().y() > 0:
            if self._zoom < self._zoom_max:
                self.scale(factor, factor)
                self._zoom *= factor
        else:
            if self._zoom > self._zoom_min:
                self.scale(1 / factor, 1 / factor)
                self._zoom /= factor

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle selection, pan start, and edge creation drag."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            try:
                item = self.itemAt(event.pos())
                if item is None:
                    # Clicked empty area — deselect
                    self._scene.clearSelection()
                    self._scene.clear_highlights()
                    self.canvas_clicked.emit()
                    self.node_selected.emit(None)
                else:
                    # Find the TrackNode parent
                    node = item
                    while node and not isinstance(node, TrackNode):
                        node = node.parentItem()
                    if isinstance(node, TrackNode):
                        # Check if clicking on the port
                        local_pos = node.mapFromScene(
                            self.mapToScene(event.pos())
                        )
                        if node.is_port_hit(local_pos):
                            # Start edge creation drag (UI-007)
                            self._edge_dragging = True
                            self._edge_source = node
                            from PyQt6.QtCore import QLineF
                            from PyQt6.QtWidgets import QGraphicsLineItem

                            sp = node.scenePos()
                            self._drag_line = QGraphicsLineItem(
                                QLineF(sp, sp)
                            )
                            self._drag_line.setPen(
                                QPen(QColor("#00D4FF"), 2, Qt.PenStyle.DashLine)
                            )
                            self._drag_line.setZValue(20)
                            self._scene.addItem(self._drag_line)
                            return
                        else:
                            self._scene.highlight_edges_for_node(node.track_id)
                            self.node_selected.emit(node.track)
            except Exception:
                logger.exception("Error in mousePressEvent")

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Pan with middle mouse, or update edge drag line."""
        if self._edge_dragging and self._drag_line:
            from PyQt6.QtCore import QLineF

            scene_pos = self.mapToScene(event.pos())
            line = self._drag_line.line()
            self._drag_line.setLine(QLineF(line.p1(), scene_pos))
            return

        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x())
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y())
            )
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if self._edge_dragging:
            self._edge_dragging = False
            if self._drag_line:
                self._scene.removeItem(self._drag_line)
                self._drag_line = None

            # Check if dropped on a target node
            item = self.itemAt(event.pos())
            target = item
            while target and not isinstance(target, TrackNode):
                target = target.parentItem()

            if (isinstance(target, TrackNode)
                    and self._edge_source
                    and target.track_id != self._edge_source.track_id):
                self.edge_created.emit(
                    self._edge_source.track, target.track
                )

            self._edge_source = None
            return

        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Right-click context menu on nodes (UI-012)."""
        item = self.itemAt(event.pos())
        node = item
        while node and not isinstance(node, TrackNode):
            node = node.parentItem()
        if isinstance(node, TrackNode):
            self.node_context_menu.emit(node.track, event.globalPos())
        else:
            super().contextMenuEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.pos())
        node = item
        while node and not isinstance(node, TrackNode):
            node = node.parentItem()
        if isinstance(node, TrackNode):
            self.node_double_clicked.emit(node.track)
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts on the canvas."""
        key = event.key()
        if key == Qt.Key.Key_F:
            self.fit_all_nodes()
        elif key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            self.scale(1.15, 1.15)
            self._zoom *= 1.15
        elif key == Qt.Key.Key_Minus:
            self.scale(1 / 1.15, 1 / 1.15)
            self._zoom /= 1.15
        else:
            super().keyPressEvent(event)
