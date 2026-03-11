from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine, select

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.logging import get_logger
from lnkdn_transcripts.storage.models import TranscriptJob

logger = get_logger(__name__)


def create_engine(settings: Settings):
    database_url = settings.database_url or f"sqlite:///{Path(settings.data_dir) / 'app.db'}"
    if database_url.startswith("sqlite:///") and settings.database_url is None:
        Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    return sqlmodel_create_engine(database_url, connect_args={"check_same_thread": False})


def create_db_and_tables(engine) -> None:
    SQLModel.metadata.create_all(engine)
    logger.info("db.init complete=true")


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
