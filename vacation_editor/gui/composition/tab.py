from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QHBoxLayout, QWidget

from vacation_editor.gui.composition.controller import CompositionController
from vacation_editor.gui.composition.export_dialog import ExportDialog
from vacation_editor.gui.composition.section_library import SectionLibraryWidget
from vacation_editor.gui.composition.sequence_track import SequenceTrackWidget
from vacation_editor.gui.composition.transition_picker import TransitionPickerWidget

if TYPE_CHECKING:
    from vacation_editor.models.composition import Composition
    from vacation_editor.models.job import JobStatus


class CompositionTab(QWidget):
    """Assembled composition tab: section library | sequence track | transition picker."""

    def __init__(
        self,
        controller: CompositionController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = controller
        self._section_info_cache: dict[str, tuple[str, float, float]] = {}
        # section_id -> (clip_name, start, end)
        self._selected_index: int | None = None
        self._export_dialog: ExportDialog | None = None

        self._setup_ui()
        self._connect_signals()
        self._ctrl.refresh_available_sections()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._library = SectionLibraryWidget()
        layout.addWidget(self._library)

        self._sequence = SequenceTrackWidget()
        layout.addWidget(self._sequence, 1)

        self._picker = TransitionPickerWidget()
        layout.addWidget(self._picker)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        ctrl = self._ctrl

        # Library → controller
        self._library.section_add_requested.connect(self._on_section_add_requested)

        # Sequence → controller + picker
        self._sequence.section_selected.connect(self._on_section_selected)
        self._sequence.section_remove_requested.connect(ctrl.remove_section)
        self._sequence.clear_requested.connect(ctrl.clear_composition)
        self._sequence.preview_requested.connect(self._on_preview_requested)

        # Picker → controller
        self._picker.transition_changed.connect(self._on_transition_changed)
        self._picker.export_requested.connect(self._on_export_requested)

        # Controller → UI
        ctrl.composition_changed.connect(self._on_composition_changed)
        ctrl.available_sections_changed.connect(self._on_available_sections_changed)
        ctrl.job_status_changed.connect(self._on_job_status_changed)

        # Initial export button state
        self._picker.set_export_enabled(False)

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_section_add_requested(self, clip_id: str, section_id: str) -> None:
        self._ctrl.add_section(clip_id, section_id)
        # Pre-cache info
        info = self._ctrl.get_section_info(clip_id, section_id)
        if info:
            self._section_info_cache[section_id] = info

    def _on_section_selected(self, index: int) -> None:
        self._selected_index = index
        composition = self._ctrl.get_composition()
        sections = sorted(composition.sections, key=lambda s: s.order)
        if index >= len(sections):
            return
        comp_sec = sections[index]
        info = self._section_info_cache.get(comp_sec.section_id)
        self._picker.set_selected_section(comp_sec.section_id, info)
        self._picker.set_section_transition(comp_sec)

    def _on_transition_changed(self, transition: str, duration_ms: int) -> None:
        if self._selected_index is None:
            return
        self._ctrl.update_transition(
            self._selected_index,
            transition,  # type: ignore[arg-type]
            duration_ms,
        )

    def _on_preview_requested(self) -> None:
        clips = self._ctrl.get_preview_clips()
        if not clips:
            return
        from vacation_editor.gui.composition.preview_dialog import CompositionPreviewDialog
        dialog = CompositionPreviewDialog(clips, parent=self)
        dialog.exec()

    def _on_export_requested(self) -> None:
        default_path = self._ctrl.get_default_export_path()
        self._export_dialog = ExportDialog(
            default_output_path=default_path,
            codec=self._picker.get_codec(),
            fps=self._picker.get_fps(),
            parent=self,
        )
        self._export_dialog.export_confirmed.connect(self._ctrl.start_export)
        self._export_dialog.cancel_requested.connect(self._ctrl.cancel_export)
        self._export_dialog.exec()

    def _on_composition_changed(self, composition: Composition) -> None:
        self._sequence.set_composition(composition, self._section_info_cache)
        has_sections = bool(composition.sections)
        self._picker.set_export_enabled(has_sections)

        # Re-sync section library to reflect "added" state
        self._ctrl.refresh_available_sections()

    def _on_available_sections_changed(
        self, items: list[tuple[str, str, str, float]]
    ) -> None:
        composition = self._ctrl.get_composition()
        added_ids = {s.section_id for s in composition.sections}

        # Update section info cache
        for clip_id, section_id, clip_name, duration in items:
            info = self._ctrl.get_section_info(clip_id, section_id)
            if info:
                self._section_info_cache[section_id] = info

        self._library.set_sections(items, added_ids)

    def _on_job_status_changed(self, status: JobStatus | None) -> None:
        if self._export_dialog is not None and status is not None:
            self._export_dialog.update_job_status(status)
