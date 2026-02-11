"""Playlist/set panel (UI-010).

Shows the current set sequence. Tracks can be reordered, added, removed.
Displays total time, average compatibility, and supports auto-order.
"""

from __future__ import annotations

from uuid import UUID

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.models import Track


def _compat_color(score: float) -> str:
    """Color for compatibility score connector."""
    if score >= 0.8:
        return "#22c55e"
    if score >= 0.6:
        return "#eab308"
    if score >= 0.4:
        return "#f97316"
    return "#ef4444"


class PlaylistTrackItem(QWidget):
    """A single track row in the playlist."""

    remove_clicked = pyqtSignal(object)  # UUID

    def __init__(self, track: Track, position: int, compat_score: float | None = None,
                 parent=None):
        super().__init__(parent)
        self.track = track

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Compatibility connector (shown above each track except first)
        if compat_score is not None:
            color = _compat_color(compat_score)
            connector = QLabel(f"  {compat_score:.2f}")
            connector.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: 600;"
                f"padding: 0 0 2px 20px;"
                f"border-left: 2px solid {color};"
                f"margin-left: 8px;"
            )
            layout.addWidget(connector)

        # Track row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        # Position badge
        pos_label = QLabel(f"{position + 1}")
        pos_label.setFixedSize(22, 22)
        pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pos_label.setStyleSheet(
            "color: #07070b; font-size: 11px; font-weight: 700;"
            "background: #FFD700; border-radius: 11px;"
        )
        row.addWidget(pos_label)

        # Track info
        info = QVBoxLayout()
        info.setSpacing(0)
        title = track.metadata.title or track.filename
        name_label = QLabel(title[:28])
        name_label.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 500;")
        info.addWidget(name_label)

        detail = f"{track.dj_metrics.bpm:.0f} BPM  {track.dj_metrics.key}"
        detail_label = QLabel(detail)
        detail_label.setStyleSheet("color: #64748b; font-size: 10px;")
        info.addWidget(detail_label)
        row.addLayout(info)

        row.addStretch()

        # Remove button
        remove_btn = QPushButton("\u00d7")
        remove_btn.setFixedSize(22, 22)
        remove_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #64748b;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 11px; font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.15);
                color: #ef4444; border-color: #ef4444;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(track.id))
        row.addWidget(remove_btn)

        layout.addLayout(row)


class PlaylistPanel(QScrollArea):
    """Panel showing the current set sequence."""

    track_removed = pyqtSignal(object)  # UUID
    optimize_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    export_requested = pyqtSignal(str)  # format
    segment_added = pyqtSignal(str, int, int)  # name, start, end

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
        header = QLabel("CURRENT SET")
        header.setFont(QFont("Inter", 10, QFont.Weight.DemiBold))
        header.setStyleSheet(
            "color: #64748b; letter-spacing: 1.5px; padding: 4px 0 8px 0;"
        )
        self._layout.addWidget(header)

        # Stats
        self._stats_label = QLabel("0 tracks | 0:00")
        self._stats_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self._layout.addWidget(self._stats_label)

        self._compat_label = QLabel("Avg compatibility: --")
        self._compat_label.setStyleSheet(
            "color: #64748b; font-size: 11px; padding-bottom: 4px;"
        )
        self._layout.addWidget(self._compat_label)

        # Buttons
        btn_row = QHBoxLayout()
        self._optimize_btn = QPushButton("Optimize Order")
        self._optimize_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00D4FF, stop:1 #0099cc
                );
                color: #07070b; border: none;
                padding: 6px 14px; border-radius: 6px;
                font-size: 11px; font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #33DDFF, stop:1 #00bbee
                );
            }
        """)
        self._optimize_btn.clicked.connect(self.optimize_requested.emit)
        btn_row.addWidget(self._optimize_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.3);
                padding: 6px 14px; border-radius: 6px;
                font-size: 11px; font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.12);
                border-color: #ef4444;
            }
        """)
        self._clear_btn.clicked.connect(self.clear_requested.emit)
        btn_row.addWidget(self._clear_btn)
        self._layout.addLayout(btn_row)

        # Track list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: transparent; border: none; outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
                padding: 0;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: rgba(0, 212, 255, 0.06);
            }
        """)
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._layout.addWidget(self._list)

        # Export buttons
        export_row = QHBoxLayout()
        for fmt in ["M3U", "XML", "CSV"]:
            btn = QPushButton(f"Export {fmt}")
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(22, 27, 34, 0.6);
                    color: #94a3b8;
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    padding: 4px 10px; border-radius: 6px;
                    font-size: 10px; font-weight: 500;
                }
                QPushButton:hover {
                    border-color: rgba(0, 212, 255, 0.3);
                    color: #f1f5f9;
                }
            """)
            btn.clicked.connect(lambda checked, f=fmt.lower(): self.export_requested.emit(f))
            export_row.addWidget(btn)
        self._layout.addLayout(export_row)

        # Segment controls (SET-005)
        seg_row = QHBoxLayout()
        add_seg_btn = QPushButton("+ Add Segment")
        add_seg_btn.setStyleSheet("""
            QPushButton {
                background: rgba(22, 27, 34, 0.6);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.06);
                padding: 4px 10px; border-radius: 6px;
                font-size: 10px; font-weight: 500;
            }
            QPushButton:hover {
                border-color: rgba(255, 215, 0, 0.3);
                color: #FFD700;
            }
        """)
        add_seg_btn.clicked.connect(self._on_add_segment)
        seg_row.addWidget(add_seg_btn)
        self._layout.addLayout(seg_row)

        self._tracks: list[Track] = []
        self._segments: list[tuple[str, int, int]] = []  # (name, start, end)

    def update_set(
        self, tracks: list[Track], compat_scores: list[float | None] | None = None
    ) -> None:
        """Refresh the playlist display."""
        self._tracks = tracks
        self._list.clear()

        if not tracks:
            self._stats_label.setText("0 tracks | 0:00")
            self._compat_label.setText("Avg compatibility: --")
            return

        total_secs = sum(t.duration_seconds for t in tracks)
        mins = int(total_secs) // 60
        secs = int(total_secs) % 60
        self._stats_label.setText(f"{len(tracks)} tracks | {mins}:{secs:02d}")

        scores = compat_scores or [None] * len(tracks)
        valid_scores = [s for s in scores if s is not None]
        if valid_scores:
            avg = sum(valid_scores) / len(valid_scores)
            self._compat_label.setText(f"Avg compatibility: {avg:.2f}")
        else:
            self._compat_label.setText("Avg compatibility: --")

        for i, track in enumerate(tracks):
            score = scores[i] if i > 0 else None
            widget = PlaylistTrackItem(track, i, score)
            widget.remove_clicked.connect(self._on_remove)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def _on_remove(self, track_id: UUID) -> None:
        self.track_removed.emit(track_id)

    def _on_add_segment(self) -> None:
        """Add a segment label to a range of tracks (SET-005)."""
        if len(self._tracks) < 2:
            return

        name, ok = QInputDialog.getText(
            self, "Add Segment", "Segment name (e.g., Opener, Peak Time):"
        )
        if not ok or not name:
            return

        # Use currently selected items as range, or default to all
        selected = self._list.selectedIndexes()
        if len(selected) >= 2:
            rows = sorted(idx.row() for idx in selected)
            start, end = rows[0], rows[-1]
        else:
            start, end = 0, len(self._tracks) - 1

        self._segments.append((name, start, end))
        self.segment_added.emit(name, start, end)
        self._refresh_segment_labels()

    def _refresh_segment_labels(self) -> None:
        """Insert segment headers in the list widget."""
        for seg_name, start, _end in self._segments:
            if start < self._list.count():
                item = self._list.item(start)
                if item:
                    widget = self._list.itemWidget(item)
                    if widget:
                        for child in widget.findChildren(QLabel):
                            if child.styleSheet() and "FFD700" in child.styleSheet():
                                current = child.text()
                                if seg_name not in current:
                                    child.setText(f"[{seg_name}] {current}")
                                break

    def get_segments(self) -> list[tuple[str, int, int]]:
        """Return the current segment definitions."""
        return list(self._segments)

    def clear_segments(self) -> None:
        """Remove all segment labels."""
        self._segments.clear()
