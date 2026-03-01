from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

TransitionType = Literal["cut", "crossfade", "dissolve", "fade_to_black"]


class CompositionSection(BaseModel):
    clip_id: str
    section_id: str
    order: int
    transition: TransitionType = "crossfade"
    transition_duration_ms: int = 500

    def with_transition(
        self, transition: TransitionType, duration_ms: int | None = None
    ) -> CompositionSection:
        update: dict[str, object] = {"transition": transition}
        if duration_ms is not None:
            update["transition_duration_ms"] = duration_ms
        return self.model_copy(update=update)


class Composition(BaseModel):
    composition_id: str
    name: str
    sections: list[CompositionSection] = Field(default_factory=list)
    music_track: str | None = None   # path to music file — informational only
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(name: str) -> Composition:
        return Composition(
            composition_id=str(uuid.uuid4()),
            name=name,
        )

    def with_section_appended(self, section: CompositionSection) -> Composition:
        next_order = max((s.order for s in self.sections), default=-1) + 1
        return self.model_copy(update={
            "sections": [*self.sections, section.model_copy(update={"order": next_order})],
        })

    def with_section_removed(self, index: int) -> Composition:
        sections = [s for i, s in enumerate(self.sections) if i != index]
        reordered = [s.model_copy(update={"order": i}) for i, s in enumerate(sections)]
        return self.model_copy(update={"sections": reordered})

    def with_sections_reordered(self, new_order: list[int]) -> Composition:
        """Reorder sections by providing a list of current indices in the desired order."""
        reordered = [
            self.sections[i].model_copy(update={"order": pos})
            for pos, i in enumerate(new_order)
        ]
        return self.model_copy(update={"sections": reordered})

    def with_transition_updated(
        self,
        index: int,
        transition: TransitionType,
        duration_ms: int | None = None,
    ) -> Composition:
        updated = [
            s.with_transition(transition, duration_ms) if i == index else s
            for i, s in enumerate(self.sections)
        ]
        return self.model_copy(update={"sections": updated})

    def with_music_track(self, path: str | None) -> Composition:
        return self.model_copy(update={"music_track": path})
