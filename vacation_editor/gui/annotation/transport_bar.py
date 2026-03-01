from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme


class _SeekSlider(QSlider):
    """Horizontal slider that jumps to the clicked position on single click."""

    jumped = pyqtSignal(int)  # emits slider value on click

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(0, 10_000)
        self.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: {theme.BG_INPUT};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {theme.ACCENT_BLUE};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            """
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            val = self._pos_to_value(event.position().x())
            self.setValue(val)
            self.jumped.emit(val)
        super().mousePressEvent(event)

    def _pos_to_value(self, x: float) -> int:
        groove_w = self.width()
        ratio = max(0.0, min(1.0, x / groove_w))
        return int(ratio * self.maximum())


class _SpeedChip(QPushButton):
    def __init__(self, label: str, speed: float, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.speed = speed
        self.setCheckable(True)
        self._update_style(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self._update_style(active)

    def _update_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(
                f"background: {theme.ACCENT_BLUE}; color: #FFFFFF;"
                f"font-size: 11px; font-weight: 600;"
                f"border-radius: 4px; padding: 3px 8px;"
            )
        else:
            self.setStyleSheet(
                f"background: {theme.BG_INPUT}; color: {theme.TEXT_SECONDARY};"
                f"font-size: 11px; font-weight: normal;"
                f"border-radius: 4px; padding: 3px 8px;"
            )


class _ControlButton(QPushButton):
    def __init__(self, symbol: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(symbol, parent)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 14px;"
            f"background: transparent; padding: 4px 6px; border-radius: 4px;"
        )
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class TransportBarWidget(QWidget):
    """Seek slider + playback controls + speed chips.

    Signals:
        seek_requested(float): position in seconds
        play_pause_toggled(): user clicked play/pause
        skip_to_start(): user clicked skip-back
        speed_changed(float): user selected a speed multiplier
    """

    seek_requested = pyqtSignal(float)
    play_pause_toggled = pyqtSignal()
    skip_to_start = pyqtSignal()
    speed_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setStyleSheet(
            f"background: {theme.BG_ELEVATED};"
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        self._duration = 0.0
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        # --- Seek row ---
        seek_row = QHBoxLayout()
        seek_row.setSpacing(10)

        self._time_in = QLabel("0:00")
        self._time_in.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px; font-weight: 500;"
            f"background: transparent;"
        )
        self._seek = _SeekSlider(self)
        self._seek.jumped.connect(self._on_slider_jumped)
        self._seek.valueChanged.connect(self._on_slider_moved)
        self._time_out = QLabel("0:00")
        self._time_out.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px; font-weight: 500;"
            f"background: transparent;"
        )

        seek_row.addWidget(self._time_in)
        seek_row.addWidget(self._seek, 1)
        seek_row.addWidget(self._time_out)
        layout.addLayout(seek_row)

        # --- Controls row ---
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(0)

        # Left: transport buttons
        left = QHBoxLayout()
        left.setSpacing(4)
        self._btn_skip = _ControlButton("|◀", "Skip to start (Home)")
        self._btn_rewind = _ControlButton("◀◀", "Rewind 5s (J)")
        self._btn_play = QPushButton("▶  Play")
        self._btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_play.setStyleSheet(
            f"background: {theme.ACCENT_BLUE}; color: #FFFFFF;"
            f"font-size: 12px; font-weight: 500;"
            f"border-radius: 6px; padding: 6px 10px;"
        )
        self._btn_ffwd = _ControlButton("▶▶", "Fast forward 5s (L)")

        self._btn_skip.clicked.connect(self.skip_to_start)
        self._btn_rewind.clicked.connect(lambda: self.seek_requested.emit(
            max(0.0, self._current_pos() - 5.0)
        ))
        self._btn_play.clicked.connect(self.play_pause_toggled)
        self._btn_ffwd.clicked.connect(lambda: self.seek_requested.emit(
            min(self._duration, self._current_pos() + 5.0)
        ))

        left.addWidget(self._btn_skip)
        left.addWidget(self._btn_rewind)
        left.addWidget(self._btn_play)
        left.addWidget(self._btn_ffwd)

        # Right: speed chips
        right = QHBoxLayout()
        right.setSpacing(6)
        self._chips: list[_SpeedChip] = []
        for label, speed in (("0.25×", 0.25), ("0.5×", 0.5), ("1×", 1.0), ("2×", 2.0)):
            chip = _SpeedChip(label, speed)
            chip.set_active(speed == 1.0)
            chip.clicked.connect(lambda _checked, c=chip: self._on_speed_chip(c))
            self._chips.append(chip)
            right.addWidget(chip)

        ctrl_row.addLayout(left)
        ctrl_row.addStretch()
        ctrl_row.addLayout(right)
        layout.addLayout(ctrl_row)

    # ------------------------------------------------------------------
    # Public slots
    # ------------------------------------------------------------------

    def set_position(self, seconds: float) -> None:
        self._seek.blockSignals(True)
        if self._duration > 0:
            self._seek.setValue(int(seconds / self._duration * 10_000))
        self._seek.blockSignals(False)
        self._time_in.setText(self._fmt(seconds))

    def set_duration(self, seconds: float) -> None:
        self._duration = seconds
        self._time_out.setText(self._fmt(seconds))

    def set_playback_state(self, state: str) -> None:
        if state == "playing":
            self._btn_play.setText("⏸  Pause")  # ⏸ renders as text on all platforms
        else:
            self._btn_play.setText("▶  Play")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _current_pos(self) -> float:
        if self._duration <= 0:
            return 0.0
        return self._seek.value() / 10_000.0 * self._duration

    def _on_slider_jumped(self, value: int) -> None:
        if self._duration > 0:
            self.seek_requested.emit(value / 10_000.0 * self._duration)

    def _on_slider_moved(self, value: int) -> None:
        if self._duration > 0:
            secs = value / 10_000.0 * self._duration
            self._time_in.setText(self._fmt(secs))

    def _on_speed_chip(self, chip: _SpeedChip) -> None:
        for c in self._chips:
            c.set_active(c is chip)
        self.speed_changed.emit(chip.speed)

    @staticmethod
    def _fmt(seconds: float) -> str:
        total = int(seconds)
        m, s = divmod(total, 60)
        return f"{m}:{s:02d}"
