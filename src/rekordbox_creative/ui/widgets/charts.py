"""Simple chart widgets using QPainter — bar, line, and pie charts."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class BarChart(QWidget):
    """Horizontal bar chart for track usage counts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(120)
        self._data: list[tuple[str, float]] = []  # (label, value)
        self._color = QColor("#00D4FF")

    def set_data(self, data: list[tuple[str, float]]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor("#0d1117"))

        max_val = max(v for _, v in self._data) if self._data else 1
        bar_h = max(8, min(20, (h - 10) // max(len(self._data), 1)))
        label_w = min(80, w // 3)

        for i, (label, val) in enumerate(self._data):
            y = i * (bar_h + 4) + 4
            if y + bar_h > h:
                break

            # Label
            painter.setPen(QPen(QColor("#94a3b8")))
            painter.drawText(2, y, label_w - 4, bar_h, Qt.AlignmentFlag.AlignVCenter, label[:12])

            # Bar
            bar_w = int((w - label_w - 30) * val / max_val) if max_val > 0 else 0
            painter.fillRect(label_w, y, bar_w, bar_h, self._color)

            # Value
            painter.setPen(QPen(QColor("#f1f5f9")))
            painter.drawText(
                label_w + bar_w + 4, y, 30, bar_h,
                Qt.AlignmentFlag.AlignVCenter, str(int(val)),
            )

        painter.end()


class LineChart(QWidget):
    """Simple line chart for trends over time."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(80)
        self._values: list[float] = []
        self._color = QColor("#00D4FF")

    def set_values(self, values: list[float]) -> None:
        self._values = values
        self.update()

    def paintEvent(self, event) -> None:
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = 8

        painter.fillRect(0, 0, w, h, QColor("#0d1117"))

        min_v = min(self._values)
        max_v = max(self._values)
        range_v = max_v - min_v if max_v != min_v else 1.0

        pen = QPen(self._color, 2)
        painter.setPen(pen)

        n = len(self._values)
        prev_x, prev_y = 0, 0
        for i, val in enumerate(self._values):
            x = pad + int(i / (n - 1) * (w - 2 * pad))
            y = pad + int((1.0 - (val - min_v) / range_v) * (h - 2 * pad))
            if i > 0:
                painter.drawLine(prev_x, prev_y, x, y)
            # Draw dot
            painter.setBrush(self._color)
            painter.drawEllipse(x - 3, y - 3, 6, 6)
            prev_x, prev_y = x, y

        painter.end()


class PieChart(QWidget):
    """Simple pie chart for key distribution."""

    # 12-hue Camelot palette
    CAMELOT_COLORS = [
        "#FF4444", "#FF6633", "#FF9922", "#FFCC11", "#99DD00", "#44CC44",
        "#22BBAA", "#22AADD", "#4488FF", "#6644FF", "#AA44FF", "#FF44AA",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self._data: list[tuple[str, float]] = []  # (label, value)

    def set_data(self, data: list[tuple[str, float]]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor("#0d1117"))

        total = sum(v for _, v in self._data) or 1
        size = min(w, h) - 16
        x_off = (w - size) // 2
        y_off = (h - size) // 2

        start_angle = 0
        for i, (label, val) in enumerate(self._data):
            span = int(val / total * 360 * 16)
            color_idx = i % len(self.CAMELOT_COLORS)
            # Try to match Camelot number from label (e.g., "8A" → index 7)
            try:
                num = int(label[:-1]) if label and label[-1] in "AB" else i + 1
                color_idx = (num - 1) % 12
            except (ValueError, IndexError):
                pass

            painter.setBrush(QColor(self.CAMELOT_COLORS[color_idx]))
            painter.setPen(QPen(QColor("#0d1117"), 1))
            painter.drawPie(x_off, y_off, size, size, start_angle, span)
            start_angle += span

        painter.end()
