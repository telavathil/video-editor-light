from __future__ import annotations

from pathlib import Path

from vacation_editor.config import AppConfig
from vacation_editor.models.annotation import ClipAnnotation


class LocalAnnotationStore:
    """Stores annotations as JSON files in AppConfig.annotations_dir.

    File naming: {clip_id}.json
    Serialization: Pydantic model_dump_json / model_validate_json
    """

    def __init__(self, config: AppConfig) -> None:
        self._dir = config.annotations_dir

    def _path(self, clip_id: str) -> Path:
        return self._dir / f"{clip_id}.json"

    def save(self, annotation: ClipAnnotation) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(annotation.clip_id).write_text(
            annotation.model_dump_json(indent=2), encoding="utf-8"
        )

    def load(self, clip_id: str) -> ClipAnnotation:
        path = self._path(clip_id)
        if not path.exists():
            raise KeyError(f"No annotation found for clip_id: {clip_id!r}")
        return ClipAnnotation.model_validate_json(path.read_text(encoding="utf-8"))

    def list_annotated_clips(self) -> list[str]:
        if not self._dir.exists():
            return []
        return [p.stem for p in self._dir.glob("*.json")]

    def delete(self, clip_id: str) -> None:
        path = self._path(clip_id)
        if not path.exists():
            raise KeyError(f"No annotation found for clip_id: {clip_id!r}")
        path.unlink()
