from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPropertyAnimation, Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme
from vacation_editor.gui.annotation.video_player import VideoPlayerWidget

# Tuple layout: (path, start_s, end_s, transition_type, transition_duration_ms)
_Clip = tuple[Path, float, float, str, int]


class CompositionPreviewDialog(QDialog):
    """Plays composition sections sequentially with simulated transitions.

    Cut        → instant switch (no overlay).
    All others → fade-to-black then fade-in, using a QGraphicsOpacityEffect
                 overlay.  The next clip loads and begins playing while the
                 screen is black so the fade-in reveals a running frame.
    """

    def __init__(
        self,
        clips: list[_Clip],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Composition Preview")
        self.setMinimumSize(800, 520)
        self.setStyleSheet(f"QDialog {{ background: {theme.BG_PRIMARY}; }}")

        self._clips = clips
        self._current_index = 0
        self._current_path: Path | None = None
        self._at_end = False
        self._pending_seek_ms: int | None = None
        self._anim: QPropertyAnimation | None = None  # keep animation alive

        self._setup_ui()
        self._connect_player_signals()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Section header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(
            f"QWidget {{ background: {theme.BG_PANEL};"
            f"border-bottom: 1px solid {theme.BORDER}; }}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)
        self._section_lbl = QLabel(f"Section 1 of {len(self._clips)}")
        self._section_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600; }}"
        )
        h_layout.addWidget(self._section_lbl)
        h_layout.addStretch()
        layout.addWidget(header)

        # Proven video player widget
        self._video = VideoPlayerWidget()
        layout.addWidget(self._video, 1)

        # Black overlay for transition simulation (child of dialog, above video)
        self._fade_widget = QWidget(self)
        self._fade_widget.setStyleSheet("background: black;")
        self._fade_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._fade_effect = QGraphicsOpacityEffect(self._fade_widget)
        self._fade_effect.setOpacity(0.0)
        self._fade_widget.setGraphicsEffect(self._fade_effect)
        self._fade_widget.raise_()

        # Transport bar
        transport = QWidget()
        transport.setFixedHeight(52)
        transport.setStyleSheet(
            f"QWidget {{ background: {theme.BG_PANEL};"
            f"border-top: 1px solid {theme.BORDER}; }}"
        )
        t_layout = QHBoxLayout(transport)
        t_layout.setContentsMargins(16, 0, 16, 0)
        t_layout.setSpacing(12)

        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setFixedSize(96, 32)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.ACCENT_BLUE}; color: {theme.TEXT_PRIMARY};"
            f"font-size: 12px; font-weight: 600; border-radius: 6px; border: none; }}"
            f"QPushButton:hover {{ background: #1A94FF; }}"
        )
        self._play_btn.clicked.connect(self._toggle_play_pause)
        t_layout.addWidget(self._play_btn)

        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 11px; }}"
        )
        t_layout.addWidget(self._time_lbl)
        t_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(64, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {theme.TEXT_SECONDARY};"
            f"font-size: 12px; border-radius: 6px; border: 1px solid {theme.BORDER}; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        close_btn.clicked.connect(self._stop_and_close)
        t_layout.addWidget(close_btn)

        layout.addWidget(transport)

    def _connect_player_signals(self) -> None:
        self._video._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._video.position_changed.connect(self._on_position_changed)
        self._video.playback_state_changed.connect(self._on_playback_state_changed)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._clips and self._current_path is None:
            QTimer.singleShot(100, lambda: self._load_section(0))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._fade_widget.setGeometry(self._video.geometry())
        self._fade_widget.raise_()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._video.pause()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Playback logic
    # ------------------------------------------------------------------

    def _load_section(self, index: int) -> None:
        self._at_end = False
        self._current_index = index
        path, start, _end, _trans, _dur = self._clips[index]
        self._section_lbl.setText(f"Section {index + 1} of {len(self._clips)}")

        if path == self._current_path:
            self._video.seek(start)
            self._video.play()
        else:
            self._current_path = path
            self._pending_seek_ms = int(start * 1000)
            self._video.load_clip(path)

    def _toggle_play_pause(self) -> None:
        self._video.toggle_play_pause()

    def _stop_and_close(self) -> None:
        self._video.pause()
        self.accept()

    def _animate_fade(self, start_opacity: float, end_opacity: float, duration_ms: int) -> None:
        anim = QPropertyAnimation(self._fade_effect, b"opacity")
        anim.setDuration(duration_ms)
        anim.setStartValue(start_opacity)
        anim.setEndValue(end_opacity)
        anim.start()
        self._anim = anim  # prevent garbage collection

    def _run_transition(self, next_index: int, duration_ms: int) -> None:
        half = max(150, duration_ms // 2)

        # 1. Fade to black
        self._animate_fade(0.0, 1.0, half)

        # 2. Mid-point: switch to next section (plays behind the black overlay)
        QTimer.singleShot(half, lambda: self._load_section(next_index))

        # 3. After switch + 200 ms buffer for the clip to start: fade in
        QTimer.singleShot(half + 200, lambda: self._animate_fade(1.0, 0.0, half))

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ) and self._pending_seek_ms is not None:
            seek_ms = self._pending_seek_ms
            self._pending_seek_ms = None
            self._video._player.setPosition(seek_ms)
            QTimer.singleShot(0, self._video.play)

    def _on_playback_state_changed(self, state: str) -> None:
        self._play_btn.setText("⏸  Pause" if state == "playing" else "▶  Play")

    def _on_position_changed(self, pos: float) -> None:
        if not self._clips:
            return
        _path, start, end, _trans, _dur = self._clips[self._current_index]
        section_pos = max(0.0, pos - start)
        section_dur = max(0.0, end - start)
        self._time_lbl.setText(f"{_fmt(section_pos)} / {_fmt(section_dur)}")

        if pos >= end - 0.05 and not self._at_end:
            self._at_end = True
            next_index = self._current_index + 1
            if next_index >= len(self._clips):
                self._video.pause()
                return
            _p, _s, _e, transition, duration_ms = self._clips[next_index]
            if transition == "cut":
                self._load_section(next_index)
            else:
                self._run_transition(next_index, duration_ms)


def _fmt(seconds: float) -> str:
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}:{secs:02d}"
