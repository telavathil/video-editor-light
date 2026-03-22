from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from vacation_editor.models.composition import Composition, CompositionSection, ExportSettings
from vacation_editor.models.job import JobStatus

if TYPE_CHECKING:
    from vacation_editor.models.composition import TransitionType
    from vacation_editor.services.protocols.annotation_store import AnnotationStore
    from vacation_editor.services.protocols.composition_processor import CompositionProcessor
    from vacation_editor.services.protocols.video_storage import VideoStorage

logger = logging.getLogger(__name__)

_POLL_INTERVAL_MS = 500


class CompositionController(QObject):
    """Coordinates all composition-tab state: building the section list,
    transitions, and export.

    Providers are injected — never instantiated here.

    Signals:
        composition_changed(Composition): emitted on any change to the composition
        available_sections_changed(list): list of (clip_id, section_id, label) tuples
        job_status_changed(JobStatus | None): export job polling updates
    """

    composition_changed = pyqtSignal(object)           # Composition
    available_sections_changed = pyqtSignal(list)      # list[tuple[str, str, str, float]]
    job_status_changed = pyqtSignal(object)            # JobStatus | None

    def __init__(
        self,
        processor: CompositionProcessor,
        annotation_store: AnnotationStore,
        video_storage: VideoStorage,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._processor = processor
        self._annotation_store = annotation_store
        self._video_storage = video_storage
        self._composition = Composition.new("My Highlight")
        self._current_job_id: str | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_job)

    # ------------------------------------------------------------------
    # Section library
    # ------------------------------------------------------------------

    def refresh_available_sections(self) -> None:
        """Reload available annotated sections from the annotation store.

        Emits available_sections_changed with a list of
        (clip_id, section_id, clip_name, duration_seconds) tuples.
        """
        items: list[tuple[str, str, str, float]] = []
        for clip_id in self._annotation_store.list_annotated_clips():
            try:
                meta = self._video_storage.get_metadata(clip_id)
                annotation = self._annotation_store.load(clip_id)
            except Exception:
                logger.warning("Could not load clip %r for composition library", clip_id)
                continue
            for section in annotation.sections:
                duration = section.end_seconds - section.start_seconds
                items.append((clip_id, section.section_id, meta.file_name, duration))
        self.available_sections_changed.emit(items)

    # ------------------------------------------------------------------
    # Composition mutations
    # ------------------------------------------------------------------

    def add_section(self, clip_id: str, section_id: str) -> None:
        """Append a section to the composition."""
        new_section = CompositionSection(
            clip_id=clip_id,
            section_id=section_id,
            order=len(self._composition.sections),
        )
        self._composition = self._composition.with_section_appended(new_section)
        self.composition_changed.emit(self._composition)

    def remove_section(self, index: int) -> None:
        self._composition = self._composition.with_section_removed(index)
        self.composition_changed.emit(self._composition)

    def reorder_sections(self, new_order: list[int]) -> None:
        self._composition = self._composition.with_sections_reordered(new_order)
        self.composition_changed.emit(self._composition)

    def update_transition(
        self,
        index: int,
        transition: TransitionType,
        duration_ms: int | None = None,
    ) -> None:
        self._composition = self._composition.with_transition_updated(
            index, transition, duration_ms
        )
        self.composition_changed.emit(self._composition)

    def clear_composition(self) -> None:
        self._composition = Composition.new("My Highlight")
        self.composition_changed.emit(self._composition)

    def get_composition(self) -> Composition:
        return self._composition

    def get_preview_clips(self) -> list[tuple[Path, float, float, str, int]]:
        """Return (path, start_s, end_s, transition, duration_ms) for each section."""
        sections = sorted(self._composition.sections, key=lambda s: s.order)
        result: list[tuple[Path, float, float, str, int]] = []
        for section in sections:
            info = self.get_section_info(section.clip_id, section.section_id)
            if info is None:
                continue
            _clip_name, start, end = info
            try:
                path = self._video_storage.get_local_path(section.clip_id)
                result.append((path, start, end, section.transition, section.transition_duration_ms))
            except Exception:
                logger.warning("Could not get local path for clip %r", section.clip_id)
        return result

    def get_section_info(
        self, clip_id: str, section_id: str
    ) -> tuple[str, float, float] | None:
        """Return (file_name, start_seconds, end_seconds) or None if not found."""
        try:
            meta = self._video_storage.get_metadata(clip_id)
            annotation = self._annotation_store.load(clip_id)
        except Exception:
            return None
        section = next(
            (s for s in annotation.sections if s.section_id == section_id), None
        )
        if section is None:
            return None
        return (meta.file_name, section.start_seconds, section.end_seconds)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def start_export(self, export_settings: ExportSettings) -> None:
        """Submit the composition for export and start polling."""
        if not self._composition.sections:
            return
        self._current_job_id = self._processor.submit(
            self._composition, export_settings
        )
        self._poll_timer.start()
        self.job_status_changed.emit(
            JobStatus(job_id=self._current_job_id)
        )

    def cancel_export(self) -> None:
        if self._current_job_id is not None:
            self._processor.cancel(self._current_job_id)

    def get_export_output_path(self) -> Path | None:
        if self._current_job_id is None:
            return None
        try:
            return self._processor.get_result(self._current_job_id)
        except (RuntimeError, KeyError):
            return None

    def get_default_export_path(self) -> str:
        return str(
            Path.home()
            / "Desktop"
            / f"{self._composition.composition_id[:8]}_highlight.mp4"
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _poll_job(self) -> None:
        if self._current_job_id is None:
            self._poll_timer.stop()
            return
        try:
            status = self._processor.poll(self._current_job_id)
        except KeyError:
            self._poll_timer.stop()
            return
        self.job_status_changed.emit(status)
        if status.is_done:
            self._poll_timer.stop()
