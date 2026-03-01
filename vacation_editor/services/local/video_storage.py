from __future__ import annotations

import shutil
from pathlib import Path

from vacation_editor.config import AppConfig
from vacation_editor.models.clip import ClipMetadata
from vacation_editor.services import ffprobe as ffprobe_service

_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi"}


class LocalVideoStorage:
    """Stores video clips in AppConfig.project_dir/clips/.

    Layout:
        clips/{clip_id}{original_extension}   — the video file
        clips/{clip_id}.meta.json             — ClipMetadata (Pydantic JSON)
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._clips_dir = config.project_dir / "clips"

    def _video_path(self, clip_id: str) -> Path:
        """Find the video file for a clip_id (any supported extension)."""
        for ext in _VIDEO_EXTENSIONS:
            candidate = self._clips_dir / f"{clip_id}{ext}"
            if candidate.exists():
                return candidate
        raise KeyError(f"No video file found for clip_id: {clip_id!r}")

    def _meta_path(self, clip_id: str) -> Path:
        return self._clips_dir / f"{clip_id}.meta.json"

    def get_local_path(self, clip_id: str) -> Path:
        return self._video_path(clip_id)

    def upload(self, local_path: Path, clip_id: str) -> None:
        """Copy a video file into the clips directory and probe its metadata."""
        if not local_path.exists():
            raise FileNotFoundError(f"Source clip not found: {local_path}")

        self._clips_dir.mkdir(parents=True, exist_ok=True)

        suffix = local_path.suffix.lower()
        if suffix not in _VIDEO_EXTENSIONS:
            raise ValueError(
                f"Unsupported video format: {suffix!r}. "
                f"Supported: {', '.join(sorted(_VIDEO_EXTENSIONS))}"
            )

        dest = self._clips_dir / f"{clip_id}{suffix}"
        if dest != local_path:
            shutil.copy2(local_path, dest)

        # Probe metadata and persist alongside the video
        ffprobe_path = ffprobe_service.detect_ffprobe(self._config)
        metadata = ffprobe_service.probe_clip(ffprobe_path, dest)
        # Store with the canonical clip_id (the probe uses path-based id by default)
        metadata_with_id = metadata.model_copy(update={"clip_id": clip_id})
        self._meta_path(clip_id).write_text(
            metadata_with_id.model_dump_json(indent=2), encoding="utf-8"
        )

    def list_clips(self) -> list[str]:
        if not self._clips_dir.exists():
            return []
        return [
            p.stem
            for p in self._clips_dir.iterdir()
            if p.suffix.lower() in _VIDEO_EXTENSIONS
        ]

    def get_metadata(self, clip_id: str) -> ClipMetadata:
        meta_path = self._meta_path(clip_id)
        if not meta_path.exists():
            raise KeyError(f"No metadata found for clip_id: {clip_id!r}")
        return ClipMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))
