from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from vacation_editor.models.composition import Composition, ExportSettings
    from vacation_editor.models.job import JobStatus


@runtime_checkable
class CompositionProcessor(Protocol):
    def submit(self, composition: Composition, export_settings: ExportSettings) -> str:
        """Submit a composition for processing.

        Returns a job_id that can be used with poll(), get_result(), and cancel().

        In local mode: starts a background thread running the FFmpeg pipeline.
        In cloud mode (future): posts to a job queue (SQS/Redis), returns the queue message ID.
        """
        ...

    def poll(self, job_id: str) -> JobStatus:
        """Check the current status of a submitted job.

        In local mode: reads from an in-memory dict (thread-safe).
        In cloud mode (future): calls GET /compositions/{job_id}/status.

        Raises KeyError if job_id is not found.
        """
        ...

    def get_result(self, job_id: str) -> Path:
        """Return the local path to the completed export.

        Raises RuntimeError if the job is not yet complete.
        Raises KeyError if job_id is not found.
        """
        ...

    def cancel(self, job_id: str) -> None:
        """Cancel a running job.

        In local mode: sets a cancel event; the background thread terminates FFmpeg.
        In cloud mode (future): calls DELETE /compositions/{job_id}.

        No-op if the job is already done.
        """
        ...
