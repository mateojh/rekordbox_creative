"""Settings panel.

Allows the user to adjust scoring weights, edge threshold,
display options, and library settings.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class WeightSlider(QWidget):
    """A labeled slider for adjusting a scoring weight (0.0 - 1.0)."""

    value_changed = pyqtSignal(str, float)  # name, value

    def __init__(self, name: str, label: str, initial: float = 0.0, parent=None):
        super().__init__(parent)
        self._name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)

        self._label = QLabel(label)
        self._label.setFixedWidth(80)
        self._label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        layout.addWidget(self._label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(initial * 100))
        self._slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1A1A2E; height: 6px; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00D4FF; width: 12px; margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #00D4FF; border-radius: 3px;
            }
        """)
        self._slider.valueChanged.connect(self._on_changed)
        layout.addWidget(self._slider)

        self._value_label = QLabel(f"{initial:.2f}")
        self._value_label.setFixedWidth(36)
        self._value_label.setStyleSheet("color: #E0E0E0; font-size: 11px;")
        layout.addWidget(self._value_label)

    def _on_changed(self, val: int) -> None:
        fval = val / 100.0
        self._value_label.setText(f"{fval:.2f}")
        self.value_changed.emit(self._name, fval)

    def set_value(self, val: float) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(int(val * 100))
        self._value_label.setText(f"{val:.2f}")
        self._slider.blockSignals(False)

    def value(self) -> float:
        return self._slider.value() / 100.0


class SettingsPanel(QScrollArea):
    """Panel for adjusting application settings."""

    weights_changed = pyqtSignal(dict)  # {name: float}
    threshold_changed = pyqtSignal(float)
    layout_changed = pyqtSignal(str)
    color_changed = pyqtSignal(str)
    folder_requested = pyqtSignal()
    reanalyze_requested = pyqtSignal()

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
        header = QLabel("SETTINGS")
        header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.setStyleSheet("color: #00D4FF; padding: 8px;")
        self._layout.addWidget(header)

        # Scoring weights
        self._add_section("Scoring Weights")
        self._weight_sliders: dict[str, WeightSlider] = {}
        weights = [
            ("harmonic", "Harmonic", 0.30),
            ("bpm", "BPM", 0.25),
            ("energy", "Energy", 0.15),
            ("groove", "Groove", 0.10),
            ("frequency", "Frequency", 0.10),
            ("mix_quality", "Mix Quality", 0.10),
        ]
        for name, label, default in weights:
            slider = WeightSlider(name, label, default)
            slider.value_changed.connect(self._on_weight_changed)
            self._weight_sliders[name] = slider
            self._layout.addWidget(slider)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888888;
                border: 1px solid #333; padding: 3px 8px;
                border-radius: 3px; font-size: 10px;
            }
            QPushButton:hover { border-color: #00D4FF; color: #E0E0E0; }
        """)
        reset_btn.clicked.connect(self._reset_weights)
        self._layout.addWidget(reset_btn)

        # Display settings
        self._add_section("Display")

        # Edge threshold
        threshold_row = QHBoxLayout()
        threshold_label = QLabel("Edge threshold:")
        threshold_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        threshold_row.addWidget(threshold_label)
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(0, 100)
        self._threshold_slider.setValue(30)
        self._threshold_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1A1A2E; height: 6px; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFD700; width: 12px; margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self._threshold_slider.valueChanged.connect(self._on_threshold_changed)
        threshold_row.addWidget(self._threshold_slider)
        self._threshold_value = QLabel("0.30")
        self._threshold_value.setFixedWidth(36)
        self._threshold_value.setStyleSheet("color: #E0E0E0; font-size: 11px;")
        threshold_row.addWidget(self._threshold_value)
        self._layout.addLayout(threshold_row)

        # Color by
        color_row = QHBoxLayout()
        color_label = QLabel("Color by:")
        color_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        color_row.addWidget(color_label)
        self._color_combo = QComboBox()
        self._color_combo.addItems(["Key", "Cluster", "Energy"])
        self._color_combo.setStyleSheet(
            "background: #1A1A2E; color: #E0E0E0; border: 1px solid #333;"
        )
        self._color_combo.currentTextChanged.connect(
            lambda t: self.color_changed.emit(t.lower())
        )
        color_row.addWidget(self._color_combo)
        self._layout.addLayout(color_row)

        # Library
        self._add_section("Library")

        self._folder_label = QLabel("No folder selected")
        self._folder_label.setStyleSheet(
            "color: #888888; font-size: 11px; padding: 0 4px;"
        )
        self._folder_label.setWordWrap(True)
        self._layout.addWidget(self._folder_label)

        folder_btn = QPushButton("Change Folder")
        folder_btn.setStyleSheet("""
            QPushButton {
                background: #1A1A2E; color: #E0E0E0;
                border: 1px solid #333; padding: 4px 12px;
                border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { border-color: #00D4FF; }
        """)
        folder_btn.clicked.connect(self.folder_requested.emit)
        self._layout.addWidget(folder_btn)

        reanalyze_btn = QPushButton("Re-analyze All")
        reanalyze_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #FF6B35;
                border: 1px solid #FF6B35; padding: 4px 12px;
                border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background: #FF6B35; color: white; }
        """)
        reanalyze_btn.clicked.connect(self.reanalyze_requested.emit)
        self._layout.addWidget(reanalyze_btn)

    def _add_section(self, title: str) -> None:
        sep = QLabel(f"--- {title} ---")
        sep.setStyleSheet("color: #555555; font-size: 10px; padding-top: 8px;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(sep)

    def _on_weight_changed(self, _name: str, _val: float) -> None:
        weights = {n: s.value() for n, s in self._weight_sliders.items()}
        self.weights_changed.emit(weights)

    def _on_threshold_changed(self, val: int) -> None:
        fval = val / 100.0
        self._threshold_value.setText(f"{fval:.2f}")
        self.threshold_changed.emit(fval)

    def _reset_weights(self) -> None:
        defaults = {
            "harmonic": 0.30, "bpm": 0.25, "energy": 0.15,
            "groove": 0.10, "frequency": 0.10, "mix_quality": 0.10,
        }
        for name, val in defaults.items():
            self._weight_sliders[name].set_value(val)
        self.weights_changed.emit(defaults)

    def set_folder(self, path: str) -> None:
        self._folder_label.setText(path)

    def set_threshold(self, val: float) -> None:
        self._threshold_slider.blockSignals(True)
        self._threshold_slider.setValue(int(val * 100))
        self._threshold_value.setText(f"{val:.2f}")
        self._threshold_slider.blockSignals(False)

    def set_weights(self, weights: dict[str, float]) -> None:
        for name, val in weights.items():
            if name in self._weight_sliders:
                self._weight_sliders[name].set_value(val)
