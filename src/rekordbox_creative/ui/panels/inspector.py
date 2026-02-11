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
from rekordbox_creative.ui.widgets.tag_chips import TagChipRow


def _bar_gradient(color: str) -> str:
    """Build a QProgressBar stylesheet with a custom accent color."""
    return f"""
        QProgressBar {{
            background: rgba(22, 27, 34, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 4px;
            text-align: center;
            color: #94a3b8;
            font-size: 10px;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {color}, stop:1 {color}80
            );
            border-radius: 3px;
        }}
    """


class MetricBar(QWidget):
    """A labeled progress bar for displaying a 0-1 metric."""

    def __init__(self, label: str, color: str = "#00D4FF", parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        self._label = QLabel(label)
        self._label.setFixedWidth(80)
        self._label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(True)
        self._bar.setFixedHeight(16)
        self._bar.setStyleSheet(_bar_gradient(color))
        layout.addWidget(self._label)
        layout.addWidget(self._bar)

    def set_value(self, value: float) -> None:
        self._bar.setValue(int(value * 100))
        self._bar.setFormat(f"{value:.2f}")


class InspectorPanel(QScrollArea):
    """Side panel showing selected track's full details."""

    @property
    def tag_row(self) -> TagChipRow:
        """Expose the tag chip row for external signal connections."""
        return self._tag_row

    def set_tags(self, tags: list[dict]) -> None:
        """Update the tag chips displayed for the current track."""
        self._tag_row.set_tags(tags)

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
        self._header = QLabel("INSPECTOR")
        self._header.setFont(QFont("Inter", 10, QFont.Weight.DemiBold))
        self._header.setStyleSheet(
            "color: #64748b; letter-spacing: 1.5px; padding: 4px 0 8px 0;"
        )
        self._layout.addWidget(self._header)

        # Placeholder
        self._placeholder = QLabel("Select a track to inspect")
        self._placeholder.setStyleSheet("color: #475569; padding: 16px 0;")
        self._placeholder.setWordWrap(True)
        self._layout.addWidget(self._placeholder)

        # Details container (hidden until track selected)
        self._details = QWidget()
        self._details_layout = QVBoxLayout(self._details)
        self._details_layout.setSpacing(4)
        self._details_layout.setContentsMargins(0, 0, 0, 0)
        self._details.setVisible(False)
        self._layout.addWidget(self._details)

        self._title_label = QLabel()
        self._title_label.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        self._title_label.setStyleSheet("color: #f1f5f9; padding-bottom: 2px;")
        self._title_label.setWordWrap(True)
        self._details_layout.addWidget(self._title_label)

        self._artist_label = QLabel()
        self._artist_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self._details_layout.addWidget(self._artist_label)

        self._duration_label = QLabel()
        self._duration_label.setStyleSheet(
            "color: #64748b; font-size: 11px; padding-bottom: 4px;"
        )
        self._details_layout.addWidget(self._duration_label)

        self._add_separator("DJ Metrics")

        self._bpm_label = QLabel()
        self._bpm_label.setStyleSheet("color: #f1f5f9; font-size: 12px;")
        self._details_layout.addWidget(self._bpm_label)

        self._key_label = QLabel()
        self._key_label.setStyleSheet("color: #f1f5f9; font-size: 12px;")
        self._details_layout.addWidget(self._key_label)

        self._groove_label = QLabel()
        self._groove_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._details_layout.addWidget(self._groove_label)

        self._freq_label = QLabel()
        self._freq_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._details_layout.addWidget(self._freq_label)

        self._mix_in_bar = MetricBar("Mix-In", "#22c55e")
        self._details_layout.addWidget(self._mix_in_bar)

        self._mix_out_bar = MetricBar("Mix-Out", "#22c55e")
        self._details_layout.addWidget(self._mix_out_bar)

        self._add_separator("Audio Features")

        self._energy_bar = MetricBar("Energy", "#ef4444")
        self._details_layout.addWidget(self._energy_bar)
        self._dance_bar = MetricBar("Dance", "#eab308")
        self._details_layout.addWidget(self._dance_bar)
        self._valence_bar = MetricBar("Valence", "#f97316")
        self._details_layout.addWidget(self._valence_bar)
        self._acoustic_bar = MetricBar("Acoustic", "#22BBAA")
        self._details_layout.addWidget(self._acoustic_bar)
        self._instrum_bar = MetricBar("Instrum.", "#4488FF")
        self._details_layout.addWidget(self._instrum_bar)
        self._live_bar = MetricBar("Liveness", "#AA44FF")
        self._details_layout.addWidget(self._live_bar)

        # Tags section
        self._add_separator("Tags")
        self._tag_row = TagChipRow()
        self._details_layout.addWidget(self._tag_row)

        self._add_separator("Structure")
        self._structure_label = QLabel()
        self._structure_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._structure_label.setWordWrap(True)
        self._details_layout.addWidget(self._structure_label)

    def _add_separator(self, title: str) -> None:
        sep = QLabel(title.upper())
        sep.setFont(QFont("Inter", 9, QFont.Weight.DemiBold))
        sep.setStyleSheet(
            "color: #475569; letter-spacing: 1px; padding: 10px 0 4px 0;"
            "border-top: 1px solid rgba(255, 255, 255, 0.04);"
        )
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
