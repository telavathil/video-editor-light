from __future__ import annotations

import tempfile
from pathlib import Path

from vacation_editor.config import AppConfig


def ensure_project_dirs(config: AppConfig) -> None:
    """Create all project directories if they do not exist."""
    config.project_dir.mkdir(parents=True, exist_ok=True)
    config.annotations_dir.mkdir(parents=True, exist_ok=True)
    config.exports_dir.mkdir(parents=True, exist_ok=True)
    (config.project_dir / "clips").mkdir(parents=True, exist_ok=True)


def get_export_path(config: AppConfig, composition_id: str, extension: str = ".mp4") -> Path:
    """Return the output file path for a composition export."""
    ext = extension if extension.startswith(".") else f".{extension}"
    return config.exports_dir / f"{composition_id}{ext}"


def get_temp_dir(config: AppConfig) -> Path:
    """Return a temporary directory for intermediate FFmpeg files.

    The caller is responsible for cleanup (use tempfile.TemporaryDirectory in production).
    This returns a path inside the system temp dir, not the project dir.
    """
    tmp = Path(tempfile.gettempdir()) / "vacation_editor"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp
