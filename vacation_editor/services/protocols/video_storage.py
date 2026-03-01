from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from vacation_editor.models.clip import ClipMetadata


@runtime_checkable
class VideoStorage(Protocol):
    def get_local_path(self, clip_id: str) -> Path:
        """Return the local filesystem path for a clip.

        In local mode: looks up the clip in the project clips directory.
        In cloud mode (future): downloads to a local cache first, then returns cache path.

        Raises KeyError if clip_id is not found.
        """
        ...

    def upload(self, local_path: Path, clip_id: str) -> None:
        """Import a clip into storage.

        In local mode: copies the file to the project clips directory and probes metadata.
        In cloud mode (future): uploads to S3/R2, stores metadata in database.

        Raises FileNotFoundError if local_path does not exist.
        """
        ...

    def list_clips(self) -> list[str]:
        """Return all known clip IDs in storage."""
        ...

    def get_metadata(self, clip_id: str) -> ClipMetadata:
        """Return metadata for a clip.

        Raises KeyError if clip_id is not found.
        """
        ...
