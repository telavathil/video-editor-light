from __future__ import annotations

import pytest

from vacation_editor.config import AppConfig
from vacation_editor.services.local.annotation_store import LocalAnnotationStore
from vacation_editor.services.local.composition_processor import LocalCompositionProcessor
from vacation_editor.services.local.video_storage import LocalVideoStorage
from vacation_editor.utils.providers import (
    build_annotation_store,
    build_composition_processor,
    build_video_storage,
)


class TestProviderFactory:
    def test_build_video_storage_returns_local(self, tmp_config: AppConfig) -> None:
        storage = build_video_storage(tmp_config)
        assert isinstance(storage, LocalVideoStorage)

    def test_build_annotation_store_returns_local(self, tmp_config: AppConfig) -> None:
        store = build_annotation_store(tmp_config)
        assert isinstance(store, LocalAnnotationStore)

    def test_build_composition_processor_returns_local(self, tmp_config: AppConfig) -> None:
        storage = build_video_storage(tmp_config)
        store = build_annotation_store(tmp_config)
        processor = build_composition_processor(tmp_config, storage, store)
        assert isinstance(processor, LocalCompositionProcessor)

    def test_cloud_mode_raises_for_video_storage(self) -> None:
        config = AppConfig(cloud_mode=True)
        with pytest.raises(NotImplementedError, match="cloud_mode=False"):
            build_video_storage(config)

    def test_cloud_mode_raises_for_annotation_store(self) -> None:
        config = AppConfig(cloud_mode=True)
        with pytest.raises(NotImplementedError, match="cloud_mode=False"):
            build_annotation_store(config)

    def test_cloud_mode_raises_for_composition_processor(
        self, mock_video_storage, mock_annotation_store
    ) -> None:
        config = AppConfig(cloud_mode=True)
        with pytest.raises(NotImplementedError, match="cloud_mode=False"):
            build_composition_processor(config, mock_video_storage, mock_annotation_store)
