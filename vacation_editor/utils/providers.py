from __future__ import annotations

from typing import TYPE_CHECKING

from vacation_editor.config import AppConfig
from vacation_editor.services.local.annotation_store import LocalAnnotationStore
from vacation_editor.services.local.composition_processor import LocalCompositionProcessor
from vacation_editor.services.local.video_storage import LocalVideoStorage

if TYPE_CHECKING:
    from vacation_editor.services.protocols.annotation_store import AnnotationStore
    from vacation_editor.services.protocols.composition_processor import CompositionProcessor
    from vacation_editor.services.protocols.video_storage import VideoStorage


def build_video_storage(config: AppConfig) -> VideoStorage:
    """Return the appropriate VideoStorage implementation for the given config."""
    if config.cloud_mode:
        raise NotImplementedError(
            "Cloud video storage not yet implemented. Set cloud_mode=False."
        )
    return LocalVideoStorage(config)


def build_annotation_store(config: AppConfig) -> AnnotationStore:
    """Return the appropriate AnnotationStore implementation for the given config."""
    if config.cloud_mode:
        raise NotImplementedError(
            "Cloud annotation store not yet implemented. Set cloud_mode=False."
        )
    return LocalAnnotationStore(config)


def build_composition_processor(
    config: AppConfig,
    video_storage: VideoStorage,
    annotation_store: AnnotationStore,
) -> CompositionProcessor:
    """Return the appropriate CompositionProcessor implementation for the given config.

    Note: the processor needs video_storage and annotation_store to look up clips and
    sections during pipeline execution.
    """
    if config.cloud_mode:
        raise NotImplementedError(
            "Cloud composition processor not yet implemented. Set cloud_mode=False."
        )
    return LocalCompositionProcessor(config, video_storage, annotation_store)
