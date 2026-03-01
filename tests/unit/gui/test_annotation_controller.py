from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vacation_editor.gui.annotation.controller import AnnotationController
from vacation_editor.models.annotation import ClipAnnotation, Section
from vacation_editor.models.clip import ClipMetadata

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def storage(sample_metadata: ClipMetadata) -> MagicMock:
    mock = MagicMock()
    mock.list_clips.return_value = ["clip1"]
    mock.get_metadata.return_value = sample_metadata
    mock.get_local_path.return_value = "/tmp/clip1.mp4"
    return mock


@pytest.fixture
def store() -> MagicMock:
    mock = MagicMock()
    mock.load.side_effect = KeyError("clip1")   # no annotation yet by default
    mock.list_annotated_clips.return_value = []
    return mock


@pytest.fixture
def ctrl(qtbot, storage, store) -> AnnotationController:
    """Controller under test (qtbot ensures a QApplication exists)."""
    return AnnotationController(storage, store)


# ---------------------------------------------------------------------------
# Clip loading
# ---------------------------------------------------------------------------

class TestLoadClip:
    def test_load_creates_empty_annotation_when_store_raises(
        self, ctrl: AnnotationController, store: MagicMock
    ) -> None:
        store.load.side_effect = KeyError("clip1")
        ctrl.load_clip("clip1")
        assert ctrl._annotation is not None
        assert ctrl._annotation.clip_id == "clip1"
        assert ctrl._annotation.sections == []

    def test_load_restores_existing_annotation(
        self, ctrl: AnnotationController, store: MagicMock, sample_section: Section
    ) -> None:
        existing = ClipAnnotation(clip_id="clip1").with_section_added(sample_section)
        store.load.return_value = existing
        store.load.side_effect = None

        ctrl.load_clip("clip1")

        assert ctrl._annotation is not None
        assert len(ctrl._annotation.sections) == 1

    def test_load_emits_clip_loaded_signal(
        self, qtbot, ctrl: AnnotationController
    ) -> None:
        with qtbot.waitSignal(ctrl.clip_loaded, timeout=500) as blocker:
            ctrl.load_clip("clip1")
        clip_id, duration = blocker.args
        assert clip_id == "clip1"
        assert duration > 0

    def test_load_clears_mark_in(self, ctrl: AnnotationController) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(5.0)
        ctrl.load_clip("clip1")  # reload (same id, forced by clearing _current_clip_id)
        # Trigger by clearing cache
        ctrl._current_clip_id = None
        ctrl.load_clip("clip1")
        assert ctrl._mark_in is None

    def test_load_clears_undo_redo(
        self, ctrl: AnnotationController, sample_section: Section
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(2.0)
        assert ctrl._undo_stack  # there should be something

        ctrl._current_clip_id = None
        ctrl.load_clip("clip1")
        assert ctrl._undo_stack == []
        assert ctrl._redo_stack == []


# ---------------------------------------------------------------------------
# Mark In / Mark Out
# ---------------------------------------------------------------------------

class TestMarkInOut:
    def test_mark_in_sets_pending_position(self, ctrl: AnnotationController) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(3.5)
        assert ctrl._mark_in == pytest.approx(3.5)

    def test_mark_in_emits_signal(self, qtbot, ctrl: AnnotationController) -> None:
        ctrl.load_clip("clip1")
        with qtbot.waitSignal(ctrl.mark_in_updated, timeout=500) as blocker:
            ctrl.mark_in(3.5)
        assert blocker.args[0] == pytest.approx(3.5)

    def test_mark_out_creates_section(self, ctrl: AnnotationController) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(3.0)
        assert ctrl._annotation is not None
        assert len(ctrl._annotation.sections) == 1
        s = ctrl._annotation.sections[0]
        assert s.start_seconds == pytest.approx(1.0)
        assert s.end_seconds == pytest.approx(3.0)

    def test_mark_out_clears_pending_mark_in(self, ctrl: AnnotationController) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(3.0)
        assert ctrl._mark_in is None

    def test_mark_out_does_nothing_without_mark_in(
        self, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_out(3.0)
        assert ctrl._annotation is not None
        assert ctrl._annotation.sections == []

    def test_mark_out_does_nothing_when_end_before_start(
        self, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(5.0)
        ctrl.mark_out(3.0)   # end < start — invalid
        assert ctrl._annotation is not None
        assert ctrl._annotation.sections == []
        assert ctrl._mark_in == pytest.approx(5.0)  # mark-in preserved

    def test_mark_out_equal_to_mark_in_does_nothing(
        self, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(2.0)
        ctrl.mark_out(2.0)
        assert ctrl._annotation is not None
        assert ctrl._annotation.sections == []

    def test_mark_out_emits_sections_updated(
        self, qtbot, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        with qtbot.waitSignal(ctrl.sections_updated, timeout=500) as blocker:
            ctrl.mark_out(2.0)
        assert len(blocker.args[0]) == 1


# ---------------------------------------------------------------------------
# Section operations
# ---------------------------------------------------------------------------

class TestSectionOperations:
    def test_delete_section_removes_it(
        self, ctrl: AnnotationController, sample_section: Section
    ) -> None:
        store_mock = ctrl._store
        store_mock.load.return_value = ClipAnnotation(clip_id="clip1").with_section_added(
            sample_section
        )
        store_mock.load.side_effect = None
        ctrl.load_clip("clip1")

        ctrl.delete_section(sample_section.section_id)

        assert ctrl._annotation is not None
        assert ctrl._annotation.sections == []

    def test_delete_nonexistent_section_is_a_noop(
        self, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(2.0)
        ctrl.delete_section("no-such-id")
        assert ctrl._annotation is not None
        assert len(ctrl._annotation.sections) == 1

    def test_trim_section_updates_times(
        self, ctrl: AnnotationController, sample_section: Section
    ) -> None:
        store_mock = ctrl._store
        store_mock.load.return_value = ClipAnnotation(clip_id="clip1").with_section_added(
            sample_section
        )
        store_mock.load.side_effect = None
        ctrl.load_clip("clip1")

        ctrl.trim_section(sample_section.section_id, 2.0, 4.0)

        assert ctrl._annotation is not None
        trimmed = ctrl._annotation.sections[0]
        assert trimmed.start_seconds == pytest.approx(2.0)
        assert trimmed.end_seconds == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Undo / Redo
# ---------------------------------------------------------------------------

class TestUndoRedo:
    def _setup_with_one_section(self, ctrl: AnnotationController) -> Section:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(3.0)
        assert ctrl._annotation is not None
        return ctrl._annotation.sections[0]

    def test_undo_removes_last_added_section(self, ctrl: AnnotationController) -> None:
        self._setup_with_one_section(ctrl)
        ctrl.undo()
        assert ctrl._annotation is not None
        assert ctrl._annotation.sections == []

    def test_redo_restores_section_after_undo(self, ctrl: AnnotationController) -> None:
        self._setup_with_one_section(ctrl)
        ctrl.undo()
        ctrl.redo()
        assert ctrl._annotation is not None
        assert len(ctrl._annotation.sections) == 1

    def test_undo_empty_stack_is_noop(self, ctrl: AnnotationController) -> None:
        ctrl.load_clip("clip1")
        ctrl.undo()  # should not raise
        assert ctrl._annotation is not None
        assert ctrl._annotation.sections == []

    def test_redo_after_new_action_clears_redo_stack(
        self, ctrl: AnnotationController
    ) -> None:
        self._setup_with_one_section(ctrl)
        ctrl.undo()
        # New action invalidates redo
        ctrl.mark_in(5.0)
        ctrl.mark_out(7.0)
        assert ctrl._redo_stack == []

    def test_multiple_undo_steps(self, ctrl: AnnotationController) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(2.0)
        ctrl.mark_in(3.0)
        ctrl.mark_out(4.0)
        assert ctrl._annotation is not None
        assert len(ctrl._annotation.sections) == 2

        ctrl.undo()
        assert len(ctrl._annotation.sections) == 1
        ctrl.undo()
        assert len(ctrl._annotation.sections) == 0


# ---------------------------------------------------------------------------
# Auto-save
# ---------------------------------------------------------------------------

class TestAutoSave:
    def test_save_now_calls_store_save(
        self, ctrl: AnnotationController, store: MagicMock
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(2.0)
        ctrl.save_now()
        store.save.assert_called_once()

    def test_save_now_passes_annotation_to_store(
        self, ctrl: AnnotationController, store: MagicMock
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(2.0)
        ctrl.save_now()
        saved = store.save.call_args[0][0]
        assert isinstance(saved, ClipAnnotation)
        assert len(saved.sections) == 1

    def test_save_emits_saved_status(
        self, qtbot, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(2.0)
        with qtbot.waitSignal(ctrl.save_status_changed, timeout=500) as blocker:
            ctrl.save_now()
        assert blocker.args[0] == "saved"


# ---------------------------------------------------------------------------
# Delete clip
# ---------------------------------------------------------------------------

class TestDeleteClip:
    def test_delete_calls_storage_delete(
        self, ctrl: AnnotationController, storage: MagicMock
    ) -> None:
        ctrl.delete_clip("clip1")
        storage.delete.assert_called_once_with("clip1")

    def test_delete_refreshes_clip_list(
        self, ctrl: AnnotationController, storage: MagicMock
    ) -> None:
        ctrl.delete_clip("clip1")
        storage.list_clips.assert_called()

    def test_delete_current_clip_clears_state(
        self, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.delete_clip("clip1")
        assert ctrl._current_clip_id is None
        assert ctrl._annotation is None
        assert ctrl._mark_in is None
        assert ctrl._undo_stack == []

    def test_delete_noncurrent_clip_preserves_state(
        self, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(2.0)
        ctrl.delete_clip("other-clip")
        assert ctrl._current_clip_id == "clip1"
        assert ctrl._mark_in == pytest.approx(2.0)

    def test_delete_emits_sections_cleared_when_current(
        self, qtbot, ctrl: AnnotationController
    ) -> None:
        ctrl.load_clip("clip1")
        ctrl.mark_in(1.0)
        ctrl.mark_out(3.0)
        with qtbot.waitSignal(ctrl.sections_updated, timeout=500) as blocker:
            ctrl.delete_clip("clip1")
        assert blocker.args[0] == []

    def test_delete_storage_error_does_not_refresh(
        self, ctrl: AnnotationController, storage: MagicMock
    ) -> None:
        storage.delete.side_effect = RuntimeError("disk error")
        storage.list_clips.reset_mock()
        ctrl.delete_clip("clip1")
        storage.list_clips.assert_not_called()
