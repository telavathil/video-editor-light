from __future__ import annotations

import pytest

from vacation_editor.models.annotation import ClipAnnotation, Section
from vacation_editor.services.local.annotation_store import LocalAnnotationStore


@pytest.fixture
def store(tmp_config) -> LocalAnnotationStore:
    return LocalAnnotationStore(tmp_config)


class TestLocalAnnotationStore:
    def test_save_and_load_roundtrip(self, store: LocalAnnotationStore) -> None:
        s = Section.new(1.0, 3.0, "beach")
        a = ClipAnnotation(clip_id="clip01").with_section_added(s)
        store.save(a)
        loaded = store.load("clip01")
        assert loaded.clip_id == "clip01"
        assert len(loaded.sections) == 1
        assert loaded.sections[0].label == "beach"

    def test_load_raises_for_missing_clip(self, store: LocalAnnotationStore) -> None:
        with pytest.raises(KeyError, match="no_such_clip"):
            store.load("no_such_clip")

    def test_list_empty_when_no_annotations(self, store: LocalAnnotationStore) -> None:
        assert store.list_annotated_clips() == []

    def test_list_returns_saved_clip_ids(self, store: LocalAnnotationStore) -> None:
        store.save(ClipAnnotation(clip_id="clip01"))
        store.save(ClipAnnotation(clip_id="clip02"))
        clips = sorted(store.list_annotated_clips())
        assert clips == ["clip01", "clip02"]

    def test_delete_removes_annotation(self, store: LocalAnnotationStore) -> None:
        store.save(ClipAnnotation(clip_id="clip01"))
        store.delete("clip01")
        assert "clip01" not in store.list_annotated_clips()

    def test_delete_raises_for_missing(self, store: LocalAnnotationStore) -> None:
        with pytest.raises(KeyError):
            store.delete("nonexistent")

    def test_save_overwrites_existing(self, store: LocalAnnotationStore) -> None:
        a = ClipAnnotation(clip_id="clip01")
        store.save(a)
        s = Section.new(0.0, 1.0)
        updated = a.with_section_added(s)
        store.save(updated)
        loaded = store.load("clip01")
        assert len(loaded.sections) == 1

    def test_creates_dir_if_not_exists(self, tmp_config) -> None:
        assert not tmp_config.annotations_dir.exists()
        store = LocalAnnotationStore(tmp_config)
        store.save(ClipAnnotation(clip_id="x"))
        assert tmp_config.annotations_dir.exists()

    def test_list_when_dir_does_not_exist(self, tmp_config) -> None:
        store = LocalAnnotationStore(tmp_config)
        assert store.list_annotated_clips() == []
