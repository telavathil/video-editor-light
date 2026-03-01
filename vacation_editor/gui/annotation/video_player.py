from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from vacation_editor.gui import theme


class VideoPlayerWidget(QWidget):
    """Video display area: QMediaPlayer + QVideoWidget with overlays.

    Signals:
        position_changed(float): current position in seconds
        duration_changed(float): clip duration in seconds
        playback_state_changed(str): "playing" | "paused" | "stopped"
    """

    position_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(float)
    playback_state_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._duration_s = 0.0
        self._setup_player()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_player(self) -> None:
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._audio.setVolume(1.0)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget(self)
        layout.addWidget(self._stack)

        # --- Placeholder (index 0) ---
        placeholder = QWidget()
        placeholder.setStyleSheet("background: #000000;")
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("◎")
        icon.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 48px; background: transparent;")
        hint = QLabel("No clip loaded")
        hint.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 13px; background: transparent;"
        )
        ph_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
        ph_layout.addSpacing(8)
        ph_layout.addWidget(hint, alignment=Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(placeholder)

        # --- Video widget (index 1) ---
        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet("background: #000000;")
        self._player.setVideoOutput(self._video_widget)
        self._stack.addWidget(self._video_widget)

        # --- Timecode overlay (top-left, on top of stack) ---
        self._timecode = QLabel("00:00:00", self)
        self._timecode.setStyleSheet(
            f"background: rgba(0,0,0,153);"
            f"color: {theme.TEXT_PRIMARY};"
            f"font-size: 12px; font-weight: 600;"
            f"letter-spacing: 1px;"
            f"padding: 5px 10px;"
            f"border-radius: 4px;"
        )
        self._timecode.hide()

        # --- Mark-in overlay (bottom-left) ---
        self._mark_in_label = QLabel("", self)
        self._mark_in_label.setStyleSheet(
            f"background: rgba(255,159,10,51);"
            f"color: {theme.ACCENT_ORANGE};"
            f"font-size: 10px; font-weight: 600;"
            f"padding: 4px 8px;"
            f"border-left: 2px solid {theme.ACCENT_ORANGE};"
            f"border-radius: 3px;"
        )
        self._mark_in_label.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_clip(self, path: Path) -> None:
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._stack.setCurrentIndex(1)
        self._timecode.show()
        self._player.pause()

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def toggle_play_pause(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def seek(self, seconds: float) -> None:
        self._player.setPosition(int(seconds * 1000))

    def get_position(self) -> float:
        return self._player.position() / 1000.0

    def get_duration(self) -> float:
        return self._duration_s

    def set_speed(self, speed: float) -> None:
        self._player.setPlaybackRate(speed)

    def set_mark_in_overlay(self, seconds: float | None) -> None:
        if seconds is None:
            self._mark_in_label.hide()
        else:
            m, s = divmod(int(seconds), 60)
            self._mark_in_label.setText(f"IN  {m:02d}:{s:02d}")
            self._mark_in_label.show()
            self._reposition_overlays()

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reposition_overlays()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reposition_overlays(self) -> None:
        self._timecode.adjustSize()
        self._timecode.move(12, 12)
        self._mark_in_label.adjustSize()
        self._mark_in_label.move(12, self.height() - 44)

    def _on_position_changed(self, ms: int) -> None:
        seconds = ms / 1000.0
        total = int(seconds)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        self._timecode.setText(f"{h:02d}:{m:02d}:{s:02d}")
        self._timecode.adjustSize()
        self.position_changed.emit(seconds)

    def _on_duration_changed(self, ms: int) -> None:
        self._duration_s = ms / 1000.0
        self.duration_changed.emit(self._duration_s)

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        match state:
            case QMediaPlayer.PlaybackState.PlayingState:
                self.playback_state_changed.emit("playing")
            case QMediaPlayer.PlaybackState.PausedState:
                self.playback_state_changed.emit("paused")
            case _:
                self.playback_state_changed.emit("stopped")
