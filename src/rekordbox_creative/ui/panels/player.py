"""Audio player panel with waveform visualization.

Shows waveform with playhead, transport controls, volume slider,
and structure markers from track analysis data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from rekordbox_creative.db.models import Track

logger = logging.getLogger(__name__)


class WaveformWidget(QWidget):
    """Custom widget that draws a waveform with playhead and structure markers."""

    seek_requested = pyqtSignal(float)  # position 0.0-1.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)
        self._samples: list[float] = []
        self._playhead: float = 0.0  # 0.0 to 1.0
        self._duration: float = 0.0
        self._drops: list[float] = []
        self._breakdowns: list[list[float]] = []
        self._intro_end: float | None = None
        self._outro_start: float | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_waveform(
        self,
        samples: list[float],
        duration: float,
        drops: list[float] | None = None,
        breakdowns: list[list[float]] | None = None,
        intro_end: float | None = None,
        outro_start: float | None = None,
    ) -> None:
        self._samples = samples
        self._duration = duration
        self._drops = drops or []
        self._breakdowns = breakdowns or []
        self._intro_end = intro_end
        self._outro_start = outro_start
        self.update()

    def set_playhead(self, position: float) -> None:
        """Set playhead position (0.0 to 1.0)."""
        self._playhead = max(0.0, min(1.0, position))
        self.update()

    def clear(self) -> None:
        self._samples = []
        self._playhead = 0.0
        self._duration = 0.0
        self._drops = []
        self._breakdowns = []
        self._intro_end = None
        self._outro_start = None
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._samples:
            pos = event.position().x() / self.width()
            self.seek_requested.emit(max(0.0, min(1.0, pos)))

    def paintEvent(self, event) -> None:
        if not self._samples:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h / 2

        # Background
        painter.fillRect(0, 0, w, h, QColor("#0d1117"))

        # Structure markers
        if self._duration > 0:
            # Breakdowns - blue tint
            for bd in self._breakdowns:
                if len(bd) >= 2:
                    x1 = int(bd[0] / self._duration * w)
                    x2 = int(bd[1] / self._duration * w)
                    painter.fillRect(x1, 0, x2 - x1, h, QColor(34, 170, 221, 25))

            # Intro/outro - green markers
            pen = QPen(QColor("#22c55e"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            if self._intro_end is not None:
                x = int(self._intro_end / self._duration * w)
                painter.drawLine(x, 0, x, h)
            if self._outro_start is not None:
                x = int(self._outro_start / self._duration * w)
                painter.drawLine(x, 0, x, h)

            # Drops - red markers
            pen = QPen(QColor("#ef4444"), 1.5)
            painter.setPen(pen)
            for drop in self._drops:
                x = int(drop / self._duration * w)
                painter.drawLine(x, 0, x, h)

        # Waveform bars
        n = len(self._samples)
        bar_width = max(1, w / n)
        playhead_x = int(self._playhead * w)

        for i, amp in enumerate(self._samples):
            x = int(i * w / n)
            bar_h = amp * (h * 0.8)

            # Color: cyan before playhead, dimmer after
            if x < playhead_x:
                color = QColor("#00D4FF")
            else:
                color = QColor(100, 116, 139, 150)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRect(int(x), int(mid_y - bar_h / 2), max(1, int(bar_width) - 1), int(bar_h))

        # Playhead line
        pen = QPen(QColor("#ffffff"), 2)
        painter.setPen(pen)
        painter.drawLine(playhead_x, 0, playhead_x, h)

        painter.end()


class PlayerPanel(QWidget):
    """Audio player with waveform display and transport controls."""

    play_state_changed = pyqtSignal(bool)  # True = playing
    track_changed = pyqtSignal(object)  # Track or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(140)
        self.setStyleSheet("""
            QWidget {
                background: rgba(13, 17, 23, 0.95);
                border-top: 1px solid rgba(255, 255, 255, 0.06);
            }
        """)

        self._current_track: Track | None = None
        self._player = None  # QMediaPlayer
        self._audio_output = None  # QAudioOutput
        self._is_playing = False
        self._waveform_cache = None  # WaveformCache
        self._waveform_worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)

        # Now Playing label
        self._now_playing = QLabel("No track loaded")
        self._now_playing.setStyleSheet(
            "color: #94a3b8; font-size: 11px; font-weight: 500; border: none;"
        )
        layout.addWidget(self._now_playing)

        # Waveform
        self._waveform = WaveformWidget()
        self._waveform.seek_requested.connect(self._on_seek)
        layout.addWidget(self._waveform)

        # Transport row
        transport = QHBoxLayout()
        transport.setSpacing(8)

        btn_style = """
            QPushButton {
                background: rgba(22, 27, 34, 0.8); color: #f1f5f9;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px; padding: 4px 12px; font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.12);
                border-color: rgba(0, 212, 255, 0.3);
            }
        """

        self._prev_btn = QPushButton("\u23ee")
        self._prev_btn.setFixedSize(36, 30)
        self._prev_btn.setStyleSheet(btn_style)
        transport.addWidget(self._prev_btn)

        self._play_btn = QPushButton("\u25b6")
        self._play_btn.setFixedSize(36, 30)
        self._play_btn.setStyleSheet(btn_style)
        self._play_btn.clicked.connect(self._toggle_play)
        transport.addWidget(self._play_btn)

        self._next_btn = QPushButton("\u23ed")
        self._next_btn.setFixedSize(36, 30)
        self._next_btn.setStyleSheet(btn_style)
        transport.addWidget(self._next_btn)

        # Time label
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
        transport.addWidget(self._time_label)

        transport.addStretch()

        # Volume
        vol_label = QLabel("\U0001f50a")
        vol_label.setStyleSheet("color: #64748b; font-size: 12px; border: none;")
        transport.addWidget(vol_label)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(80)
        self._volume_slider.setStyleSheet("""
            QSlider { border: none; }
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.08);
                height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #00D4FF; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: rgba(0, 212, 255, 0.4);
                border-radius: 2px;
            }
        """)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        transport.addWidget(self._volume_slider)

        layout.addLayout(transport)

        # Playhead update timer
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(33)  # ~30fps
        self._update_timer.timeout.connect(self._update_playhead)

        self._init_media_player()

    def _init_media_player(self) -> None:
        """Initialize QMediaPlayer + QAudioOutput."""
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._audio_output.setVolume(0.8)
            self._player.setAudioOutput(self._audio_output)
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        except ImportError:
            logger.warning("QtMultimedia not available — playback disabled")
            self._player = None
            self._audio_output = None

    def set_waveform_cache(self, cache) -> None:
        """Set the WaveformCache instance for lazy waveform generation."""
        self._waveform_cache = cache

    def load_track(self, track: Track) -> None:
        """Load a track for playback."""
        self._current_track = track
        title = track.metadata.title or track.filename
        artist = track.metadata.artist or ""
        bpm = f"{track.dj_metrics.bpm:.0f} BPM"
        key = track.dj_metrics.key
        display = f"{artist} - {title}" if artist else title
        self._now_playing.setText(f"\u25b6 {display}  {bpm} | {key}")

        # Load audio into player
        if self._player:
            path = Path(track.file_path)
            if path.exists():
                self._player.setSource(QUrl.fromLocalFile(str(path)))

        # Load or generate waveform
        self._load_waveform(track)

        self.track_changed.emit(track)

    def _load_waveform(self, track: Track) -> None:
        """Load waveform from cache or generate lazily."""
        if self._waveform_cache:
            cached = self._waveform_cache.get(track.id)
            if cached:
                samples, duration = cached
                self._set_waveform_display(track, samples, duration)
                return

        # Generate in background (deferred to avoid blocking UI)
        QTimer.singleShot(100, lambda: self._generate_waveform(track))

    def _generate_waveform(self, track: Track) -> None:
        """Generate waveform data (runs in main thread for simplicity)."""
        if self._current_track is not track:
            return
        try:
            from rekordbox_creative.analysis.waveform import generate_waveform
            path = Path(track.file_path)
            if not path.exists():
                return
            samples, duration = generate_waveform(path)
            if self._waveform_cache:
                self._waveform_cache.put(track.id, samples, duration)
            self._set_waveform_display(track, samples, duration)
        except Exception:
            logger.exception("Failed to generate waveform for %s", track.filename)

    def _set_waveform_display(
        self, track: Track, samples: list[float], duration: float
    ) -> None:
        self._waveform.set_waveform(
            samples,
            duration,
            drops=track.structure.drops,
            breakdowns=track.structure.breakdowns,
            intro_end=track.structure.intro_end,
            outro_start=track.structure.outro_start,
        )

    def _toggle_play(self) -> None:
        if not self._player or not self._current_track:
            return
        from PyQt6.QtMultimedia import QMediaPlayer
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._is_playing = False
            self._play_btn.setText("\u25b6")
            self._update_timer.stop()
        else:
            self._player.play()
            self._is_playing = True
            self._play_btn.setText("\u23f8")
            self._update_timer.start()
        self.play_state_changed.emit(self._is_playing)

    def _on_seek(self, pos: float) -> None:
        """Handle click on waveform to seek."""
        if self._player and self._current_track:
            duration = self._player.duration()
            if duration > 0:
                self._player.setPosition(int(pos * duration))
                self._waveform.set_playhead(pos)

    def _on_position_changed(self, position_ms: int) -> None:
        """Update time label from QMediaPlayer position."""
        duration = self._player.duration() if self._player else 0
        if duration > 0:
            pos_secs = position_ms // 1000
            dur_secs = duration // 1000
            self._time_label.setText(
                f"{pos_secs // 60}:{pos_secs % 60:02d} / "
                f"{dur_secs // 60}:{dur_secs % 60:02d}"
            )

    def _update_playhead(self) -> None:
        """Update waveform playhead from player position."""
        if self._player:
            duration = self._player.duration()
            if duration > 0:
                pos = self._player.position() / duration
                self._waveform.set_playhead(pos)

    def _on_volume_changed(self, value: int) -> None:
        if self._audio_output:
            self._audio_output.setVolume(value / 100.0)

    def _on_media_status_changed(self, status) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._is_playing = False
            self._play_btn.setText("\u25b6")
            self._update_timer.stop()
            self._waveform.set_playhead(0.0)
            self.play_state_changed.emit(False)

    def stop(self) -> None:
        """Stop playback."""
        if self._player:
            self._player.stop()
        self._is_playing = False
        self._play_btn.setText("\u25b6")
        self._update_timer.stop()
        self._waveform.set_playhead(0.0)
        self.play_state_changed.emit(False)

    def is_playing(self) -> bool:
        return self._is_playing

    def get_current_track(self) -> Track | None:
        return self._current_track
