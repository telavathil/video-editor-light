from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_CONFIG_PATH = Path.home() / ".vacation_editor" / "config.json"


@dataclass(frozen=True)
class AppConfig:
    project_dir: Path = field(default_factory=lambda: Path.home() / "VacationEditor")
    annotations_dir: Path = field(
        default_factory=lambda: Path.home() / "VacationEditor" / "annotations"
    )
    exports_dir: Path = field(
        default_factory=lambda: Path.home() / "VacationEditor" / "exports"
    )
    ffmpeg_path: Path | None = None    # auto-detected if None
    ffprobe_path: Path | None = None   # auto-detected if None
    hw_encoder: str = "h264_videotoolbox"
    default_transition: str = "crossfade"
    transition_duration_ms: int = 500

    # Cloud fields — dormant in local mode
    cloud_mode: bool = False
    cloud_region: str = "us-east-1"
    s3_bucket: str | None = None
    api_base_url: str | None = None


def load_config() -> AppConfig:
    """Load config from ~/.vacation_editor/config.json, falling back to defaults."""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text())
            path_keys = (
                "project_dir", "annotations_dir", "exports_dir", "ffmpeg_path", "ffprobe_path"
            )
            for key in path_keys:
                if key in data and data[key] is not None:
                    data[key] = Path(data[key])
            return AppConfig(**data)
        except Exception:
            pass  # Fall through to defaults if config is corrupt
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Persist config to ~/.vacation_editor/config.json."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "project_dir": str(config.project_dir),
        "annotations_dir": str(config.annotations_dir),
        "exports_dir": str(config.exports_dir),
        "ffmpeg_path": str(config.ffmpeg_path) if config.ffmpeg_path else None,
        "ffprobe_path": str(config.ffprobe_path) if config.ffprobe_path else None,
        "hw_encoder": config.hw_encoder,
        "default_transition": config.default_transition,
        "transition_duration_ms": config.transition_duration_ms,
        "cloud_mode": config.cloud_mode,
        "cloud_region": config.cloud_region,
        "s3_bucket": config.s3_bucket,
        "api_base_url": config.api_base_url,
    }
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))
