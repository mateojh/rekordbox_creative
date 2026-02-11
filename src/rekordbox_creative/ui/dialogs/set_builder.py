"""Set builder dialog — configure and generate smart DJ sets."""

from __future__ import annotations

from uuid import UUID

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.models import (
    EnergyProfile,
    SetBuilderConfig,
    Track,
)
from rekordbox_creative.suggestions.set_generator import ENERGY_CURVES, _interpolate_energy


class EnergyCurvePreview(QWidget):
    """Small widget that draws the energy curve preview."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(80)
        self._curve: list[tuple[float, float]] = []
        self._track_dots: list[tuple[float, float]] = []  # (position, energy)

    def set_curve(self, profile: EnergyProfile) -> None:
        self._curve = ENERGY_CURVES.get(profile, [])
        self.update()

    def set_track_dots(self, dots: list[tuple[float, float]]) -> None:
        self._track_dots = dots
        self.update()

    def paintEvent(self, event) -> None:
        if not self._curve:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#0d1117"))

        # Draw curve
        pen = QPen(QColor("#00D4FF"), 2)
        painter.setPen(pen)
        points = 100
        prev_x, prev_y = 0, 0
        for i in range(points + 1):
            pos = i / points
            energy = _interpolate_energy(self._curve, pos)
            x = int(pos * w)
            y = int(h - energy * h * 0.9 - h * 0.05)
            if i > 0:
                painter.drawLine(prev_x, prev_y, x, y)
            prev_x, prev_y = x, y

        # Draw track dots
        pen = QPen(QColor("#FFD700"), 1)
        painter.setPen(pen)
        painter.setBrush(QColor("#FFD700"))
        for pos, energy in self._track_dots:
            x = int(pos * w)
            y = int(h - energy * h * 0.9 - h * 0.05)
            painter.drawEllipse(x - 3, y - 3, 6, 6)

        painter.end()


class SetBuilderDialog(QDialog):
    """Dialog for configuring and generating a smart DJ set."""

    def __init__(
        self,
        tracks: list[Track],
        selected_track: Track | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Build Smart Set")
        self.setMinimumSize(420, 400)
        self.setStyleSheet("""
            QDialog { background: #0d1117; color: #f1f5f9; }
            QLabel { color: #f1f5f9; }
            QComboBox {
                background: rgba(22, 27, 34, 0.8); color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px; padding: 6px 10px;
            }
            QComboBox QAbstractItemView {
                background: rgba(22, 27, 34, 0.96); color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                selection-background-color: rgba(0, 212, 255, 0.2);
            }
            QRadioButton { color: #94a3b8; font-size: 11px; spacing: 6px; }
            QRadioButton::indicator { width: 14px; height: 14px; }
            QRadioButton::indicator:checked { background: #00D4FF; border-radius: 7px; }
            QRadioButton::indicator:unchecked {
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 7px; background: transparent;
            }
        """)

        self._tracks = tracks
        self._selected_track = selected_track
        self._config: SetBuilderConfig | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel("Build Smart Set")
        header.setStyleSheet("font-size: 16px; font-weight: 600; padding: 4px 0;")
        layout.addWidget(header)

        # Start track
        start_row = QHBoxLayout()
        start_row.addWidget(QLabel("Start Track:"))
        self._start_combo = QComboBox()
        self._start_combo.addItem("Auto (best fit)", None)
        for track in sorted(tracks, key=lambda t: t.metadata.title or t.filename):
            title = track.metadata.title or track.filename
            self._start_combo.addItem(
                f"{title[:30]} ({track.dj_metrics.bpm:.0f} {track.dj_metrics.key})",
                str(track.id),
            )
        if selected_track:
            for i in range(self._start_combo.count()):
                if self._start_combo.itemData(i) == str(selected_track.id):
                    self._start_combo.setCurrentIndex(i)
                    break
        start_row.addWidget(self._start_combo)
        layout.addLayout(start_row)

        # Set length
        length_label = QLabel("Set Length:")
        length_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        layout.addWidget(length_label)

        length_row = QHBoxLayout()
        self._length_group = QButtonGroup(self)
        btn_style = """
            QPushButton {
                background: rgba(22, 27, 34, 0.6);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.06);
                padding: 6px 16px; border-radius: 6px;
                font-size: 12px; font-weight: 500;
            }
            QPushButton:checked {
                background: rgba(0, 212, 255, 0.15);
                color: #00D4FF;
                border-color: rgba(0, 212, 255, 0.4);
            }
        """
        for minutes in [30, 60, 90, 120]:
            btn = QPushButton(f"{minutes} min")
            btn.setCheckable(True)
            btn.setStyleSheet(btn_style)
            if minutes == 60:
                btn.setChecked(True)
            self._length_group.addButton(btn, minutes)
            length_row.addWidget(btn)
        layout.addLayout(length_row)

        # Energy profile
        energy_label = QLabel("Energy Profile:")
        energy_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        layout.addWidget(energy_label)

        self._profile_group = QButtonGroup(self)
        profiles = [
            (EnergyProfile.WARM_UP_PEAK_COOL, "Warm-Up \u2192 Peak \u2192 Cool-Down"),
            (EnergyProfile.HIGH_ENERGY, "High Energy"),
            (EnergyProfile.CHILL_LOUNGE, "Chill / Lounge"),
            (EnergyProfile.ROLLERCOASTER, "Rollercoaster"),
        ]
        for i, (profile, label) in enumerate(profiles):
            radio = QRadioButton(label)
            if i == 0:
                radio.setChecked(True)
            self._profile_group.addButton(radio, i)
            layout.addWidget(radio)
        self._profiles = [p for p, _ in profiles]

        self._profile_group.buttonClicked.connect(self._on_profile_changed)

        # Energy curve preview
        self._curve_preview = EnergyCurvePreview()
        self._curve_preview.set_curve(EnergyProfile.WARM_UP_PEAK_COOL)
        layout.addWidget(self._curve_preview)

        # Generate button
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "background: transparent; color: #94a3b8;"
            "border: 1px solid rgba(255,255,255,0.08);"
            "padding: 8px 20px; border-radius: 6px;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        gen_btn = QPushButton("Generate Set")
        gen_btn.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            "stop:0 #00D4FF, stop:1 #0099cc);"
            "color: #07070b; border: none;"
            "padding: 8px 24px; border-radius: 6px;"
            "font-size: 13px; font-weight: 600;"
        )
        gen_btn.clicked.connect(self._on_generate)
        btn_row.addWidget(gen_btn)
        layout.addLayout(btn_row)

    def _on_profile_changed(self) -> None:
        idx = self._profile_group.checkedId()
        if 0 <= idx < len(self._profiles):
            self._curve_preview.set_curve(self._profiles[idx])

    def _on_generate(self) -> None:
        # Build config
        start_id = self._start_combo.currentData()
        start_uuid = UUID(start_id) if start_id else None

        checked_btn = self._length_group.checkedButton()
        minutes = self._length_group.id(checked_btn) if checked_btn else 60

        profile_idx = self._profile_group.checkedId()
        profile = self._profiles[profile_idx] if 0 <= profile_idx < len(self._profiles) \
            else EnergyProfile.WARM_UP_PEAK_COOL

        self._config = SetBuilderConfig(
            start_track_id=start_uuid,
            target_minutes=minutes,
            energy_profile=profile,
        )
        self.accept()

    def get_config(self) -> SetBuilderConfig | None:
        return self._config
