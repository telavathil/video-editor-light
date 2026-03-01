from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vacation_editor.config import AppConfig
from vacation_editor.models.annotation import ClipAnnotation, Section
from vacation_editor.models.clip import ClipMetadata
from vacation_editor.models.job import JobStatus

# ---------------------------------------------------------------------------
# AppConfig pointing to tmp_path
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        project_dir=tmp_path / "project",
        annotations_dir=tmp_path / "project" / "annotations",
        exports_dir=tmp_path / "project" / "exports",
    )


# ---------------------------------------------------------------------------
# Test video clip (generated via FFmpeg — requires ffmpeg on PATH)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_clip_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a 3-second 1920x1080 H.264 test clip using FFmpeg.

    Skips if FFmpeg is not installed.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg not found — skipping tests that require a real video file")

    out = tmp_path_factory.mktemp("clips") / "test_clip.mp4"
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=3:size=1920x1080:rate=24",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        pytest.skip(f"ffmpeg test clip generation failed: {result.stderr.decode()}")

    return out


# ---------------------------------------------------------------------------
# Sample model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_section() -> Section:
    return Section.new(start_seconds=1.0, end_seconds=3.0, label="test section")


@pytest.fixture
def sample_annotation(sample_section: Section) -> ClipAnnotation:
    return ClipAnnotation(clip_id="abc123").with_section_added(sample_section)


@pytest.fixture
def sample_metadata() -> ClipMetadata:
    return ClipMetadata(
        clip_id="abc123",
        file_name="test.mp4",
        duration_seconds=10.0,
        resolution=(1920, 1080),
        codec="h264",
        fps=24.0,
        file_size_bytes=1_000_000,
        source_path="/tmp/test.mp4",
    )


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_video_storage(sample_metadata: ClipMetadata, tmp_path: Path) -> MagicMock:
    """Mock VideoStorage that returns a predictable path and metadata."""
    mock = MagicMock()
    mock.get_local_path.return_value = tmp_path / "test.mp4"
    mock.get_metadata.return_value = sample_metadata
    mock.list_clips.return_value = ["abc123"]
    return mock


@pytest.fixture
def mock_annotation_store(sample_annotation: ClipAnnotation) -> MagicMock:
    mock = MagicMock()
    mock.load.return_value = sample_annotation
    mock.list_annotated_clips.return_value = ["abc123"]
    return mock


@pytest.fixture
def mock_composition_processor() -> MagicMock:
    mock = MagicMock()
    mock.submit.return_value = "test-job-id"
    mock.poll.return_value = JobStatus(
        job_id="test-job-id", status="running", progress_percent=50.0
    )
    return mock
