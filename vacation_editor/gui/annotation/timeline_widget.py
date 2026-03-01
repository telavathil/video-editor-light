from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from vacation_editor.gui import theme

if TYPE_CHECKING:
    from vacation_editor.models.annotation import Section

_TRACK_Y = 28        # y offset of the clip track within the timeline body
_TRACK_H = 28        # height of the clip track bar
_HANDLE_W = 3        # width of drag handles on section edges
_TICK_H = 20         # height of tick ruler area
_PLAYHEAD_W = 2      # playhead line width
_PLAYHEAD_CAP_W = 10 # playhead top cap width
_PADDING = 14        # left/right padding inside timeline body


@dataclass
class _DragState:
    section_id: str
    edge: str           # "left" | "right"
    origin_x: int
    origin_start: float
    origin_end: float


class TimelineWidget(QWidget):
    """Custom timeline: tick ruler + clip track + section blocks + playhead.

    Signals:
        seek_requested(float): user clicked or dragged the playhead
        section_trimmed(str, float, float): section_id, new_start, new_end
    """

    seek_requested = pyqtSignal(float)
    section_trimmed = pyqtSignal(str, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._duration = 0.0
        self._position = 0.0
        self._sections: list[Section] = []
        self._zoom = 1.0
        self._drag: _DragState | None = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header row
        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet(
            f"background: {theme.BG_ELEVATED};"
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        h_row = QHBoxLayout(header)
        h_row.setContentsMargins(14, 0, 14, 0)
        label = QLabel("TIMELINE")
        label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px; font-weight: 600;"
            f"letter-spacing: 1px; background: transparent;"
        )
        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(8)
        self._zoom_out_btn = QPushButton("−")
        self._zoom_label = QLabel("1×")
        self._zoom_in_btn = QPushButton("+")
        for btn in (self._zoom_out_btn, self._zoom_in_btn):
            btn.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; background: transparent;"
                f"font-size: 14px; padding: 0; border: none;"
            )
            btn.setFixedSize(20, 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px; background: transparent;"
        )
        self._zoom_out_btn.clicked.connect(lambda: self._set_zoom(self._zoom / 1.5))
        self._zoom_in_btn.clicked.connect(lambda: self._set_zoom(self._zoom * 1.5))
        zoom_row.addWidget(self._zoom_out_btn)
        zoom_row.addWidget(self._zoom_label)
        zoom_row.addWidget(self._zoom_in_btn)
        h_row.addWidget(label)
        h_row.addStretch()
        h_row.addLayout(zoom_row)
        outer.addWidget(header)

        # Body (the drawing canvas)
        self._body = _TimelineBody(self)
        self._body.seek_requested.connect(self.seek_requested)
        self._body.section_trimmed.connect(self.section_trimmed)
        outer.addWidget(self._body, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_duration(self, seconds: float) -> None:
        self._duration = seconds
        self._body.set_duration(seconds)

    def set_position(self, seconds: float) -> None:
        self._position = seconds
        self._body.set_position(seconds)

    def set_sections(self, sections: list[Section]) -> None:
        self._sections = list(sections)
        self._body.set_sections(self._sections)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.5, min(10.0, zoom))
        self._zoom_label.setText(f"{self._zoom:.1f}×".replace(".0×", "×"))
        self._body.set_zoom(self._zoom)


class _TimelineBody(QWidget):
    """The actual painted canvas inside the timeline."""

    seek_requested = pyqtSignal(float)
    section_trimmed = pyqtSignal(str, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {theme.BG_ELEVATED};")
        self.setMouseTracking(True)
        self._duration = 0.0
        self._position = 0.0
        self._sections: list[Section] = []
        self._zoom = 1.0
        self._drag: _DragState | None = None

    # --- public setters (trigger repaint) ---

    def set_duration(self, s: float) -> None:
        self._duration = s
        self.update()

    def set_position(self, s: float) -> None:
        self._position = s
        self.update()

    def set_sections(self, sections: list[Section]) -> None:
        self._sections = list(sections)
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self.update()

    # --- coordinate helpers ---

    def _track_width(self) -> int:
        return int((self.width() - _PADDING * 2) * self._zoom)

    def _s_to_x(self, seconds: float) -> int:
        if self._duration <= 0:
            return _PADDING
        return _PADDING + int(seconds / self._duration * self._track_width())

    def _x_to_s(self, x: int) -> float:
        tw = self._track_width()
        if tw <= 0 or self._duration <= 0:
            return 0.0
        ratio = (x - _PADDING) / tw
        return max(0.0, min(self._duration, ratio * self._duration))

    # --- painting ---

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        if self._duration <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_ticks(p)
        self._draw_track(p)
        self._draw_sections(p)
        self._draw_playhead(p)
        p.end()

    def _draw_ticks(self, p: QPainter) -> None:
        font = QFont("-apple-system", 9)
        p.setFont(font)
        p.setPen(QColor(theme.TEXT_MUTED))

        # choose tick interval so we get ~8 ticks visible
        interval = self._nice_interval(self._duration / self._zoom)
        t = 0.0
        while t <= self._duration:
            x = self._s_to_x(t)
            m, s = divmod(int(t), 60)
            p.drawText(x, _TICK_H - 4, f"{m}:{s:02d}")
            t += interval

    def _draw_track(self, p: QPainter) -> None:
        track_rect = QRect(
            _PADDING, _TICK_H, self._track_width(), _TRACK_H
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.BG_INPUT))
        p.drawRoundedRect(track_rect, 4, 4)

    def _draw_sections(self, p: QPainter) -> None:
        for i, sec in enumerate(self._sections):
            fill_hex, border_hex = theme.section_colors(i)
            x1 = self._s_to_x(sec.start_seconds)
            x2 = self._s_to_x(sec.end_seconds)
            w = max(4, x2 - x1)
            rect = QRect(x1, _TICK_H, w, _TRACK_H)

            # Fill
            p.setPen(Qt.PenStyle.NoPen)
            fill = QColor(border_hex)
            fill.setAlpha(int(fill_hex[-2:], 16) if len(fill_hex) == 9 else 60)
            p.setBrush(fill)
            p.drawRoundedRect(rect, 3, 3)

            # Border
            pen = QPen(QColor(border_hex))
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, 3, 3)

            # Label
            p.setPen(QColor(border_hex))
            p.setFont(QFont("-apple-system", 9, QFont.Weight.Bold))
            p.drawText(x1 + 5, _TICK_H + 18, f"§{i + 1}")

            # Drag handles
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FFFFFF66"))
            p.drawRoundedRect(QRect(x1, _TICK_H + 5, _HANDLE_W, _TRACK_H - 10), 1, 1)
            p.drawRoundedRect(QRect(x2 - _HANDLE_W, _TICK_H + 5, _HANDLE_W, _TRACK_H - 10), 1, 1)

    def _draw_playhead(self, p: QPainter) -> None:
        x = self._s_to_x(self._position)
        # Top cap
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRect(x - _PLAYHEAD_CAP_W // 2, _TICK_H - 8, _PLAYHEAD_CAP_W, 8), 2, 2)
        # Line
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidth(_PLAYHEAD_W)
        p.setPen(pen)
        p.drawLine(x, _TICK_H, x, self.height())

    # --- mouse events ---

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x = event.position().toPoint().x()
        y = event.position().toPoint().y()
        # Check handle hit first
        hit = self._handle_at(x, y)
        if hit:
            sec_id, edge = hit
            sec = next(s for s in self._sections if s.section_id == sec_id)
            self._drag = _DragState(sec_id, edge, x, sec.start_seconds, sec.end_seconds)
        elif _TICK_H <= y <= _TICK_H + _TRACK_H + 20:
            self.seek_requested.emit(self._x_to_s(x))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        x = event.position().toPoint().x()
        y = event.position().toPoint().y()
        if self._drag:
            delta_s = self._x_to_s(x) - self._x_to_s(self._drag.origin_x)
            sec = next(
                (s for s in self._sections if s.section_id == self._drag.section_id), None
            )
            if sec is None:
                return
            if self._drag.edge == "left":
                new_start = max(0.0, min(self._drag.origin_start + delta_s, sec.end_seconds - 0.1))
                self._sections = [
                    s.with_times(new_start, s.end_seconds)
                    if s.section_id == self._drag.section_id else s
                    for s in self._sections
                ]
            else:
                new_end = min(
                    self._duration,
                    max(self._drag.origin_end + delta_s, sec.start_seconds + 0.1),
                )
                self._sections = [
                    s.with_times(s.start_seconds, new_end)
                    if s.section_id == self._drag.section_id else s
                    for s in self._sections
                ]
            self.update()
        else:
            # Update cursor
            if self._handle_at(x, y):
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            elif _TICK_H <= y <= _TICK_H + _TRACK_H + 20:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            else:
                self.unsetCursor()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._drag:
            sec = next(
                (s for s in self._sections if s.section_id == self._drag.section_id), None
            )
            if sec:
                self.section_trimmed.emit(sec.section_id, sec.start_seconds, sec.end_seconds)
            self._drag = None

    # --- helpers ---

    def _handle_at(self, x: int, y: int) -> tuple[str, str] | None:
        """Return (section_id, edge) if (x, y) is on a drag handle."""
        if not (_TICK_H <= y <= _TICK_H + _TRACK_H):
            return None
        for sec in self._sections:
            lx = self._s_to_x(sec.start_seconds)
            rx = self._s_to_x(sec.end_seconds)
            if lx <= x <= lx + _HANDLE_W + 2:
                return sec.section_id, "left"
            if rx - _HANDLE_W - 2 <= x <= rx:
                return sec.section_id, "right"
        return None

    @staticmethod
    def _nice_interval(span: float) -> float:
        """Return a human-friendly tick interval for a given time span."""
        for interval in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600):
            if span / interval <= 10:
                return float(interval)
        return 600.0
