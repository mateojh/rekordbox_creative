"""Python-side QWebChannel bridge for JS <-> Python communication."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


class GraphBridge(QObject):
    """Bridge object exposed to JavaScript via QWebChannel.

    JS calls @pyqtSlot methods on this object.  Python pushes data to JS
    via runJavaScript() on the QWebEnginePage (not through this bridge).
    """

    # Signals emitted when JS notifies Python of user actions
    node_clicked = pyqtSignal(str)           # track_id
    node_double_clicked = pyqtSignal(str)    # track_id
    node_context_menu = pyqtSignal(str, int, int)  # track_id, screenX, screenY
    edge_create_requested = pyqtSignal(str, str)   # source_id, target_id
    canvas_clicked = pyqtSignal()
    js_ready = pyqtSignal()                  # JS finished loading

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    # --- Slots called by JavaScript ---

    @pyqtSlot(str)
    def on_node_click(self, track_id: str) -> None:
        """Called when user clicks a node in the graph."""
        logger.debug("JS node_click: %s", track_id)
        self.node_clicked.emit(track_id)

    @pyqtSlot(str)
    def on_node_dblclick(self, track_id: str) -> None:
        """Called when user double-clicks a node."""
        logger.debug("JS node_dblclick: %s", track_id)
        self.node_double_clicked.emit(track_id)

    @pyqtSlot(str, int, int)
    def on_node_context(self, track_id: str, screen_x: int, screen_y: int) -> None:
        """Called when user right-clicks a node."""
        logger.debug("JS node_context: %s at (%d, %d)", track_id, screen_x, screen_y)
        self.node_context_menu.emit(track_id, screen_x, screen_y)

    @pyqtSlot(str, str)
    def on_edge_create(self, source_id: str, target_id: str) -> None:
        """Called when user drags to create an edge between two nodes."""
        logger.debug("JS edge_create: %s -> %s", source_id, target_id)
        self.edge_create_requested.emit(source_id, target_id)

    @pyqtSlot()
    def on_canvas_click(self) -> None:
        """Called when user clicks empty canvas area."""
        logger.debug("JS canvas_click")
        self.canvas_clicked.emit()

    @pyqtSlot()
    def on_js_ready(self) -> None:
        """Called when the JS side has fully initialized."""
        logger.info("JS bridge ready")
        self.js_ready.emit()

    @pyqtSlot(str)
    def log(self, message: str) -> None:
        """Allow JS to log messages through Python's logging."""
        logger.info("[JS] %s", message)
