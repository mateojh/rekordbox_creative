"""Track inspector panel (UI-008).

Shows selected track's full analysis: artist, title, BPM, key, energy,
danceability, valence, structure, and all other metrics.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.models import Track


class MetricBar(QWidget):
    """A labeled progress bar for displaying a 0-1 metric."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        self._label = QLabel(label)
        self._label.setFixedWidth(90)
        self._label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(True)
        self._bar.setFixedHeight(16)
        self._bar.setStyleSheet("""
            QProgressBar {
                background: #1A1A2E;
                border: 1px solid #333;
                border-radius: 3px;
                text-align: center;
                color: #E0E0E0;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background: #00D4FF;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self._label)
        layout.addWidget(self._bar)

    def set_value(self, value: float) -> None:
        self._bar.setValue(int(value * 100))
        self._bar.setFormat(f"{value:.2f}")


class InspectorPanel(QScrollArea):
    """Side panel showing selected track's full details."""

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
        self._header = QLabel("INSPECTOR")
        self._header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._header.setStyleSheet("color: #00D4FF; padding: 8px;")
        self._layout.addWidget(self._header)

        # Placeholder
        self._placeholder = QLabel("Select a track to inspect")
        self._placeholder.setStyleSheet("color: #888888; padding: 16px;")
        self._placeholder.setWordWrap(True)
        self._layout.addWidget(self._placeholder)

        # Details container (hidden until track selected)
        self._details = QWidget()
        self._details_layout = QVBoxLayout(self._details)
        self._details_layout.setSpacing(4)
        self._details.setVisible(False)
        self._layout.addWidget(self._details)

        self._title_label = QLabel()
        self._title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title_label.setStyleSheet("color: #E0E0E0;")
        self._title_label.setWordWrap(True)
        self._details_layout.addWidget(self._title_label)

        self._artist_label = QLabel()
        self._artist_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        self._details_layout.addWidget(self._artist_label)

        self._duration_label = QLabel()
        self._duration_label.setStyleSheet("color: #888888; font-size: 11px;")
        self._details_layout.addWidget(self._duration_label)

        self._add_separator("DJ Metrics")

        self._bpm_label = QLabel()
        self._bpm_label.setStyleSheet("color: #E0E0E0; font-size: 11px;")
        self._details_layout.addWidget(self._bpm_label)

        self._key_label = QLabel()
        self._key_label.setStyleSheet("color: #E0E0E0; font-size: 11px;")
        self._details_layout.addWidget(self._key_label)

        self._groove_label = QLabel()
        self._groove_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        self._details_layout.addWidget(self._groove_label)

        self._freq_label = QLabel()
        self._freq_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        self._details_layout.addWidget(self._freq_label)

        self._mix_in_bar = MetricBar("Mix-In")
        self._details_layout.addWidget(self._mix_in_bar)

        self._mix_out_bar = MetricBar("Mix-Out")
        self._details_layout.addWidget(self._mix_out_bar)

        self._add_separator("Audio Features")

        self._energy_bar = MetricBar("Energy")
        self._details_layout.addWidget(self._energy_bar)
        self._dance_bar = MetricBar("Dance")
        self._details_layout.addWidget(self._dance_bar)
        self._valence_bar = MetricBar("Valence")
        self._details_layout.addWidget(self._valence_bar)
        self._acoustic_bar = MetricBar("Acoustic")
        self._details_layout.addWidget(self._acoustic_bar)
        self._instrum_bar = MetricBar("Instrum.")
        self._details_layout.addWidget(self._instrum_bar)
        self._live_bar = MetricBar("Liveness")
        self._details_layout.addWidget(self._live_bar)

        self._add_separator("Structure")
        self._structure_label = QLabel()
        self._structure_label.setStyleSheet("color: #BBBBBB; font-size: 11px;")
        self._structure_label.setWordWrap(True)
        self._details_layout.addWidget(self._structure_label)

    def _add_separator(self, title: str) -> None:
        sep = QLabel(f"--- {title} ---")
        sep.setStyleSheet("color: #555555; font-size: 10px; padding-top: 6px;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._details_layout.addWidget(sep)

    def show_track(self, track: Track | None) -> None:
        """Display track details, or show placeholder if None."""
        if track is None:
            self._placeholder.setVisible(True)
            self._details.setVisible(False)
            return

        self._placeholder.setVisible(False)
        self._details.setVisible(True)

        title = track.metadata.title or track.filename
        artist = track.metadata.artist or "Unknown Artist"
        album = track.metadata.album or ""

        self._title_label.setText(title)
        self._artist_label.setText(artist + (f" - {album}" if album else ""))

        mins = int(track.duration_seconds) // 60
        secs = int(track.duration_seconds) % 60
        self._duration_label.setText(f"Duration: {mins}:{secs:02d}")

        dj = track.dj_metrics
        self._bpm_label.setText(
            f"BPM: {dj.bpm:.1f} (stability: {dj.bpm_stability:.2f})"
        )
        self._key_label.setText(
            f"Key: {dj.key} (confidence: {dj.key_confidence:.2f})"
        )
        self._groove_label.setText(
            f"Groove: {dj.groove_type.replace('_', ' ').title()}"
        )
        self._freq_label.setText(
            f"Frequency: {dj.frequency_weight.replace('_', ' ').title()}"
        )
        self._mix_in_bar.set_value(dj.mix_in_score)
        self._mix_out_bar.set_value(dj.mix_out_score)

        ss = track.spotify_style
        self._energy_bar.set_value(ss.energy)
        self._dance_bar.set_value(ss.danceability)
        self._valence_bar.set_value(ss.valence)
        self._acoustic_bar.set_value(ss.acousticness)
        self._instrum_bar.set_value(ss.instrumentalness)
        self._live_bar.set_value(ss.liveness)

        st = track.structure
        parts = []
        if st.drops:
            drop_str = ", ".join(
                f"{int(d) // 60}:{int(d) % 60:02d}" for d in st.drops
            )
            parts.append(f"Drops: {drop_str}")
        if st.vocal_segments:
            parts.append(f"Vocal segs: {len(st.vocal_segments)}")
        if st.intro_end is not None:
            parts.append(f"Intro end: {st.intro_end:.1f}s")
        if st.outro_start is not None:
            parts.append(f"Outro start: {st.outro_start:.1f}s")
        self._structure_label.setText(
            "\n".join(parts) if parts else "No structure data"
        )
