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

_SLIDER_STYLE = """
    QSlider::groove:horizontal {
        background: rgba(22, 27, 34, 0.6);
        height: 6px; border-radius: 3px;
        border: 1px solid rgba(255, 255, 255, 0.04);
    }
    QSlider::handle:horizontal {
        background: #00D4FF;
        width: 14px; height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        border: 2px solid rgba(0, 212, 255, 0.3);
    }
    QSlider::handle:horizontal:hover {
        background: #33DDFF;
        border-color: rgba(0, 212, 255, 0.5);
    }
    QSlider::sub-page:horizontal {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #00D4FF, stop:1 rgba(0, 212, 255, 0.3)
        );
        border-radius: 3px;
    }
"""

_THRESHOLD_SLIDER_STYLE = """
    QSlider::groove:horizontal {
        background: rgba(22, 27, 34, 0.6);
        height: 6px; border-radius: 3px;
        border: 1px solid rgba(255, 255, 255, 0.04);
    }
    QSlider::handle:horizontal {
        background: #FFD700;
        width: 14px; height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        border: 2px solid rgba(255, 215, 0, 0.3);
    }
    QSlider::handle:horizontal:hover {
        background: #ffe44d;
        border-color: rgba(255, 215, 0, 0.5);
    }
    QSlider::sub-page:horizontal {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #FFD700, stop:1 rgba(255, 215, 0, 0.3)
        );
        border-radius: 3px;
    }
"""


class WeightSlider(QWidget):
    """A labeled slider for adjusting a scoring weight (0.0 - 1.0)."""

    value_changed = pyqtSignal(str, float)  # name, value

    def __init__(self, name: str, label: str, initial: float = 0.0, parent=None):
        super().__init__(parent)
        self._name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self._label = QLabel(label)
        self._label.setFixedWidth(75)
        self._label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self._label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(initial * 100))
        self._slider.setStyleSheet(_SLIDER_STYLE)
        self._slider.valueChanged.connect(self._on_changed)
        layout.addWidget(self._slider)

        self._value_label = QLabel(f"{initial:.2f}")
        self._value_label.setFixedWidth(36)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._value_label.setStyleSheet(
            "color: #f1f5f9; font-size: 11px; font-family: 'JetBrains Mono', monospace;"
        )
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
        self.setStyleSheet("""
            QScrollArea { background: rgba(13, 17, 23, 0.92); border: none; }
        """)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self.setWidget(self._container)

        # Header
        header = QLabel("SETTINGS")
        header.setFont(QFont("Inter", 10, QFont.Weight.DemiBold))
        header.setStyleSheet(
            "color: #64748b; letter-spacing: 1.5px; padding: 4px 0 8px 0;"
        )
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
                background: transparent; color: #64748b;
                border: 1px solid rgba(255, 255, 255, 0.06);
                padding: 4px 10px; border-radius: 6px;
                font-size: 10px; font-weight: 500;
            }
            QPushButton:hover {
                border-color: rgba(0, 212, 255, 0.3);
                color: #f1f5f9;
            }
        """)
        reset_btn.clicked.connect(self._reset_weights)
        self._layout.addWidget(reset_btn)

        # Display settings
        self._add_section("Display")

        # Edge threshold
        threshold_row = QHBoxLayout()
        threshold_label = QLabel("Edge threshold")
        threshold_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        threshold_row.addWidget(threshold_label)
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(0, 100)
        self._threshold_slider.setValue(30)
        self._threshold_slider.setStyleSheet(_THRESHOLD_SLIDER_STYLE)
        self._threshold_slider.valueChanged.connect(self._on_threshold_changed)
        threshold_row.addWidget(self._threshold_slider)
        self._threshold_value = QLabel("0.30")
        self._threshold_value.setFixedWidth(36)
        self._threshold_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._threshold_value.setStyleSheet(
            "color: #FFD700; font-size: 11px; font-family: 'JetBrains Mono', monospace;"
        )
        threshold_row.addWidget(self._threshold_value)
        self._layout.addLayout(threshold_row)

        # Color by
        color_row = QHBoxLayout()
        color_label = QLabel("Color by")
        color_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        color_row.addWidget(color_label)
        self._color_combo = QComboBox()
        self._color_combo.addItems(["Key", "Cluster", "Energy"])
        self._color_combo.setStyleSheet("""
            QComboBox {
                background: rgba(22, 27, 34, 0.8);
                color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background: rgba(22, 27, 34, 0.96);
                color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                selection-background-color: rgba(0, 212, 255, 0.2);
            }
        """)
        self._color_combo.currentTextChanged.connect(
            lambda t: self.color_changed.emit(t.lower())
        )
        color_row.addWidget(self._color_combo)
        self._layout.addLayout(color_row)

        # Library
        self._add_section("Library")

        self._folder_label = QLabel("No folder selected")
        self._folder_label.setStyleSheet(
            "color: #64748b; font-size: 11px; padding: 2px 0;"
        )
        self._folder_label.setWordWrap(True)
        self._layout.addWidget(self._folder_label)

        folder_btn = QPushButton("Change Folder")
        folder_btn.setStyleSheet("""
            QPushButton {
                background: rgba(22, 27, 34, 0.6);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.06);
                padding: 6px 14px; border-radius: 6px;
                font-size: 11px; font-weight: 500;
            }
            QPushButton:hover {
                border-color: rgba(0, 212, 255, 0.3);
                color: #f1f5f9;
            }
        """)
        folder_btn.clicked.connect(self.folder_requested.emit)
        self._layout.addWidget(folder_btn)

        reanalyze_btn = QPushButton("Re-analyze All")
        reanalyze_btn.setStyleSheet("""
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
        reanalyze_btn.clicked.connect(self.reanalyze_requested.emit)
        self._layout.addWidget(reanalyze_btn)

    def _add_section(self, title: str) -> None:
        sep = QLabel(title.upper())
        sep.setFont(QFont("Inter", 9, QFont.Weight.DemiBold))
        sep.setStyleSheet(
            "color: #475569; letter-spacing: 1px; padding: 10px 0 4px 0;"
            "border-top: 1px solid rgba(255, 255, 255, 0.04);"
        )
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
