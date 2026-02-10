"""Edge rendering between track nodes.

Edge thickness scales with compatibility score.
Supports hover and selection highlighting.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from rekordbox_creative.db.models import Edge
from rekordbox_creative.ui.nodes import TrackNode


def _edge_width(score: float) -> float:
    """Edge thickness based on compatibility score."""
    if score < 0.5:
        return 1.0
    elif score < 0.7:
        return 2.0
    elif score < 0.9:
        return 3.0
    else:
        return 4.0


def _edge_alpha(score: float) -> int:
    """Edge opacity based on compatibility score."""
    if score < 0.5:
        return 40
    elif score < 0.7:
        return 80
    else:
        return 140


class EdgeLine(QGraphicsLineItem):
    """A compatibility edge between two track nodes.

    Thickness and opacity scale with the compatibility score.
    """

    def __init__(
        self,
        edge: Edge,
        source_node: TrackNode,
        target_node: TrackNode,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.edge = edge
        self.source_node = source_node
        self.target_node = target_node
        self._hovered = False
        self._highlighted = False

        self.setAcceptHoverEvents(False)  # Disabled by default for perf
        self.setZValue(1)  # Below nodes
        self.update_position()
        self._apply_style()

    def _apply_style(self) -> None:
        score = self.edge.compatibility_score
        width = _edge_width(score)
        alpha = _edge_alpha(score)

        if self._highlighted:
            color = QColor("#00D4FF")
            color.setAlpha(min(alpha + 80, 255))
            width += 1
        elif self._hovered:
            color = QColor("#FFFFFF")
            color.setAlpha(min(alpha + 60, 200))
            width += 0.5
        elif self.edge.is_user_created:
            color = QColor("#FFD700")
            color.setAlpha(alpha + 40)
        else:
            color = QColor("#FFFFFF")
            color.setAlpha(alpha)

        pen = QPen(color, width)
        if self.edge.is_user_created:
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)

    def set_highlighted(self, highlighted: bool) -> None:
        self._highlighted = highlighted
        self._apply_style()

    def update_position(self) -> None:
        """Reposition edge endpoints to match node positions."""
        sp = self.source_node.scenePos()
        tp = self.target_node.scenePos()
        self.setLine(QLineF(sp, tp))

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        # Get current zoom level for LOD
        transform = painter.worldTransform()
        scale = math.sqrt(transform.m11() ** 2 + transform.m12() ** 2)

        if scale < 0.2:
            return  # Don't draw edges when very zoomed out

        super().paint(painter, option, widget)

        # Show score label on hover at medium zoom
        if self._hovered and scale > 0.5:
            line = self.line()
            mid = QPointF(
                (line.x1() + line.x2()) / 2,
                (line.y1() + line.y2()) / 2,
            )
            painter.setPen(QPen(QColor("#E0E0E0")))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(mid.x() - 20, mid.y() - 12, 40, 24),
                Qt.AlignmentFlag.AlignCenter,
                f"{self.edge.compatibility_score:.2f}",
            )

    def hoverEnterEvent(self, event):
        self._hovered = True
        self._apply_style()
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        self.update()
        super().hoverLeaveEvent(event)
