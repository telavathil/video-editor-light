from __future__ import annotations

import pytest

from vacation_editor.services.local.video_storage import LocalVideoStorage


@pytest.fixture
def storage(tmp_config) -> LocalVideoStorage:
    return LocalVideoStorage(tmp_config)


class TestLocalVideoStorage:
    def test_get_local_path_raises_for_unknown_clip(self, storage: LocalVideoStorage) -> None:
        with pytest.raises(KeyError, match="no_such_clip"):
            storage.get_local_path("no_such_clip")

    def test_list_clips_empty_initially(self, storage: LocalVideoStorage) -> None:
        assert storage.list_clips() == []

    def test_get_metadata_raises_for_unknown_clip(self, storage: LocalVideoStorage) -> None:
        with pytest.raises(KeyError, match="unknown"):
            storage.get_metadata("unknown")

    def test_upload_requires_ffmpeg(self, storage: LocalVideoStorage, test_clip_path) -> None:
        """Upload a real clip and verify it is stored with metadata."""
        clip_id = "test_abc123"
        storage.upload(test_clip_path, clip_id)

        assert clip_id in storage.list_clips()
        path = storage.get_local_path(clip_id)
        assert path.exists()

        meta = storage.get_metadata(clip_id)
        assert meta.clip_id == clip_id
        assert meta.duration_seconds == pytest.approx(3.0, abs=0.5)
        assert meta.fps == pytest.approx(24.0, abs=1.0)

    def test_upload_raises_for_missing_file(self, storage: LocalVideoStorage, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            storage.upload(tmp_path / "nonexistent.mp4", "clip01")

    def test_upload_raises_for_unsupported_extension(
        self, storage: LocalVideoStorage, tmp_path
    ) -> None:
        bad_file = tmp_path / "clip.xyz"
        bad_file.write_bytes(b"not a video")
        with pytest.raises(ValueError, match="Unsupported"):
            storage.upload(bad_file, "clip01")
