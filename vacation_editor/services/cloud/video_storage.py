from __future__ import annotations

# CLOUD STUB — Not yet implemented.
#
# Future implementation notes:
#   - Use boto3 (or an S3-compatible client for Cloudflare R2)
#   - get_local_path(): download clip to a local cache dir, return cached path
#   - upload(): upload to S3/R2 bucket, store ClipMetadata in PostgreSQL
#   - list_clips(): query database for clip IDs belonging to this project
#   - get_metadata(): query database by clip_id
#
# Recommended: Cloudflare R2 (no egress fees, S3-compatible API)
# Install when ready: pip install boto3
from pathlib import Path

from vacation_editor.models.clip import ClipMetadata


class S3VideoStorage:
    """Future cloud implementation of VideoStorage using S3 / Cloudflare R2."""

    def get_local_path(self, clip_id: str) -> Path:
        raise NotImplementedError(
            "S3VideoStorage not yet implemented. Set cloud_mode=False to use local storage."
        )

    def upload(self, local_path: Path, clip_id: str) -> None:
        raise NotImplementedError(
            "S3VideoStorage not yet implemented. Set cloud_mode=False to use local storage."
        )

    def list_clips(self) -> list[str]:
        raise NotImplementedError(
            "S3VideoStorage not yet implemented. Set cloud_mode=False to use local storage."
        )

    def get_metadata(self, clip_id: str) -> ClipMetadata:
        raise NotImplementedError(
            "S3VideoStorage not yet implemented. Set cloud_mode=False to use local storage."
        )

    def heal(self, clip_id: str) -> None:
        raise NotImplementedError(
            "S3VideoStorage not yet implemented. Set cloud_mode=False to use local storage."
        )

    def delete(self, clip_id: str) -> None:
        raise NotImplementedError(
            "S3VideoStorage not yet implemented. Set cloud_mode=False to use local storage."
        )
