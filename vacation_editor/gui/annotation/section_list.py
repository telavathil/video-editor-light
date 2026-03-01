from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme

if TYPE_CHECKING:
    from vacation_editor.models.annotation import Section


class _SectionRow(QWidget):
    """Single row in the section list."""

    play_clicked = pyqtSignal(str)    # section_id
    delete_clicked = pyqtSignal(str)  # section_id
    selected = pyqtSignal(str)        # section_id

    def __init__(
        self,
        section: Section,
        index: int,
        is_selected: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._section_id = section.section_id
        self._is_selected = is_selected
        self._setup_ui(section, index, is_selected)
        self.setFixedHeight(44)
        self._apply_style()

    def _setup_ui(self, section: Section, index: int, is_selected: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # Index badge
        badge = QLabel(str(index + 1))
        badge.setFixedSize(20, 20)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fill = theme.ACCENT_BLUE if is_selected else theme.BG_INPUT
        badge.setStyleSheet(
            f"background: {fill}; color: {'#FFFFFF' if is_selected else theme.TEXT_SECONDARY};"
            f"font-size: 10px; font-weight: 700; border-radius: 10px;"
        )

        # Time + label
        _, border = theme.section_colors(index)
        start_m, start_s = divmod(int(section.start_seconds), 60)
        end_m, end_s = divmod(int(section.end_seconds), 60)
        dur = section.duration_seconds
        dur_m, dur_s = divmod(int(dur), 60)

        time_text = f"{start_m}:{start_s:02d} – {end_m}:{end_s:02d}"
        meta_text = f"{dur_m}:{dur_s:02d}"

        details = QVBoxLayout()
        details.setSpacing(3)
        time_label = QLabel(time_text)
        time_label.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 11px; font-weight: 500;"
            f"background: transparent;"
        )
        meta_label = QLabel(section.label if section.label else meta_text)
        meta_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )
        details.addWidget(time_label)
        details.addWidget(meta_label)

        # Action buttons
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(24, 24)
        play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        play_btn.setToolTip("Play section")
        play_btn.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; background: transparent;"
            f"font-size: 11px; border-radius: 4px; padding: 0;"
        )
        play_btn.clicked.connect(lambda: self.play_clicked.emit(self._section_id))

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("Delete section (Del)")
        del_btn.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; background: transparent;"
            f"font-size: 11px; border-radius: 4px; padding: 0;"
        )
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self._section_id))

        layout.addWidget(badge)
        layout.addLayout(details, 1)
        layout.addWidget(play_btn)
        layout.addWidget(del_btn)

    def _apply_style(self) -> None:
        if self._is_selected:
            self.setStyleSheet(
                f"background: {theme.BG_ELEVATED};"
                f"border-left: 2px solid {theme.ACCENT_BLUE};"
                f"border-bottom: 1px solid {theme.ACCENT_BLUE};"
            )
        else:
            self.setStyleSheet(
                f"background: transparent;"
                f"border-bottom: 1px solid {theme.BORDER};"
            )

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.selected.emit(self._section_id)
        super().mousePressEvent(event)


class SectionListWidget(QWidget):
    """Right-panel section list.

    Signals:
        section_selected(Section): user selected a row
        section_deleted(str): section_id deleted
        section_play_requested(Section): user clicked play on a row
    """

    section_selected = pyqtSignal(object)       # Section
    section_deleted = pyqtSignal(str)           # section_id
    section_play_requested = pyqtSignal(object) # Section

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(
            f"background: {theme.BG_PANEL};"
            f"border-left: 1px solid {theme.BORDER};"
        )
        self._sections: list[Section] = []
        self._selected_id: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet(f"border-bottom: 1px solid {theme.BORDER};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 0, 14, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel("SECTIONS")
        title.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px; font-weight: 600;"
            f"letter-spacing: 1px; background: transparent;"
        )
        self._badge = QLabel("0")
        self._badge.setStyleSheet(
            f"background: {theme.ACCENT_BLUE}; color: #FFFFFF;"
            f"font-size: 10px; font-weight: 700; border-radius: 10px;"
            f"padding: 2px 7px;"
        )
        title_row.addWidget(title)
        title_row.addWidget(self._badge)
        h_layout.addLayout(title_row)
        h_layout.addStretch()
        layout.addWidget(header)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(44)
        footer.setStyleSheet(f"border-top: 1px solid {theme.BORDER};")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(14, 0, 14, 0)
        total_lbl = QLabel("Total duration")
        total_lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        self._total_val = QLabel("0:00")
        self._total_val.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
            f"background: transparent;"
        )
        f_layout.addWidget(total_lbl)
        f_layout.addStretch()
        f_layout.addWidget(self._total_val)
        layout.addWidget(footer)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_sections(self, sections: list[Section]) -> None:
        self._sections = list(sections)
        self._rebuild()

    def set_selected(self, section_id: str | None) -> None:
        self._selected_id = section_id
        self._rebuild()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        # Remove all rows (but keep the stretch at end)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, sec in enumerate(self._sections):
            row = _SectionRow(sec, i, sec.section_id == self._selected_id)
            row.selected.connect(self._on_selected)
            row.play_clicked.connect(self._on_play)
            row.delete_clicked.connect(self._on_delete)
            self._list_layout.insertWidget(i, row)

        count = len(self._sections)
        self._badge.setText(str(count))
        total = sum(s.duration_seconds for s in self._sections)
        m, s = divmod(int(total), 60)
        self._total_val.setText(f"{m}:{s:02d}")

    def _on_selected(self, section_id: str) -> None:
        self._selected_id = section_id
        self._rebuild()
        sec = next((s for s in self._sections if s.section_id == section_id), None)
        if sec:
            self.section_selected.emit(sec)

    def _on_play(self, section_id: str) -> None:
        sec = next((s for s in self._sections if s.section_id == section_id), None)
        if sec:
            self.section_play_requested.emit(sec)

    def _on_delete(self, section_id: str) -> None:
        self.section_deleted.emit(section_id)
