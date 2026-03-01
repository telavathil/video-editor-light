from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme

if TYPE_CHECKING:
    from vacation_editor.models.clip import ClipMetadata

_SUPPORTED_EXTS = {".mp4", ".mov", ".m4v", ".MP4", ".MOV", ".M4V"}


class _IconLabel(QLabel):
    """Lightweight clickable label used for icon-style buttons.

    QPushButton on macOS uses native AppKit rendering that ignores
    'background: transparent; border: none' stylesheets, making text
    invisible.  A plain QLabel has no such native rendering path.
    """

    clicked = pyqtSignal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bg: str = theme.BG_PANEL
        self.setAutoFillBackground(True)
        self._set_normal()

    # ── Public ────────────────────────────────────────────────────────

    def set_background(self, color: str) -> None:
        """Set the background colour used for normal and hover states."""
        self._bg = color
        self._set_normal()

    def click(self) -> None:
        """Programmatic click for tests and keyboard shortcuts."""
        self.clicked.emit()

    # ── Qt overrides ──────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self.setStyleSheet(
            f"QLabel {{ color: {theme.ACCENT_RED}; background: {self._bg}; font-size: 11px; }}"
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_normal()
        super().leaveEvent(event)

    def _set_normal(self) -> None:
        self.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; background: {self._bg}; font-size: 11px; }}"
        )


class _ClipRow(QWidget):
    """Single row in the file browser."""

    clicked = pyqtSignal(str)           # clip_id
    delete_requested = pyqtSignal(str)  # clip_id

    def __init__(
        self,
        clip_id: str,
        meta: ClipMetadata,
        is_selected: bool,
        has_annotation: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._clip_id = clip_id
        self._is_selected = is_selected
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui(meta, is_selected, has_annotation)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self, meta: ClipMetadata, is_selected: bool, has_annotation: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # ── Thumbnail ──────────────────────────────────────────────────
        thumb = QLabel("▶")
        thumb.setFixedSize(48, 32)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_bg = "#0A2040" if is_selected else "#1A1A1A"
        thumb_color = theme.ACCENT_BLUE if is_selected else theme.TEXT_MUTED
        thumb.setStyleSheet(
            f"QLabel {{ background: {thumb_bg}; border-radius: 3px;"
            f" color: {thumb_color}; font-size: 18px; }}"
        )

        # ── Info ───────────────────────────────────────────────────────
        # Wrap in a QWidget so the parent HBoxLayout can reliably
        # constrain the info column width without it overflowing due to
        # a long filename sizeHint.
        row_bg = theme.BG_ELEVATED if is_selected else theme.BG_PANEL
        info_widget = QWidget()
        info_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        info_widget.setStyleSheet(f"background: {row_bg};")
        info = QVBoxLayout(info_widget)
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(3)

        name = QLabel(meta.file_name)
        # Ignored policy: layout ignores sizeHint, so a long filename
        # can never push the indicator/delete button off the right edge.
        name.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        name.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 11px;"
            f" font-weight: 500; background: transparent; }}"
        )

        m, s = divmod(int(meta.duration_seconds), 60)
        w_px, _ = meta.resolution
        res_text = "4K" if w_px >= 3840 else ("FHD" if w_px >= 1920 else "HD")

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        meta_row.setContentsMargins(0, 0, 0, 0)

        dur_lbl = QLabel(f"{m}:{s:02d}")
        dur_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 10px;"
            f" background: transparent; }}"
        )
        res_badge = QLabel(res_text)
        res_badge.setStyleSheet(
            f"QLabel {{ background: #1A3D1A; color: {theme.ACCENT_GREEN};"
            f" font-size: 9px; font-weight: 600; border-radius: 3px; padding: 2px 5px; }}"
        )
        meta_row.addWidget(dur_lbl)
        meta_row.addWidget(res_badge)
        # No addStretch() — it made meta_row report Expanding preferred
        # width, inflating info's sizeHint and pushing icons off-screen.

        info.addWidget(name)
        info.addLayout(meta_row)

        # ── Annotation indicator (circle-check / circle) ───────────────
        indicator = QLabel()
        indicator.setFixedSize(16, 16)
        indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if has_annotation:
            indicator.setText("✓")
            indicator.setStyleSheet(
                f"QLabel {{ color: #FFFFFF; background: {theme.ACCENT_GREEN};"
                f" font-size: 9px; font-weight: 700; border-radius: 8px; }}"
            )
        else:
            indicator.setText("○")
            indicator.setStyleSheet(
                f"QLabel {{ color: {theme.TEXT_MUTED}; background: transparent; font-size: 14px; }}"
            )

        # ── Delete button (QLabel subclass — avoids macOS native button) ──
        self._delete_btn = _IconLabel("✕")
        self._delete_btn.setFixedSize(16, 16)
        self._delete_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._delete_btn.setToolTip("Remove from project")
        self._delete_btn.clicked.connect(self._on_delete_clicked)

        # ── Delete button — background matches row so it's always visible ─
        self._delete_btn.set_background(row_bg)

        layout.addWidget(thumb)
        layout.addWidget(info_widget, 1)
        layout.addWidget(indicator)
        layout.addWidget(self._delete_btn)

    # ------------------------------------------------------------------
    # Painting — paintEvent is the only reliable cross-platform way to
    # draw per-side borders on a plain QWidget on macOS.  CSS border-*
    # properties are silently ignored for QWidget subclasses unless
    # WA_StyledBackground is set, which triggers other side-effects.
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        try:
            if self._is_selected:
                painter.fillRect(self.rect(), QColor(theme.BG_ELEVATED))
                # Left accent border (2 px)
                painter.fillRect(0, 0, 2, self.height(), QColor(theme.ACCENT_BLUE))
                # Bottom accent border (1 px)
                painter.fillRect(
                    0, self.height() - 1, self.width(), 1, QColor(theme.ACCENT_BLUE)
                )
            else:
                painter.fillRect(self.rect(), QColor(theme.BG_PANEL))
                # Subtle bottom separator
                painter.fillRect(
                    0, self.height() - 1, self.width(), 1, QColor(theme.BORDER)
                )
        finally:
            painter.end()
        super().paintEvent(event)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _on_delete_clicked(self) -> None:
        self.delete_requested.emit(self._clip_id)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        # Suppress row-selection when the delete button was pressed
        if not self._delete_btn.geometry().contains(event.pos()):
            self.clicked.emit(self._clip_id)
        super().mousePressEvent(event)


class FileBrowserWidget(QWidget):
    """Left-panel clip list with import button.

    Signals:
        clip_selected(str): clip_id
        clip_delete_requested(str): clip_id the user wants to remove
        import_requested(Path): path chosen by the user
    """

    clip_selected = pyqtSignal(str)
    clip_delete_requested = pyqtSignal(str)
    import_requested = pyqtSignal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setStyleSheet(
            f"background: {theme.BG_PANEL}; border-right: 1px solid {theme.BORDER};"
        )
        self._clips: list[tuple[str, ClipMetadata]] = []
        self._annotated: set[str] = set()
        self._selected_id: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet(
            f"background: {theme.BG_PANEL}; border-bottom: 1px solid {theme.BORDER};"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 12, 0)

        title = QLabel("PROJECT FILES")
        title.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 10px; font-weight: 600;"
            f" letter-spacing: 1px; background: transparent; }}"
        )

        import_btn = QPushButton("+ Import")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.ACCENT_BLUE}; color: #FFFFFF;"
            f" font-size: 11px; font-weight: 500; border-radius: 4px; padding: 4px 8px; }}"
        )
        import_btn.clicked.connect(self._on_import_clicked)

        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(import_btn)
        layout.addWidget(header)

        # ── Scrollable clip list ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_clips(
        self,
        clips: list[tuple[str, ClipMetadata]],
        annotated_ids: set[str],
    ) -> None:
        self._clips = list(clips)
        self._annotated = set(annotated_ids)
        self._rebuild()

    def set_selected(self, clip_id: str | None) -> None:
        self._selected_id = clip_id
        self._rebuild()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (clip_id, meta) in enumerate(self._clips):
            row = _ClipRow(
                clip_id,
                meta,
                is_selected=(clip_id == self._selected_id),
                has_annotation=(clip_id in self._annotated),
            )
            row.clicked.connect(self._on_row_clicked)
            row.delete_requested.connect(self.clip_delete_requested)
            self._list_layout.insertWidget(i, row)

    def _on_row_clicked(self, clip_id: str) -> None:
        self._selected_id = clip_id
        self._rebuild()
        self.clip_selected.emit(clip_id)

    def _on_import_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Video Clip",
            str(Path.home()),
            "Video Files (*.mp4 *.mov *.m4v *.MP4 *.MOV *.M4V)",
        )
        if path:
            self.import_requested.emit(Path(path))
