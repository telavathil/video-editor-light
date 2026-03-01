from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel


class ClipMetadata(BaseModel):
    clip_id: str
    file_name: str
    duration_seconds: float
    resolution: tuple[int, int]   # (width, height)
    codec: str
    fps: float
    file_size_bytes: int
    source_path: str              # original import path — informational only, never use for I/O

    @staticmethod
    def make_clip_id(file_path: Path) -> str:
        """Generate a stable, short clip_id from the resolved file path."""
        return hashlib.sha256(str(file_path.resolve()).encode()).hexdigest()[:16]
