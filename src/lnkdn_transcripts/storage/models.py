from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptJob(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    source_url: str
    normalized_url: str
    source_domain: str = Field(index=True)
    provider: str = Field(default="generic", index=True)
    status: JobStatus = Field(default=JobStatus.QUEUED, index=True)
    transcript_text: str | None = None
    last_error: str | None = None
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
    last_error: str | None
    created_at: datetime
    updated_at: datetime
