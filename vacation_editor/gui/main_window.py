from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme
from vacation_editor.gui.annotation.controller import AnnotationController
from vacation_editor.gui.annotation.tab import AnnotationTab
from vacation_editor.utils.providers import (
    build_annotation_store,
    build_video_storage,
)

if TYPE_CHECKING:
    from vacation_editor.config import AppConfig

# Import QMainWindow properly (not for type checking only)
from PyQt6.QtWidgets import QMainWindow


class _TabButton(QPushButton):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(False)

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self._update_style(active)

    def _update_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(
                f"color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
                f"background: transparent; padding: 0 14px;"
                f"border-bottom: 2px solid {theme.ACCENT_BLUE}; border-radius: 0;"
            )
        else:
            self.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 12px; font-weight: normal;"
                f"background: transparent; padding: 0 14px;"
                f"border-bottom: 2px solid transparent; border-radius: 0;"
            )


class _TabBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(
            f"background: {theme.BG_PANEL};"
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        self._tabs: list[_TabButton] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("VACATION EDITOR")
        logo.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 11px; font-weight: 700;"
            f"letter-spacing: 1px; background: transparent;"
            f"padding: 0 20px;"
        )
        layout.addWidget(logo)

        # Tab buttons
        for name in ("Annotation", "Composition", "Music"):
            btn = _TabButton(name)
            btn.setFixedHeight(44)
            self._tabs.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Status dot
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            f"color: {theme.ACCENT_GREEN}; font-size: 10px; background: transparent;"
        )
        layout.addWidget(self._status_dot)

    def connect_tabs(self, stack: QStackedWidget) -> None:
        for i, btn in enumerate(self._tabs):
            btn.clicked.connect(lambda _checked, idx=i: self._switch(idx, stack))
        self._switch(0, stack)

    def _switch(self, index: int, stack: QStackedWidget) -> None:
        for i, btn in enumerate(self._tabs):
            btn.set_active(i == index)
        stack.setCurrentIndex(index)

    def set_status(self, text: str, color: str = theme.TEXT_SECONDARY) -> None:
        self._status_dot.setText(text)
        self._status_dot.setStyleSheet(
            f"color: {color}; font-size: 10px; background: transparent;"
        )


class _PlaceholderTab(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)


class MainWindow(QMainWindow):
    """Application shell: tab bar + content tabs.

    Providers are built here — the single place where local vs. cloud is decided.
    Controllers are created here and injected into tabs.
    """

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setWindowTitle("Vacation Editor")
        self.resize(1440, 900)
        self.setMinimumSize(1024, 600)

        # Build providers (single instantiation point)
        storage = build_video_storage(config)
        store = build_annotation_store(config)

        # Build controllers
        self._annotation_ctrl = AnnotationController(storage, store, parent=self)

        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab bar
        self._tab_bar = _TabBar()
        layout.addWidget(self._tab_bar)

        # Content stack
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # Annotation tab (Phase 1)
        annotation_tab = AnnotationTab(self._annotation_ctrl)
        self._stack.addWidget(annotation_tab)

        # Placeholder tabs for Phase 2 + 3
        self._stack.addWidget(_PlaceholderTab("Composition Engine — coming in Phase 2"))
        self._stack.addWidget(_PlaceholderTab("Music Sync — coming in Phase 3"))

        self._tab_bar.connect_tabs(self._stack)

        # Status bar
        status = QStatusBar()
        status.setStyleSheet(
            f"background: {theme.BG_PANEL}; color: {theme.TEXT_SECONDARY};"
            f"border-top: 1px solid {theme.BORDER}; font-size: 11px;"
        )
        self.setStatusBar(status)

        # Wire save status → status bar
        self._annotation_ctrl.save_status_changed.connect(self._on_save_status)

    def _on_save_status(self, status: str) -> None:
        messages = {
            "saving": "Saving…",
            "saved": "All changes saved",
            "error": "Save failed — check logs",
        }
        self.statusBar().showMessage(messages.get(status, status), 3000)
