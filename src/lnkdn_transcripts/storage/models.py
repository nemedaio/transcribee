from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    QUEUED = "queued"
    FETCHING = "fetching"
    FETCHED = "fetched"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptJob(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    source_url: str
    normalized_url: str
    source_domain: str = Field(index=True)
    provider: str = Field(default="generic", index=True)
    status: JobStatus = Field(default=JobStatus.QUEUED, index=True)
    media_title: str | None = None
    media_file_path: str | None = None
    media_duration_seconds: int | None = None
    source_media_id: str | None = None
    extractor_name: str | None = None
    transcript_text: str | None = None
    transcript_language: str | None = None
    transcript_segment_count: int | None = None
    last_error: str | None = None
    fetch_started_at: datetime | None = None
    fetch_completed_at: datetime | None = None
    transcription_started_at: datetime | None = None
    transcription_completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class JobRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_url: str
    normalized_url: str
    source_domain: str
    provider: str
    status: JobStatus
    media_title: str | None
    media_file_path: str | None
    media_duration_seconds: int | None
    source_media_id: str | None
    extractor_name: str | None
    transcript_text: str | None
    transcript_language: str | None
    transcript_segment_count: int | None
    last_error: str | None
    fetch_started_at: datetime | None
    fetch_completed_at: datetime | None
    transcription_started_at: datetime | None
    transcription_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
