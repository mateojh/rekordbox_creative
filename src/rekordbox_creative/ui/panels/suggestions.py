"""Suggestion panel (UI-009).

Shows top N suggested tracks with scores, strategy selector, and filter controls.
Clicking a suggestion highlights it on the graph.
"""

from __future__ import annotations

from uuid import UUID

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.models import SuggestionResult, SuggestionStrategy, Track


def _score_color(score: float) -> str:
    """Return a hex color for a compatibility score."""
    if score >= 0.8:
        return "#22c55e"
    if score >= 0.6:
        return "#eab308"
    if score >= 0.4:
        return "#f97316"
    return "#ef4444"


class SuggestionItem(QWidget):
    """A single suggestion row showing track info and colored score badge."""

    def __init__(self, result: SuggestionResult, track: Track, rank: int, parent=None):
        super().__init__(parent)
        self.result = result
        self.track = track

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Rank
        rank_label = QLabel(f"{rank}")
        rank_label.setFixedWidth(18)
        rank_label.setStyleSheet("color: #475569; font-size: 12px; font-weight: 600;")
        layout.addWidget(rank_label)

        # Track info
        info = QVBoxLayout()
        info.setSpacing(1)
        title = track.metadata.title or track.filename
        name_label = QLabel(title[:32])
        name_label.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 500;")
        info.addWidget(name_label)

        artist = track.metadata.artist or ""
        detail = f"{track.dj_metrics.bpm:.0f} BPM | {track.dj_metrics.key}"
        if artist:
            detail = f"{artist[:20]} | {detail}"
        detail_label = QLabel(detail)
        detail_label.setStyleSheet("color: #64748b; font-size: 10px;")
        info.addWidget(detail_label)
        layout.addLayout(info)

        layout.addStretch()

        # Score badge with color
        color = _score_color(result.final_score)
        score_label = QLabel(f"{result.final_score:.2f}")
        score_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 700;"
            f"background: {color}18; padding: 2px 6px; border-radius: 4px;"
        )
        layout.addWidget(score_label)


class SuggestionPanel(QScrollArea):
    """Panel showing suggestions for the selected track."""

    strategy_changed = pyqtSignal(str)
    filters_changed = pyqtSignal(dict)
    suggestion_clicked = pyqtSignal(object)  # UUID

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(260)
        self.setMaximumWidth(350)
        self.setStyleSheet("""
            QScrollArea { background: rgba(13, 17, 23, 0.92); border: none; }
        """)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self.setWidget(self._container)

        # Header
        header = QLabel("SUGGESTIONS")
        header.setFont(QFont("Inter", 10, QFont.Weight.DemiBold))
        header.setStyleSheet(
            "color: #64748b; letter-spacing: 1.5px; padding: 4px 0 8px 0;"
        )
        self._layout.addWidget(header)

        self._for_label = QLabel("Select a track")
        self._for_label.setStyleSheet("color: #475569; font-size: 12px; padding: 0 0 4px 0;")
        self._layout.addWidget(self._for_label)

        # Strategy selector
        strat_row = QHBoxLayout()
        strat_label = QLabel("Strategy")
        strat_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        strat_row.addWidget(strat_label)
        self._strategy_combo = QComboBox()
        self._strategy_combo.setStyleSheet("""
            QComboBox {
                background: rgba(22, 27, 34, 0.8);
                color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none; width: 20px;
            }
            QComboBox QAbstractItemView {
                background: rgba(22, 27, 34, 0.96);
                color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                selection-background-color: rgba(0, 212, 255, 0.2);
            }
        """)
        for s in SuggestionStrategy:
            self._strategy_combo.addItem(
                s.value.replace("_", " ").title(), s.value
            )
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        strat_row.addWidget(self._strategy_combo)
        self._layout.addLayout(strat_row)

        # Filters
        filter_row1 = QHBoxLayout()
        bpm_label = QLabel("BPM")
        bpm_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        filter_row1.addWidget(bpm_label)
        spin_style = """
            QDoubleSpinBox {
                background: rgba(22, 27, 34, 0.8); color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px; padding: 2px 4px; font-size: 11px;
            }
        """
        self._bpm_min = QDoubleSpinBox()
        self._bpm_min.setRange(0, 300)
        self._bpm_min.setValue(0)
        self._bpm_min.setSpecialValueText("Min")
        self._bpm_min.setStyleSheet(spin_style)
        filter_row1.addWidget(self._bpm_min)
        self._bpm_max = QDoubleSpinBox()
        self._bpm_max.setRange(0, 300)
        self._bpm_max.setValue(0)
        self._bpm_max.setSpecialValueText("Max")
        self._bpm_max.setStyleSheet(spin_style)
        filter_row1.addWidget(self._bpm_max)
        self._layout.addLayout(filter_row1)

        filter_row2 = QHBoxLayout()
        cb_style = """
            QCheckBox {
                color: #94a3b8; font-size: 11px; spacing: 4px;
            }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                background: rgba(22, 27, 34, 0.6);
            }
            QCheckBox::indicator:checked {
                background: #00D4FF;
                border-color: #00D4FF;
            }
        """
        self._key_lock = QCheckBox("Key Lock")
        self._key_lock.setStyleSheet(cb_style)
        filter_row2.addWidget(self._key_lock)
        self._groove_lock = QCheckBox("Groove Lock")
        self._groove_lock.setStyleSheet(cb_style)
        filter_row2.addWidget(self._groove_lock)
        self._layout.addLayout(filter_row2)

        # Suggestion list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
                padding: 1px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: rgba(0, 212, 255, 0.08);
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.04);
            }
        """)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._layout.addWidget(self._list)

        self._results: list[tuple[SuggestionResult, Track]] = []

    def _on_strategy_changed(self, _index: int) -> None:
        strategy = self._strategy_combo.currentData()
        self.strategy_changed.emit(strategy)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if 0 <= row < len(self._results):
            result, track = self._results[row]
            self.suggestion_clicked.emit(track.id)

    def set_current_track(self, track: Track | None) -> None:
        """Update the 'for' label."""
        if track:
            name = track.metadata.title or track.filename
            self._for_label.setText(f'for "{name}"')
        else:
            self._for_label.setText("Select a track")

    def show_suggestions(
        self, results: list[SuggestionResult], track_map: dict[UUID, Track]
    ) -> None:
        """Display suggestion results."""
        self._list.clear()
        self._results.clear()

        for i, result in enumerate(results):
            track = track_map.get(result.track_id)
            if track is None:
                continue
            self._results.append((result, track))
            widget = SuggestionItem(result, track, i + 1)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def get_filters(self) -> dict:
        """Return current filter settings."""
        filters = {}
        bpm_min = self._bpm_min.value()
        bpm_max = self._bpm_max.value()
        if bpm_min > 0:
            filters["bpm_min"] = bpm_min
        if bpm_max > 0:
            filters["bpm_max"] = bpm_max
        if self._key_lock.isChecked():
            filters["key_lock"] = True
        if self._groove_lock.isChecked():
            filters["groove_lock"] = True
        return filters

    def get_strategy(self) -> str:
        return self._strategy_combo.currentData()
