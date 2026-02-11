"""Transition preview dialog — hear how two tracks mix together."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.models import Track

logger = logging.getLogger(__name__)


class DualWaveformWidget(QWidget):
    """Draws two waveforms side-by-side with crossfade region highlighted."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)
        self._waveform_a: list[float] = []
        self._waveform_b: list[float] = []
        self._crossfade_ratio: float = 0.3  # fraction of total shown as crossfade
        self._playhead_pos: float = 0.0  # 0.0 to 1.0

    def set_waveforms(
        self, waveform_a: list[float], waveform_b: list[float]
    ) -> None:
        self._waveform_a = waveform_a
        self._waveform_b = waveform_b
        self.update()

    def set_playhead(self, pos: float) -> None:
        self._playhead_pos = max(0.0, min(1.0, pos))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h // 2

        # Background
        painter.fillRect(0, 0, w, QColor("#0d1117"))

        # Crossfade region background
        cf_start = int(w * (0.5 - self._crossfade_ratio / 2))
        cf_end = int(w * (0.5 + self._crossfade_ratio / 2))
        painter.fillRect(cf_start, 0, cf_end - cf_start, h, QColor(255, 215, 0, 20))

        # Draw waveform A (left portion, fading out)
        if self._waveform_a:
            pen = QPen(QColor("#00D4FF"), 1)
            painter.setPen(pen)
            n = len(self._waveform_a)
            for i in range(min(n, w // 2 + cf_end - cf_start)):
                x = int(i / n * (w * 0.6))
                amp = self._waveform_a[i] * (h * 0.4)
                painter.drawLine(x, int(mid_y - amp), x, int(mid_y + amp))

        # Draw waveform B (right portion, fading in)
        if self._waveform_b:
            pen = QPen(QColor("#FF6B35"), 1)
            painter.setPen(pen)
            n = len(self._waveform_b)
            for i in range(min(n, w // 2 + cf_end - cf_start)):
                x = w - int((n - i) / n * (w * 0.6))
                amp = self._waveform_b[i] * (h * 0.4)
                painter.drawLine(x, int(mid_y - amp), x, int(mid_y + amp))

        # Crossfade boundary lines
        pen = QPen(QColor("#FFD700"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(cf_start, 0, cf_start, h)
        painter.drawLine(cf_end, 0, cf_end, h)

        # Label
        painter.setPen(QPen(QColor("#FFD700")))
        painter.drawText(cf_start + 4, 12, "crossfade")

        # Playhead
        if self._playhead_pos > 0:
            px = int(self._playhead_pos * w)
            pen = QPen(QColor("#FFFFFF"), 2)
            painter.setPen(pen)
            painter.drawLine(px, 0, px, h)

        painter.end()


class TransitionPreviewDialog(QDialog):
    """Dialog for previewing crossfade between two tracks."""

    def __init__(
        self,
        track_a: Track,
        track_b: Track,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transition Preview")
        self.setMinimumSize(550, 350)
        self.setStyleSheet("""
            QDialog { background: #0d1117; color: #f1f5f9; }
            QLabel { color: #f1f5f9; }
            QSlider::groove:horizontal {
                background: rgba(255,255,255,0.1); height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #00D4FF; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QComboBox {
                background: rgba(22, 27, 34, 0.8); color: #f1f5f9;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px; padding: 4px 10px;
            }
        """)

        self._track_a = track_a
        self._track_b = track_b
        self._audio_data: bytes = b""
        self._is_playing = False
        self._player = None
        self._audio_output = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        title_a = track_a.metadata.title or track_a.filename
        title_b = track_b.metadata.title or track_b.filename
        header = QLabel(f"Transition: {title_a[:25]} \u2192 {title_b[:25]}")
        header.setStyleSheet("font-size: 14px; font-weight: 600; padding: 4px 0;")
        layout.addWidget(header)

        # Track info row
        info_row = QHBoxLayout()
        info_a = QLabel(
            f"A: {track_a.dj_metrics.bpm:.0f} BPM | {track_a.dj_metrics.key}"
        )
        info_a.setStyleSheet("color: #00D4FF; font-size: 11px;")
        info_row.addWidget(info_a)
        info_row.addStretch()
        info_b = QLabel(
            f"B: {track_b.dj_metrics.bpm:.0f} BPM | {track_b.dj_metrics.key}"
        )
        info_b.setStyleSheet("color: #FF6B35; font-size: 11px;")
        info_row.addWidget(info_b)
        layout.addLayout(info_row)

        # BPM match info
        bpm_diff = abs(track_a.dj_metrics.bpm - track_b.dj_metrics.bpm)
        bpm_pct = (bpm_diff / min(track_a.dj_metrics.bpm, track_b.dj_metrics.bpm)) * 100
        if bpm_pct < 0.5:
            bpm_text = f"BPM match: {track_a.dj_metrics.bpm:.0f} = {track_b.dj_metrics.bpm:.0f}"
            bpm_color = "#22c55e"
        elif bpm_pct < 8:
            bpm_text = (
                f"BPM match: {track_a.dj_metrics.bpm:.0f} \u2192 "
                f"{track_b.dj_metrics.bpm:.0f} ({bpm_pct:.1f}% stretch)"
            )
            bpm_color = "#eab308"
        else:
            bpm_text = f"BPM: {track_a.dj_metrics.bpm:.0f} \u2192 {track_b.dj_metrics.bpm:.0f} (no sync)"
            bpm_color = "#ef4444"
        bpm_label = QLabel(bpm_text)
        bpm_label.setStyleSheet(f"color: {bpm_color}; font-size: 11px;")
        layout.addWidget(bpm_label)

        # Dual waveform
        self._waveform = DualWaveformWidget()
        layout.addWidget(self._waveform)

        # Crossfade length
        cf_row = QHBoxLayout()
        cf_row.addWidget(QLabel("Crossfade:"))
        self._cf_combo = QComboBox()
        for beats, label in [(8, "8 beats"), (16, "16 beats"), (32, "32 beats")]:
            secs = beats / (track_a.dj_metrics.bpm / 60)
            self._cf_combo.addItem(f"{label} ({secs:.1f}s)", secs)
        self._cf_combo.setCurrentIndex(1)  # Default 16 beats
        cf_row.addWidget(self._cf_combo)
        cf_row.addStretch()
        layout.addLayout(cf_row)

        # Mix point slider
        mix_row = QHBoxLayout()
        mix_row.addWidget(QLabel("Mix point:"))
        self._mix_slider = QSlider(Qt.Orientation.Horizontal)
        self._mix_slider.setRange(0, 100)
        self._mix_slider.setValue(50)
        mix_row.addWidget(self._mix_slider)
        layout.addLayout(mix_row)

        # Transport controls
        btn_row = QHBoxLayout()
        btn_style = """
            QPushButton {
                background: rgba(22, 27, 34, 0.6);
                color: #f1f5f9; border: 1px solid rgba(255,255,255,0.08);
                padding: 8px 16px; border-radius: 6px;
                font-size: 12px; font-weight: 500;
            }
            QPushButton:hover {
                border-color: rgba(0, 212, 255, 0.4);
                color: #00D4FF;
            }
        """

        self._generate_btn = QPushButton("Generate Preview")
        self._generate_btn.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            "stop:0 #00D4FF, stop:1 #0099cc);"
            "color: #07070b; border: none;"
            "padding: 8px 20px; border-radius: 6px;"
            "font-size: 13px; font-weight: 600;"
        )
        self._generate_btn.clicked.connect(self._on_generate)
        btn_row.addWidget(self._generate_btn)

        self._play_btn = QPushButton("Play")
        self._play_btn.setStyleSheet(btn_style)
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._on_play_pause)
        btn_row.addWidget(self._play_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setStyleSheet(btn_style)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            "background: transparent; color: #94a3b8;"
            "border: 1px solid rgba(255,255,255,0.08);"
            "padding: 8px 16px; border-radius: 6px;"
        )
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        # Status
        self._status = QLabel("Click 'Generate Preview' to create the crossfade mix.")
        self._status.setStyleSheet("color: #64748b; font-size: 11px; padding: 4px 0;")
        layout.addWidget(self._status)

    def _on_generate(self) -> None:
        """Generate the crossfade preview audio."""
        self._status.setText("Generating preview...")
        self._generate_btn.setEnabled(False)

        try:
            from rekordbox_creative.analysis.mixer import (
                generate_crossfade_preview,
                audio_to_pcm_bytes,
            )

            cf_secs = self._cf_combo.currentData() or 8.0

            # Determine mix points from structure data
            mix_a = self._track_a.structure.outro_start
            mix_b = self._track_b.structure.intro_end

            audio, sr = generate_crossfade_preview(
                self._track_a.file_path,
                self._track_b.file_path,
                mix_point_a=mix_a,
                mix_point_b=mix_b,
                crossfade_secs=cf_secs,
                bpm_a=self._track_a.dj_metrics.bpm,
                bpm_b=self._track_b.dj_metrics.bpm,
            )

            self._audio_data = audio_to_pcm_bytes(audio, sr)

            # Generate simple waveform visualization
            n_samples = len(audio)
            n_bars = 200
            chunk_size = max(1, n_samples // n_bars)
            waveform = []
            for i in range(n_bars):
                start = i * chunk_size
                end = min(start + chunk_size, n_samples)
                if start < n_samples:
                    waveform.append(float(abs(audio[start:end]).mean()))
                else:
                    waveform.append(0.0)

            # Split waveform into A and B for dual display
            mid = len(waveform) // 2
            self._waveform.set_waveforms(waveform[:mid], waveform[mid:])

            duration = n_samples / sr
            self._status.setText(
                f"Preview ready ({duration:.1f}s). Click Play to listen."
            )
            self._play_btn.setEnabled(True)
            self._stop_btn.setEnabled(True)

        except FileNotFoundError as e:
            self._status.setText(f"Audio file not found: {e}")
        except Exception as e:
            logger.exception("Failed to generate transition preview")
            self._status.setText(f"Generation failed: {e}")
        finally:
            self._generate_btn.setEnabled(True)

    def _on_play_pause(self) -> None:
        """Play or pause the generated preview."""
        if not self._audio_data:
            return

        if self._is_playing:
            self._stop_playback()
            self._play_btn.setText("Play")
            self._is_playing = False
            return

        try:
            from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

            fmt = QAudioFormat()
            fmt.setSampleRate(44100)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

            device = QMediaDevices.defaultAudioOutput()
            self._audio_output = QAudioSink(device, fmt)

            self._buffer = QBuffer()
            self._buffer.setData(QByteArray(self._audio_data))
            self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)

            self._audio_output.start(self._buffer)
            self._play_btn.setText("Pause")
            self._is_playing = True
            self._status.setText("Playing...")

        except Exception as e:
            logger.exception("Playback failed")
            self._status.setText(f"Playback error: {e}")

    def _on_stop(self) -> None:
        """Stop playback."""
        self._stop_playback()
        self._play_btn.setText("Play")
        self._is_playing = False
        self._status.setText("Stopped.")

    def _stop_playback(self) -> None:
        if self._audio_output:
            try:
                self._audio_output.stop()
            except Exception:
                pass
            self._audio_output = None

    def closeEvent(self, event) -> None:
        self._stop_playback()
        super().closeEvent(event)
