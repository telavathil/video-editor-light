from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from vacation_editor.models.annotation import ClipAnnotation, Section
from vacation_editor.models.clip import ClipMetadata

if TYPE_CHECKING:
    from vacation_editor.services.protocols.annotation_store import AnnotationStore
    from vacation_editor.services.protocols.video_storage import VideoStorage

logger = logging.getLogger(__name__)

_AUTOSAVE_DELAY_MS = 2000
_MAX_UNDO = 50


class AnnotationController(QObject):
    """Coordinates all annotation-tab state: loading clips, marking sections,
    auto-saving, and undo/redo.

    All providers are injected via constructor — never instantiated here.

    Signals:
        clip_loaded(str, float): clip_id, duration_seconds
        clips_refreshed(list): list of (clip_id, ClipMetadata) tuples
        annotated_ids_changed(set): set of clip_ids with saved annotations
        sections_updated(list): current list[Section] after any change
        mark_in_updated(object): float | None  — pending mark-in position
        save_status_changed(str): "saving" | "saved" | "error"
    """

    clip_loaded = pyqtSignal(str, float)
    clips_refreshed = pyqtSignal(list)
    annotated_ids_changed = pyqtSignal(object)
    sections_updated = pyqtSignal(list)
    mark_in_updated = pyqtSignal(object)
    save_status_changed = pyqtSignal(str)

    def __init__(
        self,
        video_storage: VideoStorage,
        annotation_store: AnnotationStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._storage = video_storage
        self._store = annotation_store
        self._current_clip_id: str | None = None
        self._annotation: ClipAnnotation | None = None
        self._mark_in: float | None = None
        self._undo_stack: list[ClipAnnotation] = []
        self._redo_stack: list[ClipAnnotation] = []

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)

    # ------------------------------------------------------------------
    # Clip management
    # ------------------------------------------------------------------

    def refresh_clips(self) -> None:
        """Reload clip list and annotated-ids from storage."""
        clip_ids = self._storage.list_clips()
        clips: list[tuple[str, ClipMetadata]] = []
        for cid in clip_ids:
            try:
                clips.append((cid, self._storage.get_metadata(cid)))
            except KeyError:
                logger.warning("Clip %r has no metadata file — attempting to re-probe…", cid)
                try:
                    self._storage.heal(cid)
                    clips.append((cid, self._storage.get_metadata(cid)))
                    logger.info("Successfully healed metadata for clip %r", cid)
                except Exception as exc:
                    logger.warning("Skipping clip %r: could not heal metadata: %s", cid, exc)
        annotated = set(self._store.list_annotated_clips())
        self.clips_refreshed.emit(clips)
        self.annotated_ids_changed.emit(annotated)

    def load_clip(self, clip_id: str) -> None:
        """Load a clip into the player and restore its annotation."""
        if clip_id == self._current_clip_id:
            return
        # Save any unsaved work on current clip first
        if self._annotation and self._save_timer.isActive():
            self._do_save()

        self._current_clip_id = clip_id
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._mark_in = None
        self.mark_in_updated.emit(None)

        # Load or create annotation
        try:
            self._annotation = self._store.load(clip_id)
        except KeyError:
            self._annotation = ClipAnnotation(clip_id=clip_id)

        meta = self._storage.get_metadata(clip_id)
        self.clip_loaded.emit(clip_id, meta.duration_seconds)
        self.sections_updated.emit(list(self._annotation.sections))

    def get_local_path(self, clip_id: str) -> Path:
        return self._storage.get_local_path(clip_id)

    def delete_clip(self, clip_id: str) -> None:
        """Permanently remove a clip from storage and refresh the clip list."""
        if clip_id == self._current_clip_id:
            self._current_clip_id = None
            self._annotation = None
            self._mark_in = None
            self._undo_stack.clear()
            self._redo_stack.clear()
            self.mark_in_updated.emit(None)
            self.sections_updated.emit([])
        try:
            self._storage.delete(clip_id)
        except Exception as exc:
            logger.error("Delete clip failed for %r: %s", clip_id, exc)
            return
        self.refresh_clips()

    def import_clip(self, path: Path) -> None:
        """Copy a video file into the project and refresh the clip list."""
        clip_id = ClipMetadata.make_clip_id(path)
        try:
            self._storage.upload(path, clip_id)
        except Exception as exc:
            logger.error("Import failed: %s", exc)
            return
        self.refresh_clips()

    # ------------------------------------------------------------------
    # Mark in / out
    # ------------------------------------------------------------------

    def mark_in(self, position: float) -> None:
        self._mark_in = position
        self.mark_in_updated.emit(position)

    def mark_out(self, position: float) -> None:
        if self._mark_in is None or self._annotation is None:
            return
        if position <= self._mark_in:
            return
        section = Section.new(self._mark_in, position)
        self._push_undo()
        self._annotation = self._annotation.with_section_added(section)
        self._mark_in = None
        self.mark_in_updated.emit(None)
        self.sections_updated.emit(list(self._annotation.sections))
        self._schedule_save()

    # ------------------------------------------------------------------
    # Section operations
    # ------------------------------------------------------------------

    def delete_section(self, section_id: str) -> None:
        if self._annotation is None:
            return
        self._push_undo()
        self._annotation = self._annotation.with_section_removed(section_id)
        self.sections_updated.emit(list(self._annotation.sections))
        self._schedule_save()

    def trim_section(self, section_id: str, start: float, end: float) -> None:
        if self._annotation is None:
            return
        sec = next((s for s in self._annotation.sections if s.section_id == section_id), None)
        if sec is None:
            return
        self._push_undo()
        updated = sec.with_times(start, end)
        self._annotation = self._annotation.with_section_updated(updated)
        self.sections_updated.emit(list(self._annotation.sections))
        self._schedule_save()

    # ------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------

    def undo(self) -> None:
        if not self._undo_stack or self._annotation is None:
            return
        self._redo_stack.append(self._annotation)
        self._annotation = self._undo_stack.pop()
        self.sections_updated.emit(list(self._annotation.sections))
        self._schedule_save()

    def redo(self) -> None:
        if not self._redo_stack or self._annotation is None:
            return
        self._undo_stack.append(self._annotation)
        self._annotation = self._redo_stack.pop()
        self.sections_updated.emit(list(self._annotation.sections))
        self._schedule_save()

    def save_now(self) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
        self._do_save()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _push_undo(self) -> None:
        if self._annotation is not None:
            self._undo_stack.append(self._annotation)
            if len(self._undo_stack) > _MAX_UNDO:
                self._undo_stack.pop(0)
            self._redo_stack.clear()

    def _schedule_save(self) -> None:
        self.save_status_changed.emit("saving")
        self._save_timer.start(_AUTOSAVE_DELAY_MS)

    def _do_save(self) -> None:
        if self._annotation is None:
            return
        try:
            self._store.save(self._annotation)
            self.save_status_changed.emit("saved")
            # Refresh annotated indicators
            annotated = set(self._store.list_annotated_clips())
            self.annotated_ids_changed.emit(annotated)
        except Exception as exc:
            logger.error("Auto-save failed: %s", exc)
            self.save_status_changed.emit("error")
