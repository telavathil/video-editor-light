"""Smoke tests for annotation tab widgets.

These tests verify that widgets initialise without crashing, expose the
correct signals, and respond correctly to public method calls.  They do NOT
test rendering — just the public Python API.
"""

from __future__ import annotations

import pytest

from vacation_editor.gui.annotation.file_browser import FileBrowserWidget
from vacation_editor.gui.annotation.mark_bar import MarkBarWidget
from vacation_editor.gui.annotation.section_list import SectionListWidget
from vacation_editor.gui.annotation.transport_bar import TransportBarWidget
from vacation_editor.gui.annotation.video_player import VideoPlayerWidget
from vacation_editor.models.annotation import ClipAnnotation, Section

# ---------------------------------------------------------------------------
# VideoPlayerWidget
# ---------------------------------------------------------------------------

class TestVideoPlayerWidget:
    def test_creates_without_error(self, qtbot) -> None:
        w = VideoPlayerWidget()
        qtbot.addWidget(w)

    def test_initial_position_is_zero(self, qtbot) -> None:
        w = VideoPlayerWidget()
        qtbot.addWidget(w)
        assert w.get_position() == pytest.approx(0.0, abs=0.01)

    def test_mark_in_overlay_hides_when_none(self, qtbot) -> None:
        w = VideoPlayerWidget()
        qtbot.addWidget(w)
        w.set_mark_in_overlay(None)
        assert not w._mark_in_label.isVisible()

    def test_mark_in_overlay_shows_when_set(self, qtbot) -> None:
        w = VideoPlayerWidget()
        qtbot.addWidget(w)
        w.set_mark_in_overlay(65.0)
        assert not w._mark_in_label.isHidden()
        assert "01:05" in w._mark_in_label.text()


# ---------------------------------------------------------------------------
# TransportBarWidget
# ---------------------------------------------------------------------------

class TestTransportBarWidget:
    def test_creates_without_error(self, qtbot) -> None:
        w = TransportBarWidget()
        qtbot.addWidget(w)

    def test_set_duration_updates_time_out_label(self, qtbot) -> None:
        w = TransportBarWidget()
        qtbot.addWidget(w)
        w.set_duration(125.0)
        assert w._time_out.text() == "2:05"

    def test_set_playback_state_playing_shows_pause(self, qtbot) -> None:
        w = TransportBarWidget()
        qtbot.addWidget(w)
        w.set_playback_state("playing")
        assert "Pause" in w._btn_play.text()

    def test_set_playback_state_paused_shows_play(self, qtbot) -> None:
        w = TransportBarWidget()
        qtbot.addWidget(w)
        w.set_playback_state("paused")
        assert "Play" in w._btn_play.text()

    def test_play_pause_button_emits_signal(self, qtbot) -> None:
        w = TransportBarWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.play_pause_toggled, timeout=500):
            w._btn_play.click()

    def test_speed_chip_emits_speed_changed(self, qtbot) -> None:
        w = TransportBarWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.speed_changed, timeout=500) as blocker:
            # Click the 0.5× chip
            w._chips[1].click()
        assert blocker.args[0] == pytest.approx(0.5)

    def test_only_one_speed_chip_active_at_a_time(self, qtbot) -> None:
        w = TransportBarWidget()
        qtbot.addWidget(w)
        w._chips[2].click()  # 1×
        active = [c for c in w._chips if c.isChecked()]
        assert len(active) == 1


# ---------------------------------------------------------------------------
# MarkBarWidget
# ---------------------------------------------------------------------------

class TestMarkBarWidget:
    def test_creates_without_error(self, qtbot) -> None:
        w = MarkBarWidget()
        qtbot.addWidget(w)

    def test_mark_out_disabled_initially(self, qtbot) -> None:
        w = MarkBarWidget()
        qtbot.addWidget(w)
        assert not w._mark_out_btn.isEnabled()

    def test_set_mark_in_enables_mark_out(self, qtbot) -> None:
        w = MarkBarWidget()
        qtbot.addWidget(w)
        w.set_mark_in(10.0)
        assert w._mark_out_btn.isEnabled()

    def test_set_mark_in_none_disables_mark_out(self, qtbot) -> None:
        w = MarkBarWidget()
        qtbot.addWidget(w)
        w.set_mark_in(10.0)
        w.set_mark_in(None)
        assert not w._mark_out_btn.isEnabled()

    def test_mark_in_click_emits_signal(self, qtbot) -> None:
        w = MarkBarWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.mark_in_clicked, timeout=500):
            w._mark_in_btn.click()

    def test_indicator_shows_pending_time(self, qtbot) -> None:
        w = MarkBarWidget()
        qtbot.addWidget(w)
        w.set_mark_in(65.0)  # 1:05
        assert "01:05" in w._indicator.text()


# ---------------------------------------------------------------------------
# SectionListWidget
# ---------------------------------------------------------------------------

class TestSectionListWidget:
    def test_creates_without_error(self, qtbot) -> None:
        w = SectionListWidget()
        qtbot.addWidget(w)

    def test_empty_list_shows_zero_badge(self, qtbot) -> None:
        w = SectionListWidget()
        qtbot.addWidget(w)
        assert w._badge.text() == "0"

    def test_set_sections_updates_badge(self, qtbot, sample_section: Section) -> None:
        w = SectionListWidget()
        qtbot.addWidget(w)
        annotation = ClipAnnotation(clip_id="abc").with_section_added(sample_section)
        w.set_sections(annotation.sections)
        assert w._badge.text() == "1"

    def test_total_duration_updates(self, qtbot, sample_section: Section) -> None:
        w = SectionListWidget()
        qtbot.addWidget(w)
        # sample_section is 1.0 → 3.0 = 2s
        annotation = ClipAnnotation(clip_id="abc").with_section_added(sample_section)
        w.set_sections(annotation.sections)
        assert w._total_val.text() == "0:02"

    def test_section_deleted_signal(self, qtbot, sample_section: Section) -> None:
        w = SectionListWidget()
        qtbot.addWidget(w)
        annotation = ClipAnnotation(clip_id="abc").with_section_added(sample_section)
        w.set_sections(annotation.sections)

        with qtbot.waitSignal(w.section_deleted, timeout=500) as blocker:
            w.section_deleted.emit(sample_section.section_id)

        assert blocker.args[0] == sample_section.section_id


# ---------------------------------------------------------------------------
# FileBrowserWidget
# ---------------------------------------------------------------------------

class TestFileBrowserWidget:
    def test_creates_without_error(self, qtbot) -> None:
        w = FileBrowserWidget()
        qtbot.addWidget(w)

    def test_empty_list_has_no_rows(self, qtbot) -> None:
        w = FileBrowserWidget()
        qtbot.addWidget(w)
        # Only the stretch item should remain
        assert w._list_layout.count() == 1

    def test_set_clips_populates_rows(
        self, qtbot, sample_metadata
    ) -> None:
        w = FileBrowserWidget()
        qtbot.addWidget(w)
        w.set_clips([("clip1", sample_metadata)], annotated_ids=set())
        # 1 row + 1 stretch
        assert w._list_layout.count() == 2

    def test_annotated_clip_row_count(
        self, qtbot, sample_metadata
    ) -> None:
        w = FileBrowserWidget()
        qtbot.addWidget(w)
        w.set_clips(
            [("clip1", sample_metadata), ("clip2", sample_metadata)],
            annotated_ids={"clip1"},
        )
        assert w._list_layout.count() == 3  # 2 rows + stretch

    def test_delete_button_emits_clip_delete_requested(
        self, qtbot, sample_metadata
    ) -> None:
        w = FileBrowserWidget()
        qtbot.addWidget(w)
        w.set_clips([("clip1", sample_metadata)], annotated_ids=set())

        row = w._list_layout.itemAt(0).widget()
        with qtbot.waitSignal(w.clip_delete_requested, timeout=500) as blocker:
            row._delete_btn.click()

        assert blocker.args[0] == "clip1"

    def test_delete_button_does_not_emit_clip_selected(
        self, qtbot, sample_metadata
    ) -> None:
        w = FileBrowserWidget()
        qtbot.addWidget(w)
        w.set_clips([("clip1", sample_metadata)], annotated_ids=set())

        row = w._list_layout.itemAt(0).widget()
        received: list[str] = []
        w.clip_selected.connect(received.append)
        row._delete_btn.click()

        assert received == []
