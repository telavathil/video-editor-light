from __future__ import annotations

# CLOUD STUB — Not yet implemented.
#
# Future implementation notes:
#   - submit(): POST /compositions to a FastAPI backend, enqueue to SQS or Redis queue
#   - poll(): GET /compositions/{job_id}/status
#   - get_result(): GET /compositions/{job_id}/result — downloads output from S3 to local cache
#   - cancel(): DELETE /compositions/{job_id}
#
# Worker process runs on cloud GPU (Modal, AWS Lambda + EFS, or EC2 spot instance).
# Recommended: Modal.com for serverless GPU (pay-per-second, T4 ~$0.50/hr)
#
# FastAPI endpoints to build:
#   POST   /compositions           → { job_id }
#   GET    /compositions/{id}/status → JobStatus JSON
#   GET    /compositions/{id}/result → 302 redirect to S3 presigned URL
#   DELETE /compositions/{id}      → 204
#
# Install when ready: pip install httpx
from pathlib import Path

from vacation_editor.models.composition import Composition
from vacation_editor.models.job import JobStatus


class CloudCompositionProcessor:
    """Future cloud implementation of CompositionProcessor using a REST API + job queue."""

    _MSG = "CloudCompositionProcessor not implemented. Set cloud_mode=False for local processing."

    def submit(self, composition: Composition) -> str:
        raise NotImplementedError(self._MSG)

    def poll(self, job_id: str) -> JobStatus:
        raise NotImplementedError(self._MSG)

    def get_result(self, job_id: str) -> Path:
        raise NotImplementedError(self._MSG)

    def cancel(self, job_id: str) -> None:
        raise NotImplementedError(self._MSG)
