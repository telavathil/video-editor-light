from __future__ import annotations

# CLOUD STUB — Not yet implemented.
#
# Future implementation notes:
#   - Use psycopg (psycopg3) for PostgreSQL
#   - Store annotations as JSONB column for queryability
#   - Schema: annotations(clip_id TEXT PRIMARY KEY, data JSONB, updated_at TIMESTAMPTZ)
#   - Connection string from AppConfig.api_base_url or a dedicated DB config field
#   - Consider Neon (serverless PostgreSQL) for low-cost personal use
#
# Install when ready: pip install psycopg[binary]
from vacation_editor.models.annotation import ClipAnnotation


class PostgresAnnotationStore:
    """Future cloud implementation of AnnotationStore using PostgreSQL."""

    _MSG = "PostgresAnnotationStore not yet implemented. Set cloud_mode=False to use local storage."

    def save(self, annotation: ClipAnnotation) -> None:
        raise NotImplementedError(self._MSG)

    def load(self, clip_id: str) -> ClipAnnotation:
        raise NotImplementedError(self._MSG)

    def list_annotated_clips(self) -> list[str]:
        raise NotImplementedError(self._MSG)

    def delete(self, clip_id: str) -> None:
        raise NotImplementedError(self._MSG)
