from __future__ import annotations

import subprocess
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vacation_editor.gui import theme
from vacation_editor.models.composition import ExportSettings

if TYPE_CHECKING:
    from vacation_editor.models.job import JobStatus


class ExportDialog(QDialog):
    """Export dialog — two visual states: in-progress and complete.

    Signals:
        export_confirmed(ExportSettings): user clicked Export
        cancel_requested: user clicked Cancel Export
    """

    export_confirmed = pyqtSignal(object)  # ExportSettings
    cancel_requested = pyqtSignal()

    def __init__(
        self,
        default_output_path: str,
        codec: str = "h264",
        fps: int = 24,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._codec = codec
        self._fps = fps
        self._start_time: float | None = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

        self.setModal(True)
        self.setFixedWidth(520)
        self.setWindowTitle("Export Video")
        self.setStyleSheet(
            f"QDialog {{ background: {theme.BG_ELEVATED}; }}"
        )
        self._setup_ui(default_output_path)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self, default_output_path: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Config page ---
        self._config_page = QWidget()
        config_layout = QVBoxLayout(self._config_page)
        config_layout.setContentsMargins(24, 24, 24, 0)
        config_layout.setSpacing(16)

        title = QLabel("Export Video")
        title.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 15px; font-weight: 700; }}"
        )
        config_layout.addWidget(title)

        # Output file row
        out_row = QHBoxLayout()
        self._output_edit = QLineEdit(default_output_path)
        self._output_edit.setStyleSheet(
            f"QLineEdit {{ background: {theme.BG_INPUT}; color: {theme.TEXT_PRIMARY};"
            f"border: none; border-radius: 6px; padding: 6px 10px; font-size: 11px; }}"
        )
        out_row.addWidget(self._output_edit, 1)
        choose_btn = QPushButton("Choose…")
        choose_btn.setFixedSize(72, 30)
        choose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        choose_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.BG_INPUT}; color: {theme.TEXT_PRIMARY};"
            f"font-size: 11px; border-radius: 6px; }}"
            f"QPushButton:hover {{ background: {theme.BORDER}; }}"
        )
        choose_btn.clicked.connect(self._on_choose)
        out_row.addWidget(choose_btn)
        config_layout.addLayout(out_row)

        config_layout.addStretch()
        layout.addWidget(self._config_page)

        # --- Progress page ---
        self._progress_page = QWidget()
        self._progress_page.hide()
        prog_layout = QVBoxLayout(self._progress_page)
        prog_layout.setContentsMargins(24, 24, 24, 0)
        prog_layout.setSpacing(12)

        prog_title = QLabel("Exporting…")
        prog_title.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 15px; font-weight: 700; }}"
        )
        prog_layout.addWidget(prog_title)

        self._step_label = QLabel("Preparing…")
        self._step_label.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 11px; }}"
        )
        prog_layout.addWidget(self._step_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {theme.BG_INPUT}; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {theme.ACCENT_BLUE}; border-radius: 3px; }}"
        )
        prog_layout.addWidget(self._progress_bar)

        self._elapsed_label = QLabel("Elapsed: 0s")
        self._elapsed_label.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 10px; }}"
        )
        prog_layout.addWidget(self._elapsed_label)
        prog_layout.addStretch()
        layout.addWidget(self._progress_page)

        # --- Complete page ---
        self._complete_page = QWidget()
        self._complete_page.hide()
        done_layout = QVBoxLayout(self._complete_page)
        done_layout.setContentsMargins(24, 24, 24, 0)
        done_layout.setSpacing(12)
        done_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        checkmark = QLabel("✓")
        checkmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkmark.setStyleSheet(
            f"QLabel {{ color: {theme.ACCENT_GREEN}; font-size: 36px; }}"
        )
        done_layout.addWidget(checkmark)

        done_title = QLabel("Your video is ready")
        done_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        done_title.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_PRIMARY}; font-size: 15px; font-weight: 700; }}"
        )
        done_layout.addWidget(done_title)

        self._done_elapsed = QLabel("")
        self._done_elapsed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_elapsed.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_MUTED}; font-size: 11px; }}"
        )
        done_layout.addWidget(self._done_elapsed)

        self._output_path_lbl = QLabel("")
        self._output_path_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._output_path_lbl.setStyleSheet(
            f"QLabel {{ color: {theme.TEXT_SECONDARY}; font-size: 10px; }}"
        )
        done_layout.addWidget(self._output_path_lbl)
        done_layout.addStretch()
        layout.addWidget(self._complete_page)

        # --- Footer (shared) ---
        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet(
            f"QWidget {{ background: {theme.BG_ELEVATED};"
            f"border-top: 1px solid {theme.BORDER}; }}"
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 0, 24, 0)
        footer_layout.setSpacing(8)

        self._cancel_btn = QPushButton("Cancel Export")
        self._cancel_btn.setFixedHeight(36)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {theme.ACCENT_RED};"
            f"font-size: 12px; border-radius: 6px; border: 1px solid {theme.ACCENT_RED}; }}"
            f"QPushButton:hover {{ background: rgba(255,69,58,0.1); }}"
        )
        self._cancel_btn.clicked.connect(self._on_cancel)
        footer_layout.addWidget(self._cancel_btn)

        footer_layout.addStretch()

        self._action_btn = QPushButton("Export")
        self._action_btn.setFixedSize(100, 36)
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.ACCENT_BLUE}; color: {theme.TEXT_PRIMARY};"
            f"font-size: 12px; font-weight: 600; border-radius: 6px; }}"
            f"QPushButton:hover {{ background: #1A94FF; }}"
        )
        self._action_btn.clicked.connect(self._on_export)
        footer_layout.addWidget(self._action_btn)

        self._done_btn = QPushButton("Done")
        self._done_btn.setFixedSize(80, 36)
        self._done_btn.hide()
        self._done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._done_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.ACCENT_BLUE}; color: {theme.TEXT_PRIMARY};"
            f"font-size: 12px; font-weight: 600; border-radius: 6px; }}"
        )
        self._done_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self._done_btn)

        self._reveal_btn = QPushButton("Reveal in Finder")
        self._reveal_btn.hide()
        self._reveal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reveal_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {theme.TEXT_SECONDARY};"
            f"font-size: 11px; border-radius: 6px;"
            f"border: 1px solid {theme.BORDER}; padding: 0 12px; }}"
        )
        self._reveal_btn.clicked.connect(self._on_reveal)
        footer_layout.insertWidget(2, self._reveal_btn)

        layout.addWidget(footer)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_job_status(self, status: JobStatus) -> None:
        """Called repeatedly as the export job progresses."""
        if status.is_complete:
            self._elapsed_timer.stop()
            elapsed = int(time.time() - (self._start_time or time.time()))
            self._done_elapsed.setText(f"Completed in {elapsed}s")
            if status.result_path:
                self._output_path_lbl.setText(status.result_path)
            self._show_complete_page()
        elif status.is_failed:
            self._elapsed_timer.stop()
            self._step_label.setText(f"Failed: {status.error_message}")
            self._cancel_btn.setText("Close")
        else:
            pct = int(status.progress_percent)
            self._progress_bar.setValue(pct)
            self._step_label.setText(_step_label(pct))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_choose(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Export", self._output_edit.text(), "MP4 Video (*.mp4)"
        )
        if path:
            self._output_edit.setText(path)

    def _on_export(self) -> None:
        settings = ExportSettings(
            output_path=self._output_edit.text(),
            codec=self._codec,
            fps=self._fps,
            hw_encoding=True,
        )
        self._start_time = time.time()
        self._show_progress_page()
        self._elapsed_timer.start()
        self.export_confirmed.emit(settings)

    def _on_cancel(self) -> None:
        self.cancel_requested.emit()
        self.reject()

    def _on_reveal(self) -> None:
        path = self._output_path_lbl.text()
        if path:
            subprocess.run(["open", "-R", path], check=False)

    def _show_progress_page(self) -> None:
        self._config_page.hide()
        self._progress_page.show()
        self._action_btn.hide()

    def _show_complete_page(self) -> None:
        self._progress_page.hide()
        self._complete_page.show()
        self._cancel_btn.hide()
        self._done_btn.show()
        self._reveal_btn.show()
        self.adjustSize()

    def _update_elapsed(self) -> None:
        if self._start_time is not None:
            elapsed = int(time.time() - self._start_time)
            self._elapsed_label.setText(f"Elapsed: {elapsed}s")


def _step_label(pct: int) -> str:
    if pct < 50:
        return f"Extracting sections… {pct}%"
    if pct < 70:
        return f"Normalizing… {pct}%"
    if pct < 90:
        return f"Applying transitions… {pct}%"
    return f"Encoding… {pct}%"
