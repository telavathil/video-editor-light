from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field, model_validator


class Section(BaseModel):
    section_id: str
    label: str = ""
    start_seconds: float
    end_seconds: float
    notes: str = ""

    @model_validator(mode="after")
    def end_must_be_after_start(self) -> Section:
        if self.end_seconds <= self.start_seconds:
            raise ValueError(
                f"end_seconds ({self.end_seconds}) must be greater than "
                f"start_seconds ({self.start_seconds})"
            )
        return self

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    @staticmethod
    def new(start_seconds: float, end_seconds: float, label: str = "") -> Section:
        return Section(
            section_id=str(uuid.uuid4()),
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            label=label,
        )

    def with_label(self, label: str) -> Section:
        return self.model_copy(update={"label": label})

    def with_times(self, start_seconds: float, end_seconds: float) -> Section:
        return self.model_copy(update={
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
        })


class ClipAnnotation(BaseModel):
    clip_id: str
    sections: list[Section] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def with_section_added(self, section: Section) -> ClipAnnotation:
        return self.model_copy(update={
            "sections": [*self.sections, section],
            "updated_at": datetime.now(UTC),
        })

    def with_section_removed(self, section_id: str) -> ClipAnnotation:
        return self.model_copy(update={
            "sections": [s for s in self.sections if s.section_id != section_id],
            "updated_at": datetime.now(UTC),
        })

    def with_section_updated(self, updated: Section) -> ClipAnnotation:
        return self.model_copy(update={
            "sections": [
                updated if s.section_id == updated.section_id else s
                for s in self.sections
            ],
            "updated_at": datetime.now(UTC),
        })

    def with_sections_replaced(self, sections: list[Section]) -> ClipAnnotation:
        return self.model_copy(update={
            "sections": sections,
            "updated_at": datetime.now(UTC),
        })
