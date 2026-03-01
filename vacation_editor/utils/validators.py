from __future__ import annotations

from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi"}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".m4a"}


def is_supported_video(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def is_supported_audio(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def validate_section_times(start_seconds: float, end_seconds: float) -> None:
    """Raise ValueError if section times are invalid."""
    if start_seconds < 0:
        raise ValueError(f"start_seconds must be >= 0 (got {start_seconds})")
    if end_seconds <= start_seconds:
        raise ValueError(
            f"end_seconds ({end_seconds}) must be greater than start_seconds ({start_seconds})"
        )
