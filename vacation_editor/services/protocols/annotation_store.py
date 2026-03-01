from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from vacation_editor.models.annotation import ClipAnnotation


@runtime_checkable
class AnnotationStore(Protocol):
    def save(self, annotation: ClipAnnotation) -> None:
        """Persist an annotation.

        In local mode: writes {clip_id}.json to the annotations directory.
        In cloud mode (future): upserts into PostgreSQL as JSONB.
        """
        ...

    def load(self, clip_id: str) -> ClipAnnotation:
        """Load an annotation by clip ID.

        Raises KeyError if no annotation exists for clip_id.
        """
        ...

    def list_annotated_clips(self) -> list[str]:
        """Return clip IDs that have saved annotations."""
        ...

    def delete(self, clip_id: str) -> None:
        """Remove an annotation.

        Raises KeyError if no annotation exists for clip_id.
        """
        ...
