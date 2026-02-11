"""History panel — browse past sets and view analytics."""

from __future__ import annotations

import logging
from uuid import UUID

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.history import HistoryStore
from rekordbox_creative.ui.widgets.charts import BarChart, LineChart, PieChart

logger = logging.getLogger(__name__)

PANEL_STYLE = """
    QWidget { background: transparent; color: #f1f5f9; }
    QLabel { color: #94a3b8; font-size: 11px; }
"""

SET_CARD_STYLE = """
    QWidget#setCard {
        background: rgba(22, 27, 34, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
    }
    QWidget#setCard:hover {
        border-color: rgba(0, 212, 255, 0.3);
    }
"""


class SetCard(QWidget):
    """A single row/card for a historical set."""

    clicked = pyqtSignal(str)  # history_id
    delete_requested = pyqtSignal(str)  # history_id

    def __init__(self, data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("setCard")
        self.setStyleSheet(SET_CARD_STYLE)
        self._history_id = data["id"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Top row: name + date
        top = QHBoxLayout()
        name_label = QLabel(data["name"])
        name_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 600;")
        top.addWidget(name_label)
        top.addStretch()

        date_str = data["created_at"][:10] if data["created_at"] else ""
        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #64748b; font-size: 10px;")
        top.addWidget(date_label)

        delete_btn = QPushButton("x")
        delete_btn.setFixedSize(20, 20)
        delete_btn.setStyleSheet(
            "background: transparent; color: #64748b; border: none; font-size: 12px;"
        )
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._history_id))
        top.addWidget(delete_btn)
        layout.addLayout(top)

        # Bottom row: stats
        track_count = data.get("track_count", 0) or 0
        duration = data.get("duration_minutes", 0) or 0
        avg_compat = data.get("avg_compatibility", 0) or 0
        profile = data.get("energy_profile", "") or ""

        stats = f"{track_count} tracks | {duration:.0f} min"
        if avg_compat > 0:
            stats += f" | avg: {avg_compat:.2f}"
        if profile:
            stats += f" | {profile}"

        stats_label = QLabel(stats)
        stats_label.setStyleSheet("color: #64748b; font-size: 10px;")
        layout.addWidget(stats_label)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._history_id)
        super().mousePressEvent(event)


class HistoryPanel(QWidget):
    """Panel showing set history and analytics."""

    set_load_requested = pyqtSignal(str)  # history_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)
        self._history_store: HistoryStore | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header_row = QHBoxLayout()
        header = QLabel("Set History")
        header.setStyleSheet("color: #f1f5f9; font-size: 14px; font-weight: 600;")
        header_row.addWidget(header)
        header_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(
            "background: rgba(0, 212, 255, 0.1); color: #00D4FF; border: none;"
            "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
        )
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Scrollable set list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_widget = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(6)
        self._scroll_layout.addStretch()
        self._scroll.setWidget(self._scroll_widget)
        layout.addWidget(self._scroll, stretch=1)

        # Analytics section
        analytics_header = QLabel("Analytics")
        analytics_header.setStyleSheet("color: #f1f5f9; font-size: 13px; font-weight: 600;")
        layout.addWidget(analytics_header)

        # Most used tracks
        most_used_label = QLabel("Most Used Tracks")
        most_used_label.setStyleSheet("color: #94a3b8; font-size: 10px;")
        layout.addWidget(most_used_label)
        self._bar_chart = BarChart()
        self._bar_chart.setMaximumHeight(120)
        layout.addWidget(self._bar_chart)

        # Key distribution
        key_label = QLabel("Key Distribution")
        key_label.setStyleSheet("color: #94a3b8; font-size: 10px;")
        layout.addWidget(key_label)
        self._pie_chart = PieChart()
        self._pie_chart.setFixedHeight(100)
        layout.addWidget(self._pie_chart)

        # Compatibility trend
        trend_label = QLabel("Avg Compatibility Over Time")
        trend_label.setStyleSheet("color: #94a3b8; font-size: 10px;")
        layout.addWidget(trend_label)
        self._line_chart = LineChart()
        self._line_chart.setMaximumHeight(80)
        layout.addWidget(self._line_chart)

    def set_history_store(self, store: HistoryStore) -> None:
        """Inject the history store dependency."""
        self._history_store = store
        self.refresh()

    def refresh(self) -> None:
        """Reload data from the history store."""
        if not self._history_store:
            return

        # Clear existing cards
        while self._scroll_layout.count() > 1:
            item = self._scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Load sets
        sets = self._history_store.get_all_sets()
        for s in sets:
            card = SetCard(s)
            card.clicked.connect(self._on_set_clicked)
            card.delete_requested.connect(self._on_set_delete)
            self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, card)

        # Load analytics
        self._refresh_analytics()

    def _refresh_analytics(self) -> None:
        if not self._history_store:
            return

        # Most used tracks (show track_id truncated for now — app.py can
        # resolve to real names when it has the track map)
        most_used = self._history_store.get_most_used_tracks(8)
        bar_data = [(str(m["track_id"])[:8], float(m["count"])) for m in most_used]
        self._bar_chart.set_data(bar_data)

        # Key distribution
        key_dist = self._history_store.get_key_distribution()
        pie_data = [(k, float(v)) for k, v in key_dist.items()]
        self._pie_chart.set_data(pie_data)

        # Compatibility trend
        trend = self._history_store.get_avg_compatibility_over_time()
        self._line_chart.set_values([v for _, v in trend])

    def _on_set_clicked(self, history_id: str) -> None:
        self.set_load_requested.emit(history_id)

    def _on_set_delete(self, history_id: str) -> None:
        if self._history_store:
            self._history_store.delete_set(history_id)
            self.refresh()
