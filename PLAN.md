# Implementation Plan: Vacation Video Editor (Cloud-Ready)

## Overview

A macOS desktop application (PyQt6, terminal-only) for creating vacation highlight videos from DJI drone clips. Three tools: a Video Annotation Tool (GUI), a Composition Engine (FFmpeg + librosa), and an optional Music Search tool. Designed with Protocol interfaces and dependency injection so the app can be migrated to a cloud backend in the future without touching GUI or business logic.

---

## Confirmed Platform Decisions

- **Runtime**: macOS, launched via `python -m vacation_editor`
- **GUI**: PyQt6 with AVFoundation backend (native H.264/H.265 support)
- **Hardware encoding**: `h264_videotoolbox` / `hevc_videotoolbox` by default
- **FFmpeg discovery**: Auto-detect from `/opt/homebrew/bin/ffmpeg` and `/usr/local/bin/ffmpeg`
- **Keyboard shortcuts**: Cmd-based (macOS conventions)
- **Packaging**: No `.app` bundle — terminal only
- **Cloud**: Protocols and stubs only — no cloud implementation in this phase

---

## Directory Structure

```
vacation_editor/
  __init__.py
  __main__.py                          # Entry: python -m vacation_editor
  config.py                            # AppConfig dataclass (with cloud fields)

  models/
    __init__.py
    clip.py                            # ClipMetadata (Pydantic)
    annotation.py                      # ClipAnnotation, Section (Pydantic)
    composition.py                     # Composition, CompositionSection (Pydantic)
    job.py                             # JobStatus (Pydantic)

  services/
    __init__.py
    ffprobe.py                         # Stateless FFprobe wrapper
    ffmpeg.py                          # Stateless FFmpeg extract/stitch/transition functions
    protocols/
      __init__.py
      video_storage.py                 # VideoStorage Protocol
      annotation_store.py              # AnnotationStore Protocol
      composition_processor.py         # CompositionProcessor Protocol
    local/
      __init__.py
      video_storage.py                 # LocalVideoStorage
      annotation_store.py              # LocalAnnotationStore
      composition_processor.py         # LocalCompositionProcessor
    cloud/                             # STUBS ONLY — documents future architecture
      __init__.py
      video_storage.py                 # S3VideoStorage (NotImplementedError)
      annotation_store.py              # PostgresAnnotationStore (NotImplementedError)
      composition_processor.py         # CloudCompositionProcessor (NotImplementedError)

  utils/
    __init__.py
    providers.py                       # build_video_storage(), build_annotation_store(), build_composition_processor()
    paths.py                           # Config-aware path resolution (no hardcoded paths)
    validators.py                      # Input validation helpers

  gui/
    __init__.py
    main_window.py                     # MainWindow — wires providers to controllers via DI
    annotation/
      __init__.py
      video_player.py                  # QMediaPlayer + QVideoWidget wrapper
      timeline_widget.py               # Custom timeline with section markers
      section_list.py                  # QListWidget for marked sections
      file_browser.py                  # Clip browser / import
      controller.py                    # AnnotationController (receives providers via DI)
    composition/
      __init__.py
      ordering_widget.py               # Drag-and-drop section ordering
      transition_picker.py             # Transition type selector
      export_dialog.py                 # Export settings + progress
      controller.py                    # CompositionController (receives providers via DI)
    music/
      __init__.py
      beat_timeline.py                 # Beat-aligned timeline visualization
      music_search.py                  # Optional music search widget
      controller.py                    # MusicController (receives providers via DI)

  audio/
    __init__.py
    beat_detection.py                  # Stateless librosa beat detection
    beat_fitting.py                    # Beat-fitting algorithm
    mixer.py                           # Audio mixing via FFmpeg

tests/
  __init__.py
  conftest.py                          # Mock providers, tmp AppConfig, test clip fixture
  unit/
    models/
    services/
    utils/
  integration/
    services/
  e2e/

pyproject.toml
```

---

## Design Rules (Mandatory)

1. **Never hardcode local paths** — all paths flow through `AppConfig` and storage protocols
2. **Pydantic models are cloud-agnostic** — no storage-specific fields, serialize to JSON natively
3. **FFmpeg/FFprobe functions are stateless** — pure input→output, callable from cloud workers unchanged
4. **Progress callbacks map to job polling** — `LocalCompositionProcessor` uses `on_progress(percent)` callback today; cloud uses `poll(job_id) -> JobStatus` tomorrow; the `CompositionProcessor` Protocol hides the difference
5. **Constructor injection everywhere** — controllers never instantiate providers directly
6. **Immutability** — all state updates create new objects, never mutate

---

## Phase 0: Project Foundation (Cloud-Ready)

**Goal**: Establish all infrastructure, models, protocols, and local implementations before any GUI work begins.

### Step 0.1 — Scaffolding + pyproject.toml

- Create full directory tree with empty `__init__.py` files
- `pyproject.toml` with Python 3.12+, dependencies:
  - `PyQt6>=6.6`, `pydantic>=2.5`, `ffmpeg-python>=0.2`
  - `librosa>=0.10` (optional extra for Phase 3)
  - Dev: `pytest`, `pytest-qt`, `pytest-cov`, `ruff`, `mypy`
- Create `vacation_editor/__main__.py` minimal entry point
- **Risk**: Low

### Step 0.2 — AppConfig

- **File**: `vacation_editor/config.py`
- Frozen dataclass with local and cloud fields:

```python
@dataclass(frozen=True)
class AppConfig:
    project_dir: Path = Path.home() / "VacationEditor"
    annotations_dir: Path = ...
    exports_dir: Path = ...
    ffmpeg_path: Path | None = None        # auto-detected if None
    ffprobe_path: Path | None = None
    hw_encoder: str = "h264_videotoolbox"
    default_transition: str = "crossfade"
    transition_duration_ms: int = 500

    # Cloud fields — dormant in local mode
    cloud_mode: bool = False
    cloud_region: str = "us-east-1"
    s3_bucket: str | None = None
    api_base_url: str | None = None
```

- `load_config()` reads from `~/.vacation_editor/config.json` or returns defaults
- **Risk**: Low

### Step 0.3 — Pydantic Models

- **`models/clip.py`**: `ClipMetadata(clip_id, file_name, duration_seconds, resolution, codec, fps, file_size_bytes, source_path)`
- **`models/annotation.py`**: `Section(section_id, label, start_seconds, end_seconds, notes)` and `ClipAnnotation(clip_id, sections, created_at, updated_at)`
- **`models/composition.py`**: `CompositionSection(clip_id, section_id, order, transition, transition_duration_ms)` and `Composition(composition_id, name, sections, music_track, created_at)`
- **`models/job.py`**: `JobStatus(job_id, status: pending|running|complete|failed, progress_percent, error_message, result_path)`
- All models are pure data — no storage logic, serialize to JSON natively
- **Risk**: Low

### Step 0.4 — Protocol Definitions

- **`services/protocols/video_storage.py`**:

```python
class VideoStorage(Protocol):
    def get_local_path(self, clip_id: str) -> Path: ...
    def upload(self, local_path: Path, clip_id: str) -> None: ...
    def list_clips(self) -> list[str]: ...
    def get_metadata(self, clip_id: str) -> ClipMetadata: ...
```

- **`services/protocols/annotation_store.py`**:

```python
class AnnotationStore(Protocol):
    def save(self, annotation: ClipAnnotation) -> None: ...
    def load(self, clip_id: str) -> ClipAnnotation: ...
    def list_annotated_clips(self) -> list[str]: ...
    def delete(self, clip_id: str) -> None: ...
```

- **`services/protocols/composition_processor.py`**:

```python
class CompositionProcessor(Protocol):
    def submit(self, composition: Composition) -> str: ...   # returns job_id
    def poll(self, job_id: str) -> JobStatus: ...
    def get_result(self, job_id: str) -> Path: ...
    def cancel(self, job_id: str) -> None: ...
```

- These are the seams between business logic and infrastructure — the only place that changes for cloud
- **Risk**: Low

### Step 0.5 — Local Protocol Implementations

- **`services/local/video_storage.py`** — `LocalVideoStorage`: reads/writes disk, `upload()` copies to project dir, `get_metadata()` calls FFprobe service
- **`services/local/annotation_store.py`** — `LocalAnnotationStore`: saves/loads `{clip_id}.json` in `annotations_dir` using Pydantic `.model_dump_json()` / `.model_validate_json()`
- **`services/local/composition_processor.py`** — `LocalCompositionProcessor`: `submit()` starts FFmpeg pipeline in background thread, returns UUID job_id; `poll()` returns current `JobStatus` from a thread-safe in-memory dict; `cancel()` terminates FFmpeg subprocess
- **Risk**: Medium — `LocalCompositionProcessor` threading needs `threading.Lock` around job state dict

### Step 0.6 — Stateless FFprobe Service

- **File**: `services/ffprobe.py`
- `detect_ffprobe(config: AppConfig) -> Path` — auto-detect from config, then `/opt/homebrew/bin/ffprobe`, then `/usr/local/bin/ffprobe`
- `probe_clip(ffprobe_path: Path, clip_path: Path) -> ClipMetadata` — runs FFprobe, parses JSON output
- Pure functions — no state, no side effects beyond subprocess call
- **Risk**: Low

### Step 0.7 — Stateless FFmpeg Service

- **File**: `services/ffmpeg.py`
- `detect_ffmpeg(config: AppConfig) -> Path`
- `extract_section(ffmpeg_path, input_path, output_path, start_seconds, end_seconds, hw_encoder) -> Path`
- `apply_transition(ffmpeg_path, clip_a, clip_b, output_path, transition, duration_ms) -> Path`
- `concat_clips(ffmpeg_path, clips: list[Path], output_path) -> Path`
- All functions are stateless — same signatures work in a cloud worker
- **Risk**: Medium — FFmpeg `xfade` filter requires matching resolution/fps/pixel format; normalization step needed

### Step 0.8 — Provider Factory

- **File**: `utils/providers.py`

```python
def build_video_storage(config: AppConfig) -> VideoStorage:
    if config.cloud_mode:
        raise NotImplementedError("Cloud storage not yet implemented")
    return LocalVideoStorage(config)

def build_annotation_store(config: AppConfig) -> AnnotationStore:
    if config.cloud_mode:
        raise NotImplementedError("Cloud annotation store not yet implemented")
    return LocalAnnotationStore(config)

def build_composition_processor(config: AppConfig) -> CompositionProcessor:
    if config.cloud_mode:
        raise NotImplementedError("Cloud composition processor not yet implemented")
    return LocalCompositionProcessor(config)
```

- Single place where local vs. cloud is decided
- **Risk**: Low

### Step 0.9 — Cloud Stub Files

- **Files**: `services/cloud/video_storage.py`, `annotation_store.py`, `composition_processor.py`
- Each class contains `raise NotImplementedError` in every method
- Inline comments document the intended implementation:
  - `S3VideoStorage`: use `boto3`, `get_local_path()` downloads to local cache
  - `PostgresAnnotationStore`: use `psycopg`, store annotations as JSONB
  - `CloudCompositionProcessor`: post to REST API / job queue, poll status, download result from S3
- **Risk**: Low — documentation only

### Step 0.10 — Path Utilities

- **File**: `utils/paths.py`
- `ensure_project_dirs(config)` — create project dirs on first run
- `get_export_path(config, composition_id, extension) -> Path`
- `get_temp_dir(config) -> Path`
- No hardcoded paths — all resolution goes through config
- **Risk**: Low

### Step 0.11 — Phase 0 Tests

- Model serialization/deserialization round-trips for all Pydantic models
- `LocalAnnotationStore` save/load/delete with `tmp_path` fixture
- `LocalVideoStorage` import and retrieve with test clip fixture
- Provider factory: returns correct local types; raises `NotImplementedError` for cloud mode
- `conftest.py` fixtures: `AppConfig` pointing to `tmp_path`, mock providers, 3-second H.264 test clip generated by FFmpeg
- **Target**: 80%+ coverage on Phase 0 code
- **Risk**: Low

---

## Phase 1: Video Annotation Tool GUI

**Goal**: A working PyQt6 app that plays DJI clips, marks in/out sections, displays a visual timeline, and persists annotations.

### Step 1.1 — Video Player Widget

- **File**: `gui/annotation/video_player.py`
- `VideoPlayerWidget(QWidget)` wrapping `QMediaPlayer` + `QVideoWidget`
- Methods: `load_clip(path: Path)`, `play()`, `pause()`, `seek(seconds: float)`, `get_position() -> float`
- Signals: `position_changed(float)`, `duration_changed(float)`, `playback_state_changed(str)`
- Playback speed control (0.25x, 0.5x, 1x, 2x)
- Uses AVFoundation backend (default on macOS with PyQt6) — natively handles H.264/H.265
- **Risk**: Low — AVFoundation confirmed to support DJI codecs on macOS

### Step 1.2 — Frame-Accurate Seeking

- Extend `VideoPlayerWidget` with frame-step forward/backward (advance by 1/fps seconds)
- Keyboard shortcuts: Space (play/pause), Left/Right (1s seek), Shift+Left/Right (5s seek), J/K/L (rewind/pause/forward)
- Scrub via slider drag — `QSlider` bound to `QMediaPlayer.setPosition()`
- **Risk**: Medium — `QMediaPlayer.setPosition()` seeks to nearest keyframe by default; frame-accurate mode may need additional FFmpeg decode pass

### Step 1.3 — Mark In / Mark Out Controls

- "Mark In" button (keyboard: `I`) — stores current position as `pending_in`
- "Mark Out" button (keyboard: `O`) — creates `Section(start=pending_in, end=current_position)`, validates end > start, emits `section_marked` signal
- Visual flash/highlight on mark confirmation
- **Risk**: Low

### Step 1.4 — Timeline Widget

- **File**: `gui/annotation/timeline_widget.py`
- `TimelineWidget(QWidget)` with custom `paintEvent`
- Horizontal bar = clip duration; colored rectangles = marked sections; vertical line = playhead
- Click-to-seek: clicking the timeline seeks the video
- Zoom (Ctrl+scroll) and horizontal scroll for long clips
- Signals: `seek_requested(float)`, `section_marked(float, float)`
- **Risk**: Medium — custom painting requires careful coordinate math; use `QGraphicsScene`/`QGraphicsView` for interactive items

### Step 1.5 — Draggable Section Handles

- Draggable left/right handles on each section rectangle in the timeline
- Drag adjusts section start or end time, snaps to frame boundaries (round to 1/fps)
- Prevents invalid states (end ≤ start)
- Emits signal when section modified so section list and annotation state update
- **Risk**: Medium — Qt drag interaction on custom graphics items requires correct mouse event handling

### Step 1.6 — Section List Panel

- **File**: `gui/annotation/section_list.py`
- `SectionListWidget(QWidget)` — `QListWidget` showing all sections: index, start, end, duration, label
- Selecting a row seeks player to section start
- Actions: "Delete Section", "Play Section" (plays start→end), "Edit Label"
- Double-click plays section
- Signals: `section_selected(Section)`, `section_deleted(str)`, `sections_reordered(list[Section])`
- **Risk**: Low

### Step 1.7 — Annotation Controller

- **File**: `gui/annotation/controller.py`

```python
class AnnotationController:
    def __init__(
        self,
        video_storage: VideoStorage,       # injected
        annotation_store: AnnotationStore, # injected
    ):
```

- Loads clip via `video_storage.get_local_path(clip_id)`
- Saves/loads via `annotation_store`
- Auto-saves on every section change (debounced 2s)
- Undo/redo stack (store immutable state snapshots)
- Never instantiates providers directly
- **Risk**: Low

### Step 1.8 — File Browser

- **File**: `gui/annotation/file_browser.py`
- List of video clips in project directory
- "Import" button opens `QFileDialog` filtered to `.mp4`, `.mov`, `.m4v`
- Import calls `video_storage.upload()` (copies to project dir for local storage)
- Shows clip metadata (duration, resolution) via `video_storage.get_metadata()`
- Visual indicator (checkmark) on clips that already have annotations
- Signals: `clip_selected(str)` — emits clip_id
- **Risk**: Low

### Step 1.9 — Annotation Tab Assembly

- Wire all widgets into layout: file browser (left) | video player + timeline (center) | section list (right)
- **Risk**: Low

### Step 1.10 — Keyboard Shortcuts (macOS)

| Key | Action |
|-----|--------|
| `Space` | Play/Pause |
| `I` | Mark In |
| `O` | Mark Out |
| `Left` / `Right` | Seek ±1s |
| `Shift+Left` / `Shift+Right` | Seek ±5s |
| `J` / `K` / `L` | Rewind / Pause / Forward |
| `Cmd+S` | Save annotations |
| `Cmd+Z` / `Cmd+Shift+Z` | Undo / Redo |
| `Cmd+O` | Import clip |
| `Delete` | Remove selected section |

### Step 1.11 — Phase 1 Tests

- Controller tests with mock `VideoStorage` and `AnnotationStore` (no file I/O in unit tests)
- Timeline coordinate calculation tests
- Section list add/remove/reorder logic tests
- Widget smoke tests via `pytest-qt`
- **Target**: 80%+ coverage on controller and model interaction logic
- **Risk**: Medium — GUI testing more fragile than unit testing

---

## Phase 2: Composition Engine — Short Clip Mode

**Goal**: Take ordered annotated sections, stitch them with FFmpeg transitions, export a 4K MP4.

### Step 2.1 — Section Extraction Pipeline

- Implement extraction step in `LocalCompositionProcessor`
- For each `CompositionSection`, call `ffmpeg.extract_section()`
- Store extracted clips in temp dir (cleaned up on completion or crash via `atexit`)
- Normalize all sections to canonical format before transitions: H.264, yuv420p, original resolution, constant fps
- Progress tracking: extraction = 0–50% of total job
- **Risk**: Medium — FFmpeg subprocess management, error handling for corrupt clips

### Step 2.2 — Transition Pipeline

- Implement `ffmpeg.apply_transition()` for:
  - `cut` — simple concatenation, no processing
  - `crossfade` — FFmpeg `xfade` filter with `transition=fade`
  - `dissolve` — FFmpeg `xfade` filter with `transition=dissolve`
  - `fade_to_black` — `fade=out` on clip A + `fade=in` on clip B
- **Normalization required before `xfade`**: all inputs must match resolution, fps, pixel format
- Progress: 50–90% of total job
- **Risk**: Medium-High — `xfade` filter is strict about format matching; normalization step is critical

### Step 2.3 — Final Stitch Pipeline

- `ffmpeg.concat_clips()` to concatenate all processed segments
- Final encode: `h264_videotoolbox` (default) or `hevc_videotoolbox`; 4K; 24/25fps
- Clean up temp files on success; log and preserve on failure for debugging
- Progress: 90–100%
- **Risk**: Low

### Step 2.4 — Section Ordering UI

- **File**: `gui/composition/ordering_widget.py`
- `OrderingWidget(QWidget)` — drag-and-drop list of sections
- Load annotation JSON files to populate section list
- Thumbnail for each section (FFmpeg frame extract at section midpoint, generated async via `QThreadPool`)
- Add/remove sections from composition
- Per-transition type dropdown + duration spinner between each pair
- Default transition logic: cut between same-clip sections, crossfade between different clips
- Signals: `composition_changed(Composition)`
- **Risk**: Medium — thumbnail generation for many sections could be slow

### Step 2.5 — Transition Picker Widget

- **File**: `gui/composition/transition_picker.py`
- `QComboBox` (Cut / Crossfade / Dissolve / Fade to Black) + `QSpinBox` for duration
- **Risk**: Low

### Step 2.6 — Export Dialog

- **File**: `gui/composition/export_dialog.py`
- Settings: output path, codec (H.264/H.265), framerate (24/25)
- Progress bar polling `CompositionProcessor.poll()` via `QTimer`
- Cancel button calls `CompositionProcessor.cancel()`
- On completion: show output path, "Reveal in Finder" button
- **Risk**: Low

### Step 2.7 — Composition Controller

- **File**: `gui/composition/controller.py`

```python
class CompositionController:
    def __init__(
        self,
        video_storage: VideoStorage,
        annotation_store: AnnotationStore,
        composition_processor: CompositionProcessor, # injected
    ):
```

- Coordinates ordering widget, export dialog, transition review
- Submits via `composition_processor.submit()`; polls status; updates export dialog progress
- **Risk**: Low

### Step 2.8 — Transition Review Step

- Click any transition in the ordered list to open transition editor
- Change type/duration
- "Preview transition" — renders a 5-second clip centered on the transition point, plays in player widget
- **Risk**: Low-Medium — single transition preview is fast

### Step 2.9 — Phase 2 Tests

- Unit: FFmpeg command construction (mock subprocess), composition model validation
- Integration: full extract→normalize→transition→stitch pipeline with real 3-second test clip, verify output duration/resolution
- `LocalCompositionProcessor` lifecycle: submit/poll/cancel
- Controller tests with mock `CompositionProcessor`
- **Target**: 80%+ coverage
- **Risk**: Medium — integration tests require real FFmpeg binary and test clips

---

## Phase 3: Long-Form Music-Synced Composition

**Goal**: Analyze music for beats, align transitions to musical events, fit composition to music length, mix audio.

### Step 3.1 — Beat Detection Service

- **File**: `audio/beat_detection.py`
- Stateless functions:

```python
def detect_beats(audio_path: Path) -> list[float]:     # beat timestamps in seconds
def detect_tempo(audio_path: Path) -> float:           # BPM
def detect_downbeats(audio_path: Path) -> list[float]: # downbeat timestamps
```

- Uses `librosa.beat.beat_track()` for tempo/beats, `librosa.onset.onset_detect()` for onsets
- Stateless — callable from cloud worker unchanged
- **Risk**: Medium — accuracy varies by genre; provide manual adjustment UI

### Step 3.2 — Beat-Fitting Algorithm

- **File**: `audio/beat_fitting.py`

```python
def fit_sections_to_beats(
    sections: list[CompositionSection],
    beats: list[float],
    strategy: Literal["cut", "stretch", "speed_ramp"] = "cut",
) -> list[FittedSection]:
```

- Aligns section boundaries to nearest beat timestamps
- If total sections > music duration: trim proportionally, prefer cuts at beat boundaries
- If total sections < music duration: extend final section or add fade-to-black at phrase boundary
- Prefer downbeats for transitions (stronger visual-musical sync)
- Returns new `Composition` with adjusted timings — never mutates input
- **Risk**: High — most algorithmically complex part; start with greedy "nearest beat" algorithm and iterate

### Step 3.3 — Audio Mixer

- **File**: `audio/mixer.py`

```python
def mix_audio(
    video_path: Path,
    music_path: Path,
    output_path: Path,
    music_volume: float = 0.7,
    original_audio_volume: float = 0.3,
) -> Path:
```

- FFmpeg `amix` filter for mixing tracks
- 2s fade-in at start, 3s fade-out at end of music track
- Stateless
- **Risk**: Low

### Step 3.4 — Beat Timeline UI

- **File**: `gui/music/beat_timeline.py`
- `BeatTimelineWidget(QWidget)` showing:
  - Waveform visualization (rendered via librosa, displayed as `QPixmap`)
  - Beat marker overlays (vertical lines at beat timestamps)
  - Section arrangement overlaid on music timeline
  - Drag beat markers to adjust manually
- **Risk**: Medium — combined waveform + beat + section visualization is complex; reuse timeline architecture from Phase 1

### Step 3.5 — Music Controller

- **File**: `gui/music/controller.py`

```python
class MusicController:
    def __init__(
        self,
        video_storage: VideoStorage,
        composition_processor: CompositionProcessor,
    ):
```

- Loads music file, runs beat detection, runs beat-fitting on current composition
- Provides "Sync to Music" action
- Integrates with `CompositionProcessor` for final export with mixed audio
- **Risk**: Low

### Step 3.6 — Phase 3 Tests

- Beat-fitting: unit test with known inputs (5 sections totaling 60s against 45s music; verify transitions land within 0.1s of beats)
- Music mixer: integration test with real audio file
- Beat detection: test produces reasonable output (within tolerance range)
- **Target**: 80%+
- **Risk**: Medium

---

## Phase 4: Music Search Tool (Optional)

**Goal**: Help users find free music tracks by mood and duration. Lowest priority — skip if time-constrained.

### Step 4.1 — Music Search Service

- **File**: `services/music_search.py`
- Pluggable `MusicSearchProvider` Protocol — supports swapping APIs
- Initial implementation: Free Music Archive API
- `search(keywords: str, min_duration: float, max_duration: float) -> list[MusicTrack]`
- `download(track: MusicTrack, output_path: Path) -> Path`
- Rate limiting and caching
- Fallback: open browser to FMA or YouTube Audio Library if API unavailable
- **Risk**: High — FMA API has been historically unreliable; design as pluggable so alternatives (Freesound.org, Pixabay) can be added

### Step 4.2 — Music Search UI

- **File**: `gui/music/music_search.py`
- Keyword input, duration range spinners, search button
- Results list: title, artist, duration, license
- "Preview" button (plays audio in player widget)
- "Download" button (saves to music library, feeds into composition)
- **Risk**: Low

### Step 4.3 — Phase 4 Tests

- Mock API responses for search
- Test download and local storage
- **Target**: 80%+
- **Risk**: Low

---

## Phase 5: App Shell and Polish

**Goal**: Unified application, preferences, error handling, keyboard shortcut reference.

### Step 5.1 — MainWindow with Tabs

- **File**: `gui/main_window.py`
- `MainWindow(QMainWindow)`:
  - Tab 1: Annotation Tool (Phase 1)
  - Tab 2: Composition Engine (Phase 2)
  - Tab 3: Music (Phase 3, shown if librosa available)
  - macOS menu bar: File, Edit, View, Help
  - Status bar: background job status, FFmpeg availability indicator
- Provider wiring — **only place providers are instantiated**:

```python
class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        storage   = build_video_storage(config)
        store     = build_annotation_store(config)
        processor = build_composition_processor(config)

        self.annotation_ctrl   = AnnotationController(storage, store)
        self.composition_ctrl  = CompositionController(storage, store, processor)
        self.music_ctrl        = MusicController(storage, processor)
```

- **Risk**: Low

### Step 5.2 — Entry Point

- **File**: `vacation_editor/__main__.py`

```python
def main():
    config = load_config()
    ensure_project_dirs(config)
    app = QApplication(sys.argv)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())
```

### Step 5.3 — Preferences Dialog

- **File**: `gui/preferences.py`
- Edit `AppConfig`: project directory, default encoder, default transition, FFmpeg path override
- Cloud fields hidden when `cloud_mode=False`
- Changes persisted to `~/.vacation_editor/config.json`
- **Risk**: Low

### Step 5.4 — Error Handling

- FFmpeg not found: dialog with `brew install ffmpeg` instructions
- Corrupt video file: skip with warning, do not crash
- Disk full during export: catch `OSError`, clean up temp files, show dialog
- FFmpeg process failure: capture stderr, display in error dialog with "Copy to Clipboard"
- Logging via Python `logging` module to `~/.vacation_editor/logs/`
- **Risk**: Low

### Step 5.5 — Keyboard Shortcut Reference

`Cmd+/` opens a shortcut reference dialog.

| Key | Action |
|-----|--------|
| `Space` | Play/Pause |
| `I` / `O` | Mark In / Mark Out |
| `Left` / `Right` | Seek ±1s |
| `Shift+Left` / `Shift+Right` | Seek ±5s |
| `J` / `K` / `L` | Rewind / Pause / Forward |
| `Cmd+S` | Save annotations |
| `Cmd+Z` / `Cmd+Shift+Z` | Undo / Redo |
| `Cmd+O` | Import clip |
| `Cmd+E` | Export composition |
| `Delete` | Remove selected section |
| `Cmd+/` | Show shortcuts |

### Step 5.6 — Phase 5 Tests

- App launches without crash
- E2E: import clip → mark section → create composition → export
- **Target**: 80%+ overall
- **Risk**: Medium

---

## Cloud Migration Path (Future — Nothing to Build Now)

The Protocol interfaces and provider factory are the only preparation needed. When ready to go cloud:

| Step | What to do |
|------|------------|
| 1 | Implement `S3VideoStorage` in `services/cloud/` using `boto3`; `get_local_path()` downloads to local cache |
| 2 | Implement `PostgresAnnotationStore` using `psycopg`; store annotations as JSONB |
| 3 | Implement `CloudCompositionProcessor`; `submit()` posts to job queue; `poll()` queries REST API; result downloaded from S3 |
| 4 | Add FastAPI backend: `POST /compositions`, `GET /compositions/{id}/status`, `GET /compositions/{id}/result` |
| 5 | Update `providers.py` factory to return cloud implementations when `cloud_mode=True` |
| **0 changes** | GUI, controllers, models, FFmpeg service — **completely untouched** |

### Cloud Cost Estimates (Personal Use — ~5 exports/month, ~50GB footage)

| Service | Provider | Estimated Monthly Cost |
|---------|----------|------------------------|
| Video storage (50GB) | Cloudflare R2 | ~$5–14 (no egress fees) |
| Video storage (50GB) | AWS S3 | ~$7–21 + egress costs |
| Composition compute | Modal GPU (T4) | ~$0.01–0.02/export |
| Composition compute | AWS MediaConvert | $0.045 per 3-min video |
| Composition compute | Cloud CPU (c6i) | ~$0.10–0.30/export |
| API hosting | Fly.io | ~$3–5 |
| Database | Neon free tier | $0 |
| **Total (R2 + Modal + Fly.io)** | | **~$9–20/month** |
| **Total (S3 + MediaConvert + Fly.io)** | | **~$11–27/month** |

> **Recommendation**: Cloudflare R2 for storage (zero egress fees matter significantly for 4K video), Modal for compute (pay-per-second GPU), Fly.io for API hosting.

---

## Risk Summary

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | DJI codec playback in QMediaPlayer | **LOW** | AVFoundation natively handles H.264/H.265 on macOS |
| 2 | FFmpeg `xfade` filter format mismatch | MEDIUM | Normalize all sections to canonical format before any transition |
| 3 | `LocalCompositionProcessor` threading | MEDIUM | `threading.Lock` around job state dict; Qt signals for progress updates |
| 4 | librosa beat detection accuracy | MEDIUM | Manual beat marker adjustment UI; "beat sensitivity" slider; tap-to-beat fallback |
| 5 | 4K proxy/performance during playback | MEDIUM | Offer lower-res proxy for annotation playback; full res only for export |
| 6 | Beat-fitting algorithm quality | HIGH | Start with greedy "nearest beat" algorithm; iterate based on real use |
| 7 | FMA API reliability (Tool 3) | HIGH | Pluggable provider; browser fallback; skip if time-constrained |

---

## Success Criteria

- [ ] App launches via `python -m vacation_editor` on macOS
- [ ] Can import and play DJI H.264 and H.265 clips with smooth scrubbing
- [ ] Can mark in/out sections with I/O keyboard shortcuts
- [ ] Sections persist to JSON and survive app restart
- [ ] Can order sections across multiple clips via drag-and-drop
- [ ] Can export stitched 4K video with crossfade transitions
- [ ] Hardware encoding (`h264_videotoolbox`) used for export
- [ ] Music beat detection and sync work for long-form compositions
- [ ] All providers injected via constructor — no direct instantiation in controllers
- [ ] All paths go through `AppConfig` — no hardcoded paths anywhere
- [ ] All FFmpeg/FFprobe functions are stateless
- [ ] Cloud stubs exist and document the future architecture
- [ ] `cloud_mode=True` raises `NotImplementedError` cleanly
- [ ] Test coverage ≥ 80% across all phases

---

## Estimated Effort

| Phase | Description | Effort |
|-------|-------------|--------|
| 0 | Foundation + Cloud-Ready Abstractions | 2–3 days |
| 1 | Video Annotation Tool GUI | 6–8 days |
| 2 | Composition Engine (short clip) | 6–8 days |
| 3 | Music-Synced Long-Form | 4–5 days |
| 4 | Music Search (optional) | 2–3 days |
| 5 | App Shell + Polish | 2–3 days |
| **Total** | | **~22–30 days** |

---

## Session Checklist

Use this section to track progress across implementation sessions. Check off steps as they are completed.

### Phase 0 — Foundation
- [x] 0.1 Scaffolding + pyproject.toml
- [x] 0.2 AppConfig
- [x] 0.3 Pydantic models
- [x] 0.4 Protocol definitions
- [x] 0.5 Local implementations
- [x] 0.6 FFprobe service
- [x] 0.7 FFmpeg service
- [x] 0.8 Provider factory
- [x] 0.9 Cloud stub files
- [x] 0.10 Path utilities
- [x] 0.11 Tests

### Phase 1 — Annotation Tool
- [x] 1.1 Video player widget  (gui/annotation/video_player.py)
- [x] 1.2 Frame-accurate seeking  (transport_bar.py + keyboard shortcuts)
- [x] 1.3 Mark In / Mark Out controls  (mark_bar.py)
- [x] 1.4 Timeline widget  (timeline_widget.py — painted ticks/track/playhead)
- [x] 1.5 Draggable section handles  (timeline_widget.py — mouse drag on handles)
- [x] 1.6 Section list panel  (section_list.py)
- [x] 1.7 Annotation controller  (controller.py — auto-save, undo/redo)
- [x] 1.8 File browser  (file_browser.py)
- [x] 1.9 Tab assembly  (tab.py)
- [x] 1.10 Keyboard shortcuts  (tab.py _setup_shortcuts)
- [x] 1.11 Tests  (114 tests passing — controller, widgets, models, services)

### Phase 2 — Composition Engine (Short Clip)
- [x] 2.1 Section extraction pipeline  (ffmpeg.extract_section — was already complete)
- [x] 2.2 Transition pipeline  (ffmpeg.apply_transition — was already complete)
- [x] 2.3 Final stitch pipeline  (ffmpeg.final_encode — hardware-accelerated VideoToolbox)
- [x] 2.4 Section ordering UI  (SectionLibraryWidget + SequenceTrackWidget)
- [x] 2.5 Transition picker widget  (TransitionPickerWidget with codec/fps selectors)
- [x] 2.6 Export dialog  (ExportDialog — in-progress + complete states)
- [x] 2.7 Composition controller  (CompositionController with QTimer polling)
- [x] 2.8 ExportSettings model  (output_path, codec, fps, hw_encoding)
- [x] 2.9 Tests  (142 tests passing — +28 new: controller, ExportSettings model)

### Phase 3 — Music-Synced Long-Form
- [ ] 3.1 Beat detection service
- [ ] 3.2 Beat-fitting algorithm
- [ ] 3.3 Audio mixer
- [ ] 3.4 Beat timeline UI
- [ ] 3.5 Music controller
- [ ] 3.6 Tests

### Phase 4 — Music Search (Optional)
- [ ] 4.1 Music search service
- [ ] 4.2 Music search UI
- [ ] 4.3 Tests

### Phase 5 — App Shell + Polish
- [ ] 5.1 MainWindow with tabs
- [ ] 5.2 Entry point
- [ ] 5.3 Preferences dialog
- [ ] 5.4 Error handling
- [ ] 5.5 Keyboard shortcut reference
- [ ] 5.6 Tests
