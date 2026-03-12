from collections.abc import Generator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine, select

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.logging import get_logger
from lnkdn_transcripts.services.fetcher import FetchedMedia
from lnkdn_transcripts.services.transcriber import TranscriptionResult
from lnkdn_transcripts.storage.models import JobStatus, TranscriptJob, utc_now

logger = get_logger(__name__)


def create_engine(settings: Settings):
    database_url = settings.database_url or f"sqlite:///{Path(settings.data_dir) / 'app.db'}"
    if database_url.startswith("sqlite:///") and settings.database_url is None:
        Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    return sqlmodel_create_engine(database_url, connect_args={"check_same_thread": False})


def create_db_and_tables(engine) -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_sqlite_transcript_job_table(engine)
    logger.info("db.init complete=true")


def _migrate_sqlite_transcript_job_table(engine) -> None:
    if engine.url.get_backend_name() != "sqlite":
        return

    expected_columns = {
        "media_title": "TEXT",
        "media_file_path": "TEXT",
        "media_duration_seconds": "INTEGER",
        "source_media_id": "TEXT",
        "extractor_name": "TEXT",
        "fetch_started_at": "TIMESTAMP",
        "fetch_completed_at": "TIMESTAMP",
        "transcript_language": "TEXT",
        "transcript_segment_count": "INTEGER",
        "transcription_started_at": "TIMESTAMP",
        "transcription_completed_at": "TIMESTAMP",
    }
    existing_columns = {column["name"] for column in inspect(engine).get_columns("transcriptjob")}

    with engine.begin() as connection:
        for column_name, column_type in expected_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(text(f"ALTER TABLE transcriptjob ADD COLUMN {column_name} {column_type}"))
            logger.info("db.migrate table=transcriptjob added_column=%s", column_name)


class JobRepository:
    def __init__(self, engine) -> None:
        self.engine = engine

    def session(self) -> Generator[Session, None, None]:
        with Session(self.engine) as session:
            yield session

    def create_job(self, job: TranscriptJob) -> TranscriptJob:
        with Session(self.engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def get_job(self, job_id: str) -> TranscriptJob | None:
        with Session(self.engine) as session:
            return session.get(TranscriptJob, job_id)

    def list_recent_jobs(self, limit: int = 10) -> list[TranscriptJob]:
        with Session(self.engine) as session:
            statement = select(TranscriptJob).order_by(TranscriptJob.created_at.desc()).limit(limit)
            return list(session.exec(statement))

    def mark_fetch_started(self, job_id: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.FETCHING
            job.last_error = None
            job.fetch_started_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def mark_fetch_succeeded(self, job_id: str, fetched_media: FetchedMedia) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.FETCHED
            job.media_title = fetched_media.title
            job.media_file_path = fetched_media.local_path
            job.media_duration_seconds = fetched_media.duration_seconds
            job.source_media_id = fetched_media.source_id
            job.extractor_name = fetched_media.extractor
            job.last_error = None
            job.fetch_completed_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def mark_fetch_failed(self, job_id: str, error_message: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.FAILED
            job.last_error = error_message
            job.fetch_completed_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def mark_transcription_started(self, job_id: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.TRANSCRIBING
            job.last_error = None
            job.transcription_started_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def mark_transcription_succeeded(self, job_id: str, result: TranscriptionResult) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.COMPLETED
            job.transcript_text = result.text
            job.transcript_language = result.language
            job.transcript_segment_count = len(result.segments)
            job.last_error = None
            job.transcription_completed_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def mark_transcription_failed(self, job_id: str, error_message: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.FAILED
            job.last_error = error_message
            job.transcription_completed_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job
