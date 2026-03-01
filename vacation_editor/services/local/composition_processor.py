from __future__ import annotations

import logging
import tempfile
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from vacation_editor.config import AppConfig
from vacation_editor.models.job import JobStatus
from vacation_editor.services import ffmpeg as ffmpeg_service

if TYPE_CHECKING:
    from vacation_editor.models.composition import Composition
    from vacation_editor.services.protocols.annotation_store import AnnotationStore
    from vacation_editor.services.protocols.video_storage import VideoStorage

logger = logging.getLogger(__name__)


class LocalCompositionProcessor:
    """Runs the FFmpeg composition pipeline in a background thread.

    Thread safety: all access to _jobs is protected by _lock.
    Cancellation: each job has a threading.Event; the pipeline thread checks it
    between stages and sets it on cancel().
    """

    def __init__(
        self,
        config: AppConfig,
        video_storage: VideoStorage,
        annotation_store: AnnotationStore,
    ) -> None:
        self._config = config
        self._video_storage = video_storage
        self._annotation_store = annotation_store
        self._jobs: dict[str, JobStatus] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def submit(self, composition: Composition) -> str:
        job_id = str(uuid.uuid4())
        cancel_event = threading.Event()

        with self._lock:
            self._jobs[job_id] = JobStatus(job_id=job_id)
            self._cancel_events[job_id] = cancel_event

        thread = threading.Thread(
            target=self._run_pipeline,
            args=(job_id, composition, cancel_event),
            daemon=True,
            name=f"composition-{job_id[:8]}",
        )
        thread.start()
        return job_id

    def poll(self, job_id: str) -> JobStatus:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Unknown job_id: {job_id!r}")
            return self._jobs[job_id]

    def get_result(self, job_id: str) -> Path:
        status = self.poll(job_id)
        if not status.is_complete:
            raise RuntimeError(
                f"Job {job_id!r} is not complete (status: {status.status})"
            )
        assert status.result_path is not None
        return Path(status.result_path)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            if self._jobs[job_id].is_done:
                return
            self._cancel_events[job_id].set()

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _update_status(self, job_id: str, status: JobStatus) -> None:
        with self._lock:
            self._jobs[job_id] = status

    def _run_pipeline(
        self,
        job_id: str,
        composition: Composition,
        cancel_event: threading.Event,
    ) -> None:
        self._update_status(job_id, JobStatus(job_id=job_id).as_running(0.0))

        try:
            ffmpeg_path = ffmpeg_service.detect_ffmpeg(self._config)
            output_path = self._config.exports_dir / f"{composition.composition_id}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory(prefix="vacation_editor_") as tmp_dir:
                tmp = Path(tmp_dir)
                sections = sorted(composition.sections, key=lambda s: s.order)
                total = len(sections)

                # Stage 1: Extract each section (0–50%)
                extracted: list[Path] = []
                for i, comp_section in enumerate(sections):
                    if cancel_event.is_set():
                        self._update_status(job_id, JobStatus(job_id=job_id).as_failed("Cancelled"))
                        return

                    annotation = self._annotation_store.load(comp_section.clip_id)
                    section = next(
                        (s for s in annotation.sections if s.section_id == comp_section.section_id),
                        None,
                    )
                    if section is None:
                        raise RuntimeError(
                            f"Section {comp_section.section_id!r} not found in annotation "
                            f"for clip {comp_section.clip_id!r}"
                        )

                    clip_path = self._video_storage.get_local_path(comp_section.clip_id)
                    out = tmp / f"extracted_{i:03d}.mp4"
                    ffmpeg_service.extract_section(
                        ffmpeg_path, clip_path, out,
                        section.start_seconds, section.end_seconds,
                    )
                    extracted.append(out)

                    progress = (i + 1) / total * 50
                    self._update_status(job_id, JobStatus(job_id=job_id).as_running(progress))

                # Stage 2: Normalize all sections (50–70%)
                normalized: list[Path] = []
                for i, clip in enumerate(extracted):
                    if cancel_event.is_set():
                        self._update_status(job_id, JobStatus(job_id=job_id).as_failed("Cancelled"))
                        return

                    out = tmp / f"normalized_{i:03d}.mp4"
                    ffmpeg_service.normalize_section(ffmpeg_path, clip, out)
                    normalized.append(out)

                    progress = 50 + (i + 1) / total * 20
                    self._update_status(job_id, JobStatus(job_id=job_id).as_running(progress))

                # Stage 3: Apply transitions (70–90%)
                if len(normalized) == 1:
                    processed = normalized
                else:
                    processed = self._apply_transitions(
                        ffmpeg_path, normalized, sections, tmp, job_id, cancel_event
                    )
                    if cancel_event.is_set():
                        return

                # Stage 4: Final concat and encode (90–100%)
                self._update_status(job_id, JobStatus(job_id=job_id).as_running(90.0))

                if len(processed) == 1:
                    import shutil
                    shutil.copy2(processed[0], output_path)
                else:
                    ffmpeg_service.concat_clips(ffmpeg_path, processed, output_path)

                self._update_status(
                    job_id,
                    JobStatus(job_id=job_id).as_complete(str(output_path)),
                )
                logger.info("Composition complete: %s", output_path)

        except Exception as e:
            logger.exception("Composition pipeline failed for job %s", job_id)
            self._update_status(job_id, JobStatus(job_id=job_id).as_failed(str(e)))

    def _apply_transitions(
        self,
        ffmpeg_path: Path,
        clips: list[Path],
        sections: list,
        tmp: Path,
        job_id: str,
        cancel_event: threading.Event,
    ) -> list[Path]:
        """Apply transitions between consecutive clips, returning a list of merged clips."""
        result = [clips[0]]
        for i in range(1, len(clips)):
            if cancel_event.is_set():
                self._update_status(job_id, JobStatus(job_id=job_id).as_failed("Cancelled"))
                return result

            prev = result[-1]
            curr = clips[i]
            transition = sections[i].transition
            duration_ms = sections[i].transition_duration_ms
            out = tmp / f"transition_{i:03d}.mp4"

            ffmpeg_service.apply_transition(
                ffmpeg_path, prev, curr, out, transition, duration_ms
            )
            result = [*result[:-1], out]

            progress = 70 + i / (len(clips) - 1) * 20
            self._update_status(job_id, JobStatus(job_id=job_id).as_running(progress))

        return result
