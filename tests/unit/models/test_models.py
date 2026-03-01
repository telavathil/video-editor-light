from __future__ import annotations

import pytest

from vacation_editor.models.annotation import ClipAnnotation, Section
from vacation_editor.models.clip import ClipMetadata
from vacation_editor.models.composition import Composition, CompositionSection
from vacation_editor.models.job import JobStatus


class TestSection:
    def test_new_creates_with_uuid(self) -> None:
        s = Section.new(1.0, 5.0, "hello")
        assert s.start_seconds == 1.0
        assert s.end_seconds == 5.0
        assert s.label == "hello"
        assert len(s.section_id) > 0

    def test_duration_property(self) -> None:
        s = Section.new(2.0, 7.5)
        assert s.duration_seconds == pytest.approx(5.5)

    def test_end_before_start_raises(self) -> None:
        with pytest.raises(ValueError, match="end_seconds"):
            Section.new(5.0, 2.0)

    def test_end_equal_start_raises(self) -> None:
        with pytest.raises(ValueError):
            Section.new(3.0, 3.0)

    def test_with_label_is_immutable(self) -> None:
        s = Section.new(1.0, 2.0)
        s2 = s.with_label("new label")
        assert s.label == ""
        assert s2.label == "new label"
        assert s.section_id == s2.section_id

    def test_roundtrip_json(self) -> None:
        s = Section.new(1.0, 5.0, "trip")
        restored = Section.model_validate_json(s.model_dump_json())
        assert restored == s


class TestClipAnnotation:
    def test_starts_empty(self) -> None:
        a = ClipAnnotation(clip_id="abc")
        assert a.sections == []

    def test_with_section_added(self) -> None:
        a = ClipAnnotation(clip_id="abc")
        s = Section.new(1.0, 2.0)
        a2 = a.with_section_added(s)
        assert a.sections == []          # original unchanged
        assert len(a2.sections) == 1

    def test_with_section_removed(self) -> None:
        s = Section.new(1.0, 2.0)
        a = ClipAnnotation(clip_id="abc").with_section_added(s)
        a2 = a.with_section_removed(s.section_id)
        assert len(a2.sections) == 0

    def test_with_section_updated(self) -> None:
        s = Section.new(1.0, 2.0)
        a = ClipAnnotation(clip_id="abc").with_section_added(s)
        updated = s.with_label("updated")
        a2 = a.with_section_updated(updated)
        assert a2.sections[0].label == "updated"
        assert a.sections[0].label == ""  # original unchanged

    def test_roundtrip_json(self) -> None:
        s = Section.new(1.0, 5.0)
        a = ClipAnnotation(clip_id="abc").with_section_added(s)
        restored = ClipAnnotation.model_validate_json(a.model_dump_json())
        assert restored.clip_id == "abc"
        assert len(restored.sections) == 1


class TestComposition:
    def test_new(self) -> None:
        c = Composition.new("My Video")
        assert c.name == "My Video"
        assert c.sections == []
        assert len(c.composition_id) > 0

    def test_with_section_appended_assigns_order(self) -> None:
        c = Composition.new("test")
        s1 = CompositionSection(clip_id="a", section_id="s1", order=0)
        s2 = CompositionSection(clip_id="b", section_id="s2", order=0)
        c2 = c.with_section_appended(s1).with_section_appended(s2)
        assert c2.sections[0].order == 0
        assert c2.sections[1].order == 1

    def test_with_section_removed_reorders(self) -> None:
        c = Composition.new("test")
        s1 = CompositionSection(clip_id="a", section_id="s1", order=0)
        s2 = CompositionSection(clip_id="b", section_id="s2", order=0)
        s3 = CompositionSection(clip_id="c", section_id="s3", order=0)
        c2 = c.with_section_appended(s1).with_section_appended(s2).with_section_appended(s3)
        c3 = c2.with_section_removed(1)  # remove middle
        assert len(c3.sections) == 2
        assert c3.sections[0].order == 0
        assert c3.sections[1].order == 1
        assert c3.sections[1].section_id == "s3"

    def test_immutability(self) -> None:
        c = Composition.new("test")
        s = CompositionSection(clip_id="a", section_id="s1", order=0)
        c2 = c.with_section_appended(s)
        assert len(c.sections) == 0
        assert len(c2.sections) == 1

    def test_roundtrip_json(self) -> None:
        c = Composition.new("Holiday 2024")
        restored = Composition.model_validate_json(c.model_dump_json())
        assert restored.name == "Holiday 2024"


class TestJobStatus:
    def test_initial_state(self) -> None:
        j = JobStatus(job_id="j1")
        assert j.status == "pending"
        assert not j.is_complete
        assert not j.is_failed
        assert not j.is_done

    def test_as_running(self) -> None:
        j = JobStatus(job_id="j1").as_running(42.0)
        assert j.status == "running"
        assert j.progress_percent == 42.0

    def test_as_complete(self) -> None:
        j = JobStatus(job_id="j1").as_complete("/tmp/out.mp4")
        assert j.is_complete
        assert j.is_done
        assert j.result_path == "/tmp/out.mp4"
        assert j.progress_percent == 100.0

    def test_as_failed(self) -> None:
        j = JobStatus(job_id="j1").as_failed("something went wrong")
        assert j.is_failed
        assert j.is_done
        assert j.error_message == "something went wrong"

    def test_immutability(self) -> None:
        j = JobStatus(job_id="j1")
        j2 = j.as_running(50.0)
        assert j.status == "pending"
        assert j2.status == "running"


class TestClipMetadata:
    def test_make_clip_id_is_stable(self, tmp_path) -> None:
        p = tmp_path / "clip.mp4"
        p.touch()
        id1 = ClipMetadata.make_clip_id(p)
        id2 = ClipMetadata.make_clip_id(p)
        assert id1 == id2
        assert len(id1) == 16

    def test_roundtrip_json(self) -> None:
        m = ClipMetadata(
            clip_id="abc123",
            file_name="test.mp4",
            duration_seconds=10.0,
            resolution=(3840, 2160),
            codec="h265",
            fps=24.0,
            file_size_bytes=500_000_000,
            source_path="/Volumes/DJI/test.mp4",
        )
        restored = ClipMetadata.model_validate_json(m.model_dump_json())
        assert restored == m
