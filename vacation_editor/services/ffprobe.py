from __future__ import annotations

import json
import subprocess
from pathlib import Path

from vacation_editor.config import AppConfig
from vacation_editor.models.clip import ClipMetadata

_CANDIDATE_PATHS = [
    Path("/opt/homebrew/bin/ffprobe"),   # Apple Silicon Homebrew
    Path("/usr/local/bin/ffprobe"),      # Intel Homebrew
    Path("/usr/bin/ffprobe"),            # System install
]


def detect_ffprobe(config: AppConfig) -> Path:
    """Return the path to the ffprobe binary.

    Checks config.ffprobe_path first, then known macOS Homebrew locations.
    Raises FileNotFoundError if not found.
    """
    if config.ffprobe_path is not None:
        if config.ffprobe_path.is_file():
            return config.ffprobe_path
        raise FileNotFoundError(
            f"ffprobe not found at configured path: {config.ffprobe_path}\n"
            "Install via: brew install ffmpeg"
        )

    for candidate in _CANDIDATE_PATHS:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "ffprobe not found. Install via: brew install ffmpeg\n"
        "Or set ffprobe_path in ~/.vacation_editor/config.json"
    )


def probe_clip(ffprobe_path: Path, clip_path: Path) -> ClipMetadata:
    """Run ffprobe on a clip and return its metadata.

    Raises FileNotFoundError if clip_path does not exist.
    Raises RuntimeError if ffprobe fails or output cannot be parsed.
    """
    if not clip_path.exists():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    cmd = [
        str(ffprobe_path),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(clip_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed for {clip_path}:\n{result.stderr}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}") from e

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise RuntimeError(f"No video stream found in {clip_path}")

    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0))
    file_size = int(fmt.get("size", clip_path.stat().st_size))

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    codec = video_stream.get("codec_name", "unknown")

    # Parse frame rate — stored as "24/1" or "30000/1001"
    fps_str = video_stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    return ClipMetadata(
        clip_id=ClipMetadata.make_clip_id(clip_path),
        file_name=clip_path.name,
        duration_seconds=duration,
        resolution=(width, height),
        codec=codec,
        fps=fps,
        file_size_bytes=file_size,
        source_path=str(clip_path),
    )
