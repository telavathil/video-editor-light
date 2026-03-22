from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme


class _SectionRow(QWidget):
    """A single available section row in the library."""

    add_requested = pyqtSignal(str, str)  # clip_id, section_id

    def __init__(
        self,
        clip_id: str,
        section_id: str,
        duration: float,
        already_added: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._clip_id = clip_id
        self._section_id = section_id
        self._already_added = already_added
        self._setup_ui(duration)

    def _setup_ui(self, duration: float) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(8)

        # Thumbnail placeholder
        thumb = QLabel()
        thumb.setFixedSize(40, 28)
        thumb.setStyleSheet(
            f"QLabel {{ background: {theme.BG_INPUT}; border-radius: 2px; }}"
        )
        layout.addWidget(thumb)

        # Duration label
        mins = int(duration) // 60
        secs = int(duration) % 60
        dur_lbl = QLabel(f"{mins}:{secs:02d}")
        dur_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 11px; }}"
        )
        layout.addWidget(dur_lbl)
        layout.addStretch()

        # Add / Added button
        self._add_btn = QPushButton("Added" if self._already_added else "+ Add")
        self._add_btn.setFixedSize(52, 22)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setEnabled(not self._already_added)
        self._update_btn_style()
        self._add_btn.clicked.connect(self._on_add)
        layout.addWidget(self._add_btn)

    def _update_btn_style(self) -> None:
        if self._already_added:
            self._add_btn.setStyleSheet(
                f"QPushButton {{ color: {theme.TEXT_MUTED}; font-size: 10px;"
                f"background: transparent; border: 1px solid {theme.BORDER};"
                f"border-radius: 4px; }}"
            )
        else:
            self._add_btn.setStyleSheet(
                f"QPushButton {{ color: {theme.ACCENT_BLUE}; font-size: 10px;"
                f"background: transparent; border: 1px solid {theme.ACCENT_BLUE};"
                f"border-radius: 4px; }}"
                f"QPushButton:hover {{ background: rgba(10,132,255,0.12); }}"
            )

    def mark_added(self) -> None:
        self._already_added = True
        self._add_btn.setText("Added")
        self._add_btn.setEnabled(False)
        self._update_btn_style()

    def _on_add(self) -> None:
        self.add_requested.emit(self._clip_id, self._section_id)
        self.mark_added()


class _ClipGroup(QWidget):
    """A collapsible group of section rows for one clip."""

    section_add_requested = pyqtSignal(str, str)  # clip_id, section_id

    def __init__(
        self,
        clip_name: str,
        sections: list[tuple[str, str, float]],  # (clip_id, section_id, duration)
        added_section_ids: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._expanded = True
        self._setup_ui(clip_name, sections, added_section_ids)

    def _setup_ui(
        self,
        clip_name: str,
        sections: list[tuple[str, str, float]],
        added_section_ids: set[str],
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row
        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet(
            f"QWidget {{ background: {theme.BG_ELEVATED}; }}"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 8, 0)
        header_layout.setSpacing(6)

        self._chevron = QLabel("▾")
        self._chevron.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 10px; }}"
        )
        header_layout.addWidget(self._chevron)

        name_lbl = QLabel(clip_name)
        name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 11px; font-weight: 600; }}"
        )
        header_layout.addWidget(name_lbl, 1)

        count_lbl = QLabel(str(len(sections)))
        count_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 10px; }}"
        )
        header_layout.addWidget(count_lbl)

        layout.addWidget(header)

        # Section rows container
        self._rows_widget = QWidget()
        rows_layout = QVBoxLayout(self._rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(0)

        for clip_id, section_id, duration in sections:
            row = _SectionRow(
                clip_id, section_id, duration,
                already_added=section_id in added_section_ids,
            )
            row.add_requested.connect(self.section_add_requested)
            rows_layout.addWidget(row)

        layout.addWidget(self._rows_widget)

        # Toggle on header click
        header.mousePressEvent = lambda _: self._toggle()  # type: ignore[method-assign]

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._rows_widget.setVisible(self._expanded)
        self._chevron.setText("▾" if self._expanded else "▸")


class SectionLibraryWidget(QWidget):
    """Left panel: scrollable list of available annotated sections grouped by clip."""

    section_add_requested = pyqtSignal(str, str)  # clip_id, section_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(
            f"SectionLibraryWidget {{ background: {theme.BG_PANEL};"
            f"border-right: 1px solid {theme.BORDER}; }}"
        )
        self._groups: list[_ClipGroup] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(
            f"QWidget {{ background: {theme.BG_PANEL};"
            f"border-bottom: 1px solid {theme.BORDER}; }}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 12, 0)
        title = QLabel("Section Library")
        title.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600; }}"
        )
        h_layout.addWidget(title)
        layout.addWidget(header)

        # Scrollable clip groups
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self._content = QWidget()
        self._content.setStyleSheet(
            f"QWidget {{ background: {theme.BG_PANEL}; }}"
        )
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        # Empty state
        self._empty_label = QLabel("No annotated sections yet.\nAnnotate clips first.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 11px; }}"
        )
        self._content_layout.insertWidget(0, self._empty_label)

    def set_sections(
        self,
        items: list[tuple[str, str, str, float]],  # clip_id, section_id, clip_name, duration
        added_section_ids: set[str] | None = None,
    ) -> None:
        """Rebuild the library from a fresh list of available sections."""
        added_ids = added_section_ids or set()

        # Remove only _ClipGroup widgets — do NOT touch _empty_label or the stretch
        for group in self._groups:
            self._content_layout.removeWidget(group)
            group.deleteLater()
        self._groups.clear()

        if not items:
            self._empty_label.show()
            return

        self._empty_label.hide()

        # Group by clip
        clip_groups: dict[str, tuple[str, list[tuple[str, str, float]]]] = {}
        for clip_id, section_id, clip_name, duration in items:
            if clip_id not in clip_groups:
                clip_groups[clip_id] = (clip_name, [])
            clip_groups[clip_id][1].append((clip_id, section_id, duration))

        for clip_id, (clip_name, sections) in clip_groups.items():
            group = _ClipGroup(clip_name, sections, added_ids)
            group.section_add_requested.connect(self.section_add_requested)
            # Insert before the stretch (always the last item in the layout)
            self._content_layout.insertWidget(self._content_layout.count() - 1, group)
            self._groups.append(group)
