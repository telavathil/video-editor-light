from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from vacation_editor.gui.annotation.controller import AnnotationController
from vacation_editor.gui.annotation.file_browser import FileBrowserWidget
from vacation_editor.gui.annotation.mark_bar import MarkBarWidget
from vacation_editor.gui.annotation.section_list import SectionListWidget
from vacation_editor.gui.annotation.timeline_widget import TimelineWidget
from vacation_editor.gui.annotation.transport_bar import TransportBarWidget
from vacation_editor.gui.annotation.video_player import VideoPlayerWidget


class AnnotationTab(QWidget):
    """Assembled annotation tab: file browser | center panel | section list."""

    def __init__(
        self,
        controller: AnnotationController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = controller
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        # Load initial clip list
        self._ctrl.refresh_clips()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left: file browser
        self._browser = FileBrowserWidget()
        layout.addWidget(self._browser)

        # Center: video + controls stack
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._player = VideoPlayerWidget()
        self._transport = TransportBarWidget()
        self._mark_bar = MarkBarWidget()
        self._timeline = TimelineWidget()

        center_layout.addWidget(self._player, 1)
        center_layout.addWidget(self._transport)
        center_layout.addWidget(self._mark_bar)
        center_layout.addWidget(self._timeline, 1)
        layout.addWidget(center, 1)

        # Right: section list
        self._section_list = SectionListWidget()
        layout.addWidget(self._section_list)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        ctrl = self._ctrl

        # File browser → controller
        self._browser.clip_selected.connect(ctrl.load_clip)
        self._browser.import_requested.connect(ctrl.import_clip)
        self._browser.clip_delete_requested.connect(self._on_delete_clip_requested)

        # Controller → file browser
        ctrl.clips_refreshed.connect(
            lambda clips: self._browser.set_clips(clips, set())
        )
        ctrl.annotated_ids_changed.connect(
            lambda ids: self._browser.set_clips(
                [(cid, meta) for cid, meta in self._browser._clips], ids
            )
        )
        ctrl.clip_loaded.connect(self._on_clip_loaded)

        # Video player → transport
        self._player.position_changed.connect(self._transport.set_position)
        self._player.duration_changed.connect(self._transport.set_duration)
        self._player.playback_state_changed.connect(self._transport.set_playback_state)

        # Video player → timeline
        self._player.position_changed.connect(self._timeline.set_position)
        self._player.duration_changed.connect(self._timeline.set_duration)

        # Transport → player
        self._transport.seek_requested.connect(self._player.seek)
        self._transport.play_pause_toggled.connect(self._player.toggle_play_pause)
        self._transport.skip_to_start.connect(lambda: self._player.seek(0.0))
        self._transport.speed_changed.connect(self._player.set_speed)

        # Mark bar
        self._mark_bar.mark_in_clicked.connect(
            lambda: ctrl.mark_in(self._player.get_position())
        )
        self._mark_bar.mark_out_clicked.connect(
            lambda: ctrl.mark_out(self._player.get_position())
        )

        # Controller → mark bar + player overlay
        ctrl.mark_in_updated.connect(self._mark_bar.set_mark_in)
        ctrl.mark_in_updated.connect(self._player.set_mark_in_overlay)

        # Timeline → player + controller
        self._timeline.seek_requested.connect(self._player.seek)
        self._timeline.section_trimmed.connect(ctrl.trim_section)

        # Section list → player + controller
        self._section_list.section_selected.connect(
            lambda s: self._player.seek(s.start_seconds)
        )
        self._section_list.section_deleted.connect(ctrl.delete_section)
        self._section_list.section_play_requested.connect(self._play_section)

        # Controller → section list + timeline
        ctrl.sections_updated.connect(self._section_list.set_sections)
        ctrl.sections_updated.connect(self._timeline.set_sections)

    # ------------------------------------------------------------------
    # Keyboard shortcuts (macOS conventions)
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        def shortcut(key: str, slot) -> None:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(slot)

        shortcut("Space", self._player.toggle_play_pause)
        shortcut("I", lambda: self._ctrl.mark_in(self._player.get_position()))
        shortcut("O", lambda: self._ctrl.mark_out(self._player.get_position()))
        shortcut("Left", lambda: self._player.seek(max(0.0, self._player.get_position() - 1.0)))
        shortcut("Right", lambda: self._player.seek(self._player.get_position() + 1.0))
        shortcut(
            "Shift+Left",
            lambda: self._player.seek(max(0.0, self._player.get_position() - 5.0)),
        )
        shortcut("Shift+Right", lambda: self._player.seek(self._player.get_position() + 5.0))
        shortcut("J", lambda: self._player.seek(max(0.0, self._player.get_position() - 5.0)))
        shortcut("K", self._player.pause)
        shortcut("L", lambda: self._player.seek(self._player.get_position() + 5.0))
        shortcut("Ctrl+S", self._ctrl.save_now)
        shortcut("Ctrl+Z", self._ctrl.undo)
        shortcut("Ctrl+Shift+Z", self._ctrl.redo)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _on_clip_loaded(self, clip_id: str, duration: float) -> None:
        path = self._ctrl.get_local_path(clip_id)
        self._player.load_clip(path)
        self._browser.set_selected(clip_id)

    def _on_delete_clip_requested(self, clip_id: str) -> None:
        reply = QMessageBox.question(
            self,
            "Remove Clip",
            "Remove this clip from the project?\n"
            "This will also delete its video file and annotations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_clip(clip_id)

    def _play_section(self, section) -> None:
        self._player.seek(section.start_seconds)
        self._player.play()
        # TODO Phase 2: stop playback at section.end_seconds via QTimer
