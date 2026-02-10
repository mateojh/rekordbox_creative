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


class PlaylistTrackItem(QWidget):
    """A single track row in the playlist."""

    remove_clicked = pyqtSignal(object)  # UUID

    def __init__(self, track: Track, position: int, compat_score: float | None = None,
                 parent=None):
        super().__init__(parent)
        self.track = track

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        # Position
        pos_label = QLabel(f"{position + 1}.")
        pos_label.setFixedWidth(24)
        pos_label.setStyleSheet("color: #FFD700; font-size: 11px; font-weight: bold;")
        layout.addWidget(pos_label)

        # Track info
        info = QVBoxLayout()
        info.setSpacing(0)
        title = track.metadata.title or track.filename
        name_label = QLabel(title[:28])
        name_label.setStyleSheet("color: #E0E0E0; font-size: 11px;")
        info.addWidget(name_label)

        detail = f"{track.dj_metrics.bpm:.0f} BPM  {track.dj_metrics.key}"
        detail_label = QLabel(detail)
        detail_label.setStyleSheet("color: #888888; font-size: 10px;")
        info.addWidget(detail_label)
        layout.addLayout(info)

        layout.addStretch()

        # Compatibility arrow (if not first)
        if compat_score is not None:
            arrow = QLabel(f"  {compat_score:.2f}")
            arrow.setStyleSheet("color: #00D4FF; font-size: 10px;")
            layout.addWidget(arrow)

        # Remove button
        remove_btn = QPushButton("x")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #FF6B35;
                border: 1px solid #FF6B35; border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover { background: #FF6B35; color: white; }
        """)
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(track.id))
        layout.addWidget(remove_btn)


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
        self.setStyleSheet("QScrollArea { background: #0F0F23; border: none; }")

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.setSpacing(4)
        self.setWidget(self._container)

        # Header
        header = QLabel("CURRENT SET")
        header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.setStyleSheet("color: #00D4FF; padding: 8px;")
        self._layout.addWidget(header)

        # Stats
        self._stats_label = QLabel("0 tracks | 0:00")
        self._stats_label.setStyleSheet("color: #888888; font-size: 11px; padding: 0 8px;")
        self._layout.addWidget(self._stats_label)

        self._compat_label = QLabel("Avg compatibility: --")
        self._compat_label.setStyleSheet("color: #888888; font-size: 11px; padding: 0 8px;")
        self._layout.addWidget(self._compat_label)

        # Buttons
        btn_row = QHBoxLayout()
        self._optimize_btn = QPushButton("Optimize Order")
        self._optimize_btn.setStyleSheet("""
            QPushButton {
                background: #00D4FF; color: #000; border: none;
                padding: 4px 12px; border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background: #33DDFF; }
        """)
        self._optimize_btn.clicked.connect(self.optimize_requested.emit)
        btn_row.addWidget(self._optimize_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #FF6B35;
                border: 1px solid #FF6B35; padding: 4px 12px;
                border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background: #FF6B35; color: white; }
        """)
        self._clear_btn.clicked.connect(self.clear_requested.emit)
        btn_row.addWidget(self._clear_btn)
        self._layout.addLayout(btn_row)

        # Track list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: #0F0F23; border: none; outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #1A1A2E; padding: 2px;
            }
            QListWidget::item:selected { background: #16213E; }
        """)
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._layout.addWidget(self._list)

        # Export buttons
        export_row = QHBoxLayout()
        for fmt in ["M3U", "XML", "CSV"]:
            btn = QPushButton(f"Export {fmt}")
            btn.setStyleSheet("""
                QPushButton {
                    background: #1A1A2E; color: #E0E0E0;
                    border: 1px solid #333; padding: 3px 8px;
                    border-radius: 3px; font-size: 10px;
                }
                QPushButton:hover { border-color: #00D4FF; }
            """)
            btn.clicked.connect(lambda checked, f=fmt.lower(): self.export_requested.emit(f))
            export_row.addWidget(btn)
        self._layout.addLayout(export_row)

        # Segment controls (SET-005)
        seg_row = QHBoxLayout()
        add_seg_btn = QPushButton("+ Add Segment")
        add_seg_btn.setStyleSheet("""
            QPushButton {
                background: #1A1A2E; color: #E0E0E0;
                border: 1px solid #333; padding: 3px 8px;
                border-radius: 3px; font-size: 10px;
            }
            QPushButton:hover { border-color: #FFD700; color: #FFD700; }
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
        # Re-render the list with segment labels
        # For simplicity, just update the existing items' labels
        for seg_name, start, _end in self._segments:
            if start < self._list.count():
                item = self._list.item(start)
                if item:
                    widget = self._list.itemWidget(item)
                    if widget:
                        # Find the position label and prepend segment name
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
