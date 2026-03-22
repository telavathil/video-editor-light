from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from vacation_editor.config import AppConfig

_CANDIDATE_PATHS = [
    Path("/opt/homebrew/bin/ffmpeg"),   # Apple Silicon Homebrew
    Path("/usr/local/bin/ffmpeg"),      # Intel Homebrew
    Path("/usr/bin/ffmpeg"),            # System install
]


def detect_ffmpeg(config: AppConfig) -> Path:
    """Return the path to the ffmpeg binary.

    Checks config.ffmpeg_path first, then known macOS Homebrew locations.
    Raises FileNotFoundError if not found.
    """
    if config.ffmpeg_path is not None:
        if config.ffmpeg_path.is_file():
            return config.ffmpeg_path
        raise FileNotFoundError(
            f"ffmpeg not found at configured path: {config.ffmpeg_path}\n"
            "Install via: brew install ffmpeg"
        )

    for candidate in _CANDIDATE_PATHS:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "ffmpeg not found. Install via: brew install ffmpeg\n"
        "Or set ffmpeg_path in ~/.vacation_editor/config.json"
    )


def extract_section(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    start_seconds: float,
    end_seconds: float,
) -> Path:
    """Extract a time range from a video file, re-encoding for frame accuracy.

    Uses libx264 + AAC to ensure precise in/out points regardless of keyframe positions.
    Output is suitable for further processing (transitions, concat).

    Raises FileNotFoundError if input_path does not exist.
    Raises RuntimeError if ffmpeg fails.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input clip not found: {input_path}")

    duration = end_seconds - start_seconds
    if duration <= 0:
        raise ValueError(f"end_seconds must be greater than start_seconds (got {duration}s)")

    cmd = [
        str(ffmpeg_path), "-y",
        "-ss", str(start_seconds),
        "-i", str(input_path),
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-avoid_negative_ts", "make_zero",
        str(output_path),
    ]
    _run(cmd, f"extract_section({input_path.name}, {start_seconds:.2f}–{end_seconds:.2f}s)")
    return output_path


def normalize_section(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    target_fps: float = 24.0,
) -> Path:
    """Re-encode a clip to a canonical format required before applying xfade transitions.

    Ensures consistent codec (libx264), pixel format (yuv420p), framerate, audio (aac 48kHz stereo).

    Resolution is preserved from the source.

    Raises RuntimeError if ffmpeg fails.
    """
    cmd = [
        str(ffmpeg_path), "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-vf", f"fps={target_fps},format=yuv420p",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        str(output_path),
    ]
    _run(cmd, f"normalize_section({input_path.name})")
    return output_path


def apply_transition(
    ffmpeg_path: Path,
    clip_a: Path,
    clip_b: Path,
    output_path: Path,
    transition: str,
    duration_ms: int,
) -> Path:
    """Apply a transition between two normalized clips and write to output_path.

    Both clips must be pre-normalized (same resolution, fps, pixel format).
    Supported transitions: "cut", "crossfade", "dissolve", "fade_to_black".

    Raises ValueError for unsupported transition type.
    Raises RuntimeError if ffmpeg fails.
    """
    if transition == "cut":
        return concat_clips(ffmpeg_path, [clip_a, clip_b], output_path)

    duration_sec = duration_ms / 1000.0
    offset = _get_duration(ffmpeg_path, clip_a) - duration_sec

    has_audio = _has_audio(ffmpeg_path, clip_a)

    if transition in ("crossfade", "dissolve"):
        xfade_type = "fade" if transition == "crossfade" else "dissolve"
        if has_audio:
            filter_complex = (
                f"[0:v][1:v]xfade=transition={xfade_type}"
                f":duration={duration_sec}:offset={offset:.4f}[v];"
                f"[0:a][1:a]acrossfade=d={duration_sec}[a]"
            )
            maps = ["-map", "[v]", "-map", "[a]"]
        else:
            filter_complex = (
                f"[0:v][1:v]xfade=transition={xfade_type}"
                f":duration={duration_sec}:offset={offset:.4f}[v]"
            )
            maps = ["-map", "[v]", "-an"]
        cmd = [
            str(ffmpeg_path), "-y",
            "-i", str(clip_a),
            "-i", str(clip_b),
            "-filter_complex", filter_complex,
            *maps,
            str(output_path),
        ]
        _run(cmd, f"apply_transition({transition}, {clip_a.name} → {clip_b.name})")
        return output_path

    if transition == "fade_to_black":
        clip_a_duration = _get_duration(ffmpeg_path, clip_a)
        fade_start = clip_a_duration - duration_sec
        if has_audio:
            filter_complex = (
                f"[0:v]fade=t=out:st={fade_start:.4f}:d={duration_sec}[va];"
                f"[1:v]fade=t=in:st=0:d={duration_sec}[vb];"
                "[va][vb]concat=n=2:v=1:a=0[v];"
                f"[0:a]afade=t=out:st={fade_start:.4f}:d={duration_sec}[aa];"
                f"[1:a]afade=t=in:st=0:d={duration_sec}[ab];"
                "[aa][ab]concat=n=2:v=0:a=1[a]"
            )
            maps = ["-map", "[v]", "-map", "[a]"]
        else:
            filter_complex = (
                f"[0:v]fade=t=out:st={fade_start:.4f}:d={duration_sec}[va];"
                f"[1:v]fade=t=in:st=0:d={duration_sec}[vb];"
                "[va][vb]concat=n=2:v=1:a=0[v]"
            )
            maps = ["-map", "[v]", "-an"]
        cmd = [
            str(ffmpeg_path), "-y",
            "-i", str(clip_a),
            "-i", str(clip_b),
            "-filter_complex", filter_complex,
            *maps,
            str(output_path),
        ]
        _run(cmd, f"apply_transition(fade_to_black, {clip_a.name} → {clip_b.name})")
        return output_path

    raise ValueError(f"Unsupported transition type: {transition!r}")


def concat_clips(ffmpeg_path: Path, clips: list[Path], output_path: Path) -> Path:
    """Concatenate a list of clips in order using the FFmpeg concat demuxer.

    All clips must have the same codec, resolution, and frame rate (use normalize_section first).
    Raises ValueError if clips list is empty.
    Raises RuntimeError if ffmpeg fails.
    """
    if not clips:
        raise ValueError("clips list must not be empty")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        concat_file = Path(f.name)
        for clip in clips:
            f.write(f"file '{clip.resolve()}'\n")

    try:
        cmd = [
            str(ffmpeg_path), "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ]
        _run(cmd, f"concat_clips({len(clips)} clips)")
    finally:
        concat_file.unlink(missing_ok=True)

    return output_path


def final_encode(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    codec: str = "h264",
    fps: int = 24,
    hw_encoding: bool = True,
) -> Path:
    """Encode the assembled clip to the delivery format.

    On macOS, uses VideoToolbox hardware encoders (h264_videotoolbox /
    hevc_videotoolbox) when hw_encoding=True. VideoToolbox does not support
    CRF mode so a high-quality bitrate target (40 Mbps) is used instead.
    Falls back to libx264 / libx265 with CRF=18 when hw_encoding=False.

    Raises RuntimeError if ffmpeg fails.
    """
    if hw_encoding:
        video_codec = "h264_videotoolbox" if codec == "h264" else "hevc_videotoolbox"
        video_quality_opts = ["-b:v", "40M"]
    else:
        video_codec = "libx264" if codec == "h264" else "libx265"
        video_quality_opts = ["-crf", "18", "-preset", "slow"]

    cmd = [
        str(ffmpeg_path), "-y",
        "-i", str(input_path),
        "-c:v", video_codec,
        *video_quality_opts,
        "-vf", f"fps={fps},format=yuv420p",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        str(output_path),
    ]
    _run(cmd, f"final_encode(codec={codec}, fps={fps}, hw={hw_encoding})")
    return output_path


def _has_audio(ffmpeg_path: Path, clip_path: Path) -> bool:
    """Return True if the clip contains at least one audio stream."""
    ffprobe_path = ffmpeg_path.parent / "ffprobe"
    cmd = [
        str(ffprobe_path),
        "-v", "quiet",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(clip_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return bool(result.stdout.strip())


def _get_duration(ffmpeg_path: Path, clip_path: Path) -> float:
    """Return the duration of a clip in seconds using ffprobe."""
    ffprobe_path = ffmpeg_path.parent / "ffprobe"
    cmd = [
        str(ffprobe_path),
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(clip_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {clip_path}:\n{result.stderr}")
    return float(result.stdout.strip())


def _run(cmd: list[str], label: str) -> None:
    """Run an FFmpeg command, raising RuntimeError on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed [{label}]:\n"
            f"Command: {' '.join(cmd)}\n"
            f"stderr: {result.stderr[-2000:]}"
        )
