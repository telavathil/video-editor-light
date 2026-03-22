from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vacation_editor.gui.composition.controller import CompositionController
from vacation_editor.models.annotation import ClipAnnotation
from vacation_editor.models.clip import ClipMetadata
from vacation_editor.models.composition import Composition, ExportSettings
from vacation_editor.models.job import JobStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(sample_metadata: ClipMetadata) -> MagicMock:
    mock = MagicMock()
    mock.get_metadata.return_value = sample_metadata
    return mock


@pytest.fixture
def store(sample_annotation: ClipAnnotation) -> MagicMock:
    mock = MagicMock()
    mock.list_annotated_clips.return_value = ["abc123"]
    mock.load.return_value = sample_annotation
    return mock


@pytest.fixture
def processor() -> MagicMock:
    mock = MagicMock()
    mock.submit.return_value = "job-001"
    mock.poll.return_value = JobStatus(
        job_id="job-001", status="running", progress_percent=25.0
    )
    return mock


@pytest.fixture
def ctrl(qtbot, processor, store, storage) -> CompositionController:
    return CompositionController(processor, store, storage)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_composition_starts_empty(self, ctrl: CompositionController) -> None:
        assert ctrl.get_composition().sections == []

    def test_composition_has_name(self, ctrl: CompositionController) -> None:
        assert ctrl.get_composition().name == "My Highlight"


# ---------------------------------------------------------------------------
# Composition mutations
# ---------------------------------------------------------------------------


class TestAddSection:
    def test_add_section_appends_to_composition(
        self, ctrl: CompositionController
    ) -> None:
        ctrl.add_section("abc123", "section-1")
        comp = ctrl.get_composition()
        assert len(comp.sections) == 1
        assert comp.sections[0].clip_id == "abc123"
        assert comp.sections[0].section_id == "section-1"

    def test_add_section_emits_composition_changed(
        self, ctrl: CompositionController, qtbot
    ) -> None:
        with qtbot.waitSignal(ctrl.composition_changed, timeout=500) as blocker:
            ctrl.add_section("abc123", "section-1")
        emitted: Composition = blocker.args[0]
        assert len(emitted.sections) == 1

    def test_add_multiple_sections_assigns_correct_order(
        self, ctrl: CompositionController
    ) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.add_section("abc123", "s2")
        comp = ctrl.get_composition()
        orders = [s.order for s in comp.sections]
        assert orders == [0, 1]


class TestRemoveSection:
    def test_remove_section_reduces_count(
        self, ctrl: CompositionController
    ) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.add_section("abc123", "s2")
        ctrl.remove_section(0)
        assert len(ctrl.get_composition().sections) == 1

    def test_remove_section_reorders(self, ctrl: CompositionController) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.add_section("abc123", "s2")
        ctrl.remove_section(0)
        comp = ctrl.get_composition()
        assert comp.sections[0].order == 0

    def test_remove_emits_signal(self, ctrl: CompositionController, qtbot) -> None:
        ctrl.add_section("abc123", "s1")
        with qtbot.waitSignal(ctrl.composition_changed, timeout=500):
            ctrl.remove_section(0)


class TestUpdateTransition:
    def test_update_transition_type(self, ctrl: CompositionController) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.add_section("abc123", "s2")
        ctrl.update_transition(1, "cut")
        comp = ctrl.get_composition()
        assert comp.sections[1].transition == "cut"

    def test_update_transition_duration(self, ctrl: CompositionController) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.add_section("abc123", "s2")
        ctrl.update_transition(1, "dissolve", 1000)
        comp = ctrl.get_composition()
        assert comp.sections[1].transition_duration_ms == 1000

    def test_update_transition_emits_signal(
        self, ctrl: CompositionController, qtbot
    ) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.add_section("abc123", "s2")
        with qtbot.waitSignal(ctrl.composition_changed, timeout=500):
            ctrl.update_transition(1, "fade_to_black")


class TestClearComposition:
    def test_clear_resets_to_empty(self, ctrl: CompositionController) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.clear_composition()
        assert ctrl.get_composition().sections == []

    def test_clear_emits_signal(self, ctrl: CompositionController, qtbot) -> None:
        ctrl.add_section("abc123", "s1")
        with qtbot.waitSignal(ctrl.composition_changed, timeout=500):
            ctrl.clear_composition()


# ---------------------------------------------------------------------------
# Section library
# ---------------------------------------------------------------------------


class TestRefreshAvailableSections:
    def test_emits_items_for_annotated_clips(
        self, ctrl: CompositionController, qtbot, sample_annotation: ClipAnnotation
    ) -> None:
        with qtbot.waitSignal(ctrl.available_sections_changed, timeout=500) as blocker:
            ctrl.refresh_available_sections()
        items: list = blocker.args[0]
        assert len(items) == len(sample_annotation.sections)
        clip_id, section_id, clip_name, duration = items[0]
        assert clip_id == "abc123"
        assert clip_name == "test.mp4"
        assert duration > 0

    def test_skips_clips_with_missing_metadata(
        self, ctrl: CompositionController, qtbot
    ) -> None:
        ctrl._video_storage.get_metadata.side_effect = KeyError("abc123")
        with qtbot.waitSignal(ctrl.available_sections_changed, timeout=500) as blocker:
            ctrl.refresh_available_sections()
        items: list = blocker.args[0]
        assert items == []

    def test_get_section_info_returns_correct_data(
        self,
        ctrl: CompositionController,
        sample_annotation: ClipAnnotation,
        sample_metadata: ClipMetadata,
    ) -> None:
        section = sample_annotation.sections[0]
        info = ctrl.get_section_info("abc123", section.section_id)
        assert info is not None
        file_name, start, end = info
        assert file_name == sample_metadata.file_name
        assert start == section.start_seconds
        assert end == section.end_seconds

    def test_get_section_info_returns_none_for_missing_section(
        self, ctrl: CompositionController
    ) -> None:
        info = ctrl.get_section_info("abc123", "nonexistent-section-id")
        assert info is None


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    def test_start_export_calls_processor_submit(
        self,
        ctrl: CompositionController,
        processor: MagicMock,
        qtbot,
    ) -> None:
        ctrl.add_section("abc123", "s1")
        settings = ExportSettings(output_path="/tmp/out.mp4")
        ctrl.start_export(settings)
        processor.submit.assert_called_once()
        call_args = processor.submit.call_args
        assert call_args[0][1] is settings

    def test_start_export_does_nothing_if_empty(
        self, ctrl: CompositionController, processor: MagicMock
    ) -> None:
        settings = ExportSettings(output_path="/tmp/out.mp4")
        ctrl.start_export(settings)
        processor.submit.assert_not_called()

    def test_start_export_emits_job_status(
        self, ctrl: CompositionController, qtbot
    ) -> None:
        ctrl.add_section("abc123", "s1")
        settings = ExportSettings(output_path="/tmp/out.mp4")
        with qtbot.waitSignal(ctrl.job_status_changed, timeout=500) as blocker:
            ctrl.start_export(settings)
        status: JobStatus = blocker.args[0]
        assert status.job_id == "job-001"

    def test_cancel_export_calls_processor_cancel(
        self, ctrl: CompositionController, processor: MagicMock
    ) -> None:
        ctrl.add_section("abc123", "s1")
        ctrl.start_export(ExportSettings(output_path="/tmp/out.mp4"))
        ctrl.cancel_export()
        processor.cancel.assert_called_once_with("job-001")

    def test_cancel_export_noop_when_no_job(
        self, ctrl: CompositionController, processor: MagicMock
    ) -> None:
        ctrl.cancel_export()
        processor.cancel.assert_not_called()

    def test_get_default_export_path_is_nonempty(
        self, ctrl: CompositionController
    ) -> None:
        path = ctrl.get_default_export_path()
        assert path.endswith(".mp4")
        assert len(path) > 10
