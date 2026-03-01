from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

JobStatusValue = Literal["pending", "running", "complete", "failed"]


class JobStatus(BaseModel):
    job_id: str
    status: JobStatusValue = "pending"
    progress_percent: float = 0.0
    error_message: str | None = None
    result_path: str | None = None   # local path to output file when complete

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_done(self) -> bool:
        return self.status in ("complete", "failed")

    def as_running(self, progress_percent: float) -> JobStatus:
        return self.model_copy(update={"status": "running", "progress_percent": progress_percent})

    def as_complete(self, result_path: str) -> JobStatus:
        return self.model_copy(update={
            "status": "complete",
            "progress_percent": 100.0,
            "result_path": result_path,
        })

    def as_failed(self, error_message: str) -> JobStatus:
        return self.model_copy(update={"status": "failed", "error_message": error_message})
