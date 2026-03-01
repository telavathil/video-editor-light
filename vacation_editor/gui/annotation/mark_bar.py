from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from vacation_editor.gui import theme


class _MarkButton(QWidget):
    """Clickable button with icon, label, and styled key-hint chip.

    Matches the design's orange-bordered Mark In / plain Mark Out buttons.
    """

    clicked = pyqtSignal()

    def __init__(
        self,
        symbol: str,
        label: str,
        key: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(6)

        self._sym_lbl = QLabel(symbol)
        self._txt_lbl = QLabel(label)
        self._key_lbl = QLabel(key)

        # Let mouse events pass through child labels to self
        for lbl in (self._sym_lbl, self._txt_lbl, self._key_lbl):
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(self._sym_lbl)
        layout.addWidget(self._txt_lbl)
        layout.addWidget(self._key_lbl)

        self._apply_style()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def setEnabled(self, enabled: bool) -> None:  # type: ignore[override]
        super().setEnabled(enabled)
        self._apply_style()

    def click(self) -> None:
        """Programmatic click — for tests and keyboard shortcut wiring."""
        self.clicked.emit()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _apply_style(self) -> None:
        if not self.isEnabled():
            border = theme.BORDER
            text_c = theme.TEXT_MUTED
            chip_bg = theme.BG_INPUT
            chip_c = theme.TEXT_MUTED
        elif self._active:
            border = theme.ACCENT_ORANGE
            text_c = theme.ACCENT_ORANGE
            chip_bg = "#3A2A10"
            chip_c = theme.ACCENT_ORANGE
        else:
            border = theme.BORDER
            text_c = theme.TEXT_SECONDARY
            chip_bg = theme.BG_INPUT
            chip_c = theme.TEXT_SECONDARY

        self.setStyleSheet(
            f"background: {theme.BG_ELEVATED}; border: 1px solid {border};"
            f"border-radius: 5px;"
        )
        for lbl in (self._sym_lbl, self._txt_lbl):
            lbl.setStyleSheet(
                f"color: {text_c}; font-size: 12px; font-weight: 500;"
                f"background: transparent; border: none;"
            )
        self._key_lbl.setStyleSheet(
            f"background: {chip_bg}; color: {chip_c};"
            f"font-size: 10px; font-weight: 700;"
            f"border-radius: 3px; padding: 1px 5px; border: none;"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MarkBarWidget(QWidget):
    """Mark In / Mark Out controls + pending-section indicator.

    Signals:
        mark_in_clicked(): user pressed Mark In (or I key)
        mark_out_clicked(): user pressed Mark Out (or O key)
    """

    mark_in_clicked = pyqtSignal()
    mark_out_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(
            f"background: {theme.BG_PANEL};"
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Mark In button
        self._mark_in_btn = _MarkButton("▷", "Mark In", "I")
        self._mark_in_btn.clicked.connect(self.mark_in_clicked)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.VLine)
        div1.setFixedHeight(20)
        div1.setStyleSheet(f"color: {theme.BORDER};")

        # Status indicator (centre)
        self._indicator = QLabel("Set a mark-in point to begin a section  ( I )")
        self._indicator.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        self._indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.VLine)
        div2.setFixedHeight(20)
        div2.setStyleSheet(f"color: {theme.BORDER};")

        # Mark Out button
        self._mark_out_btn = _MarkButton("◁", "Mark Out", "O")
        self._mark_out_btn.setEnabled(False)
        self._mark_out_btn.clicked.connect(self.mark_out_clicked)

        layout.addWidget(self._mark_in_btn)
        layout.addWidget(div1)
        layout.addWidget(self._indicator, 1)
        layout.addWidget(div2)
        layout.addWidget(self._mark_out_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_mark_in(self, seconds: float | None) -> None:
        """Update UI to reflect whether mark-in is pending."""
        if seconds is None:
            self._indicator.setText("Set a mark-in point to begin a section  ( I )")
            self._indicator.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; font-size: 11px; background: transparent;"
            )
            self._mark_out_btn.setEnabled(False)
            self._mark_in_btn.set_active(False)
        else:
            m, s = divmod(int(seconds), 60)
            self._indicator.setText(f"●  {m:02d}:{s:02d}  →  pending mark-out…")
            self._indicator.setStyleSheet(
                f"color: {theme.ACCENT_ORANGE}; font-size: 11px; background: transparent;"
            )
            self._mark_out_btn.setEnabled(True)
            self._mark_in_btn.set_active(True)
