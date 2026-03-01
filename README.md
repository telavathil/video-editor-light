# Vacation Video Editor

A macOS desktop app for creating polished vacation videos from DJI drone clips. Built in Python with PyQt6, it handles everything a non-expert editor needs — annotation, composition, and music sync — while DaVinci Resolve handles colour grading separately.

## Tools

**Video Annotation Tool** — Load DJI clips (Action 5 Pro / Action 2, H.264 and H.265), watch them in a built-in player, and mark interesting in/out sections on a visual timeline. Annotations are saved to JSON and can be reviewed, adjusted, or deleted.

**Composition Engine** — Order your marked sections across clips, choose transitions (cuts, crossfades, dissolves), and export a stitched 4K MP4 with hardware-accelerated encoding. In long-form mode, the engine analyses a music track with librosa, aligns transitions to beats, and mixes the audio into the final export.

**Music Search** *(optional)* — Search free music libraries by mood and duration, preview tracks, and download directly into the composition workflow.

## Requirements

- macOS (uses AVFoundation for video playback and `h264_videotoolbox` / `hevc_videotoolbox` for encoding)
- Python 3.12+
- FFmpeg — install via Homebrew: `brew install ffmpeg`

## Installation

```bash
pip install -e .
```

## Usage

```bash
python -m vacation_editor
```

## Architecture

The app is built with cloud migration in mind. All storage and processing operations are accessed through Protocol interfaces (`VideoStorage`, `AnnotationStore`, `CompositionProcessor`), with local implementations used today. Swapping in cloud backends (S3, PostgreSQL, GPU job queues) requires only new implementations of those interfaces — no changes to the GUI or business logic.

## Implementation Plan

See [`PLAN.md`](PLAN.md) for the full phased implementation plan, design decisions, and session-by-session progress checklist.
