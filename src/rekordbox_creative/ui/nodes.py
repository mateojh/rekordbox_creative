"""Track node rendering on the QGraphicsScene.

Nodes are color-coded by Camelot key and sized by energy level.
Supports selection, dragging, hover, and level-of-detail rendering.
Optimized for large libraries (200+ tracks).
"""

from __future__ import annotations

import math
from uuid import UUID

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from rekordbox_creative.db.models import Track

# Camelot key number -> color
CAMELOT_COLORS: dict[int, str] = {
    1: "#FF4444",
    2: "#FF6633",
    3: "#FF9922",
    4: "#FFCC11",
    5: "#99DD00",
    6: "#44CC44",
    7: "#22BBAA",
    8: "#22AADD",
    9: "#4488FF",
    10: "#6644FF",
    11: "#AA44FF",
    12: "#FF44AA",
}


def _key_color(key: str) -> QColor:
    """Get the Camelot color for a key string like '8A'."""
    try:
        num = int(key[:-1])
        mode = key[-1]
        hex_color = CAMELOT_COLORS.get(num, "#888888")
        color = QColor(hex_color)
        if mode == "B":
            # Major keys: lighter/pastel version
            color = color.lighter(140)
        return color
    except (ValueError, IndexError):
        return QColor("#888888")


def _node_radius(energy: float) -> float:
    """Node radius based on energy: 10-20px (compact for large libraries)."""
    if energy < 0.3:
        return 10.0
    elif energy < 0.6:
        return 13.0
    elif energy < 0.8:
        return 16.0
    else:
        return 20.0


class TrackNode(QGraphicsItem):
    """A track node on the canvas.

    Renders as a small colored circle by default, expanding to show
    details only when zoomed in. Uses QGraphicsItem (not QGraphicsObject)
    for minimal overhead with 200+ nodes.
    """

    def __init__(self, track: Track, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.track = track
        self._radius = _node_radius(track.spotify_style.energy)
        self._color = _key_color(track.dj_metrics.key)
        self._selected = False
        self._in_sequence = False
        self._sequence_position: int | None = None
        self._hovered = False

        # Enable interactions
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        # No cache — DeviceCoordinateCache causes segfaults with 200+ nodes
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.setZValue(10)

    @property
    def track_id(self) -> UUID:
        return self.track.id

    def set_in_sequence(self, in_seq: bool, position: int | None = None) -> None:
        self._in_sequence = in_seq
        self._sequence_position = position
        self.update()

    def boundingRect(self) -> QRectF:
        r = self._radius
        margin = 4
        # When hovered/selected, we draw a label below — account for it
        extra_h = 20 if self._hovered or self.isSelected() else 0
        return QRectF(-r - margin, -r - margin, (r + margin) * 2, (r + margin) * 2 + extra_h)

    def shape(self):
        """Hit area is just the circle, not the label."""
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        r = self._radius
        path.addEllipse(QPointF(0, 0), r, r)
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        r = self._radius

        # Get current zoom level for LOD
        transform = painter.worldTransform()
        scale = math.sqrt(transform.m11() ** 2 + transform.m12() ** 2)

        if scale < 0.15:
            # Very zoomed out: tiny dot, no antialiasing
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._color))
            painter.drawEllipse(QPointF(0, 0), 3, 3)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw node as a filled circle
        body_color = QColor(self._color)
        body_color.setAlpha(220)
        painter.setBrush(QBrush(body_color))

        # Border style
        if self._in_sequence:
            painter.setPen(QPen(QColor("#FFD700"), 2.5))
        elif self.isSelected():
            painter.setPen(QPen(QColor("#FFFFFF"), 2.5))
        elif self._hovered:
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        else:
            painter.setPen(QPen(QColor("#FFFFFF"), 0.5))

        painter.drawEllipse(QPointF(0, 0), r, r)

        # Key label inside circle (always visible at medium zoom)
        if scale > 0.3:
            key = self.track.dj_metrics.key
            painter.setPen(QPen(QColor("#FFFFFF")))
            font_size = max(5, int(r * 0.55))
            painter.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
            painter.drawText(
                QRectF(-r, -r, r * 2, r * 2),
                Qt.AlignmentFlag.AlignCenter,
                key,
            )

        # Track name label below circle (only when hovered or selected)
        if scale > 0.4 and (self._hovered or self.isSelected()):
            title = self.track.metadata.title or self.track.filename
            if len(title) > 22:
                title = title[:20] + ".."
            bpm = self.track.dj_metrics.bpm
            label = f"{title}\n{bpm:.0f} BPM"

            painter.setPen(QPen(QColor("#E0E0E0")))
            painter.setFont(QFont("Segoe UI", 7))
            label_rect = QRectF(-50, r + 2, 100, 20)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )

        # Connection port for manual edge creation (UI-007)
        if scale > 0.5 and self._hovered:
            port_r = 4
            port_x = r + 2
            port_y = 0
            painter.setBrush(QBrush(QColor("#00D4FF")))
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.drawEllipse(QPointF(port_x, port_y), port_r, port_r)

        # Sequence badge
        if self._in_sequence and self._sequence_position is not None:
            badge_r = 7
            badge_x = -r * 0.6
            badge_y = -r * 0.6
            painter.setBrush(QBrush(QColor("#FFD700")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(badge_x, badge_y), badge_r, badge_r)
            painter.setPen(QPen(QColor("#000000")))
            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.drawText(
                QRectF(badge_x - badge_r, badge_y - badge_r, badge_r * 2, badge_r * 2),
                Qt.AlignmentFlag.AlignCenter,
                str(self._sequence_position + 1),
            )

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.prepareGeometryChange()  # bounding rect changes with hover
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.prepareGeometryChange()
        self.update()
        super().hoverLeaveEvent(event)

    def port_rect(self) -> QRectF:
        """Return the connection port area in local coordinates."""
        r = self._radius
        port_r = 6
        return QRectF(r - 2, -port_r, port_r * 2, port_r * 2)

    def is_port_hit(self, local_pos: QPointF) -> bool:
        """Check if a local position is within the connection port."""
        return self.port_rect().contains(local_pos)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Notify canvas to update edges
            scene = self.scene()
            if scene and hasattr(scene, "node_moved"):
                scene.node_moved(self)
        return super().itemChange(change, value)
