from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme

if TYPE_CHECKING:
    from vacation_editor.models.composition import CompositionSection

_TRANSITIONS: list[tuple[str, str]] = [
    ("cut", "Cut"),
    ("crossfade", "Crossfade"),
    ("dissolve", "Dissolve"),
]


class _SegmentedButton(QPushButton):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self._update_style(False)
        self.toggled.connect(self._update_style)

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self._update_style(active)

    def _update_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(
                f"QPushButton {{ background: {theme.ACCENT_BLUE};"
                f"color: {theme.TEXT_PRIMARY}; font-size: 11px;"
                f"border-radius: 4px; padding: 0 8px; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: {theme.BG_INPUT};"
                f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
                f"border-radius: 4px; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {theme.BG_ELEVATED};"
                f"color: {theme.TEXT_PRIMARY}; }}"
            )


class TransitionPickerWidget(QWidget):
    """Right panel: section info + transition controls + export settings.

    Signals:
        transition_changed(str, int): transition type and duration_ms
        export_requested: user clicked "Export 4K Video"
    """

    transition_changed = pyqtSignal(str, int)
    export_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(
            f"TransitionPickerWidget {{ background: {theme.BG_PANEL};"
            f"border-left: 1px solid {theme.BORDER}; }}"
        )
        self._setup_ui()
        self._selected_transition: str = "crossfade"

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable body
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(16)

        # --- Selected section info ---
        self._section_info = QWidget()
        info_layout = QVBoxLayout(self._section_info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        info_lbl = QLabel("SELECTED SECTION")
        info_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 9px;"
            f"letter-spacing: 1px; font-weight: 600; }}"
        )
        info_layout.addWidget(info_lbl)

        times_row = QHBoxLayout()
        times_row.setSpacing(12)
        for key, attr in (("IN", "_in_lbl"), ("OUT", "_out_lbl"), ("DUR", "_dur_lbl")):
            col = QVBoxLayout()
            col.setSpacing(2)
            k = QLabel(key)
            k.setStyleSheet(
                f"QLabel {{ color: {theme.ACCENT_ORANGE}; font-size: 9px;"
                f"font-weight: 600; }}"
            )
            v = QLabel("–")
            v.setStyleSheet(
                f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 11px; }}"
            )
            setattr(self, attr, v)
            col.addWidget(k)
            col.addWidget(v)
            times_row.addLayout(col)
        times_row.addStretch()
        info_layout.addLayout(times_row)
        body_layout.addWidget(self._section_info)

        self._divider1 = _divider()
        body_layout.addWidget(self._divider1)

        # --- Transition picker ---
        trans_lbl = QLabel("TRANSITION TO NEXT")
        trans_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 9px;"
            f"letter-spacing: 1px; font-weight: 600; }}"
        )
        body_layout.addWidget(trans_lbl)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._trans_buttons: dict[str, _SegmentedButton] = {}
        grid = QHBoxLayout()
        grid.setSpacing(4)
        for value, label in _TRANSITIONS:
            btn = _SegmentedButton(label)
            btn.set_active(value == "crossfade")
            self._btn_group.addButton(btn)
            self._trans_buttons[value] = btn
            btn.clicked.connect(lambda _, v=value: self._on_transition_clicked(v))
            grid.addWidget(btn)
        body_layout.addLayout(grid)

        # --- Duration stepper ---
        dur_row = QHBoxLayout()
        dur_lbl = QLabel("Duration")
        dur_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 11px; }}"
        )
        dur_row.addWidget(dur_lbl)
        dur_row.addStretch()
        self._dur_spin = QSpinBox()
        self._dur_spin.setRange(100, 3000)
        self._dur_spin.setSingleStep(100)
        self._dur_spin.setValue(500)
        self._dur_spin.setSuffix(" ms")
        self._dur_spin.setFixedWidth(80)
        self._dur_spin.setStyleSheet(
            f"QSpinBox {{ background: {theme.BG_INPUT};"
            f"color: {theme.TEXT_PRIMARY}; border-radius: 4px;"
            f"padding: 2px 6px; font-size: 11px; border: none; }}"
        )
        self._dur_spin.valueChanged.connect(self._on_duration_changed)
        dur_row.addWidget(self._dur_spin)
        body_layout.addLayout(dur_row)

        body_layout.addWidget(_divider())

        # --- Export settings ---
        exp_lbl = QLabel("EXPORT")
        exp_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 9px;"
            f"letter-spacing: 1px; font-weight: 600; }}"
        )
        body_layout.addWidget(exp_lbl)

        # Codec row
        codec_lbl = QLabel("Codec")
        codec_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 11px; }}"
        )
        body_layout.addWidget(codec_lbl)

        self._codec_combo = QComboBox()
        self._codec_combo.addItems(["H.264 (VideoToolbox)", "H.265 (VideoToolbox)"])
        self._codec_combo.setStyleSheet(
            f"QComboBox {{ background: {theme.BG_INPUT}; color: {theme.TEXT_PRIMARY};"
            f"border-radius: 4px; padding: 2px 6px; font-size: 11px; border: none; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ background: {theme.BG_ELEVATED};"
            f"color: {theme.TEXT_PRIMARY}; selection-background-color: {theme.ACCENT_BLUE}; }}"
        )
        body_layout.addWidget(self._codec_combo)

        # FPS row
        fps_lbl = QLabel("Frame rate")
        fps_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 11px; }}"
        )
        body_layout.addWidget(fps_lbl)

        fps_row = QHBoxLayout()
        fps_row.setSpacing(4)
        self._fps_btns: dict[int, _SegmentedButton] = {}
        fps_group = QButtonGroup(self)
        fps_group.setExclusive(True)
        for value, label in ((24, "24 fps"), (25, "25 fps")):
            btn = _SegmentedButton(label)
            btn.set_active(value == 24)
            fps_group.addButton(btn)
            self._fps_btns[value] = btn
            fps_row.addWidget(btn)
        body_layout.addLayout(fps_row)

        body_layout.addStretch()
        outer.addWidget(body, 1)

        # --- Export button (pinned to bottom) ---
        btn_container = QWidget()
        btn_container.setFixedHeight(56)
        btn_container.setStyleSheet(
            f"QWidget {{ background: {theme.BG_PANEL};"
            f"border-top: 1px solid {theme.BORDER}; }}"
        )
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(16, 0, 16, 0)

        self._export_btn = QPushButton("Export 4K Video")
        self._export_btn.setFixedHeight(36)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.ACCENT_BLUE};"
            f"color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
            f"border-radius: 6px; }}"
            f"QPushButton:hover {{ background: #1A94FF; }}"
            f"QPushButton:disabled {{ background: {theme.BG_INPUT};"
            f"color: {theme.TEXT_MUTED}; }}"
        )
        self._export_btn.clicked.connect(self.export_requested)
        btn_layout.addWidget(self._export_btn)
        outer.addWidget(btn_container)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_selected_section(
        self, section_id: str | None, info: tuple[str, float, float] | None
    ) -> None:
        """Update the section info pane. info=(clip_name, start, end) or None."""
        if info is None:
            self._in_lbl.setText("–")
            self._out_lbl.setText("–")
            self._dur_lbl.setText("–")
            return
        _clip_name, start, end = info
        self._in_lbl.setText(_fmt_time(start))
        self._out_lbl.setText(_fmt_time(end))
        self._dur_lbl.setText(f"{end - start:.1f}s")

    def set_section_transition(self, section: CompositionSection) -> None:
        """Sync UI to the selected section's current transition."""
        self._selected_transition = section.transition
        for value, btn in self._trans_buttons.items():
            btn.set_active(value == section.transition)
        self._dur_spin.setValue(section.transition_duration_ms)

    def set_export_enabled(self, enabled: bool) -> None:
        self._export_btn.setEnabled(enabled)

    def get_codec(self) -> str:
        return "h265" if self._codec_combo.currentIndex() == 1 else "h264"

    def get_fps(self) -> int:
        for value, btn in self._fps_btns.items():
            if btn.isChecked():
                return value
        return 24

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_transition_clicked(self, value: str) -> None:
        self._selected_transition = value
        self.transition_changed.emit(value, self._dur_spin.value())

    def _on_duration_changed(self, value: int) -> None:
        self.transition_changed.emit(self._selected_transition, value)


def _divider() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(f"QWidget {{ background: {theme.BORDER}; }}")
    return line


def _fmt_time(seconds: float) -> str:
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    frac = int((seconds - int(seconds)) * 10)
    return f"{mins}:{secs:02d}.{frac}"
