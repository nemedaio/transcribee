from collections.abc import Generator
from datetime import datetime
import json
from pathlib import Path

from sqlalchemy import func, inspect, or_, text
from sqlmodel import Session, SQLModel, create_engine as sqlmodel_create_engine, select

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.logging import get_logger
from lnkdn_transcripts.services.audio import PreparedAudio
from lnkdn_transcripts.services.fetcher import FetchedMedia
from lnkdn_transcripts.services.transcriber import TranscriptionResult
from lnkdn_transcripts.storage.models import (
    AccessAccount,
    AccessAuditAction,
    AccessAuditEvent,
    AccessRole,
    AccessStatus,
    DashboardCounts,
    JobStatus,
    TranscriptJob,
    utc_now,
)

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
        "source_media_path": "TEXT",
        "media_file_path": "TEXT",
        "media_duration_seconds": "INTEGER",
        "source_media_id": "TEXT",
        "extractor_name": "TEXT",
        "fetch_started_at": "TIMESTAMP",
        "fetch_completed_at": "TIMESTAMP",
        "audio_prepared_at": "TIMESTAMP",
        "transcript_language": "TEXT",
        "transcript_segment_count": "INTEGER",
        "transcript_segments_json": "TEXT",
        "retry_count": "INTEGER DEFAULT 0",
        "transcription_started_at": "TIMESTAMP",
        "transcription_completed_at": "TIMESTAMP",
        "artifacts_cleaned_at": "TIMESTAMP",
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

    def list_jobs_by_status(self, statuses: list[JobStatus], limit: int = 20) -> list[TranscriptJob]:
        with Session(self.engine) as session:
            statement = (
                select(TranscriptJob)
                .where(TranscriptJob.status.in_(statuses))
                .order_by(TranscriptJob.updated_at.desc())
                .limit(limit)
            )
            return list(session.exec(statement))

    def dashboard_counts(self) -> DashboardCounts:
        with Session(self.engine) as session:
            statement = select(TranscriptJob.status, func.count()).group_by(TranscriptJob.status)
            rows = list(session.exec(statement))
            counts = {status.value: count for status, count in rows}
            return DashboardCounts(
                queued=counts.get(JobStatus.QUEUED.value, 0),
                fetching=counts.get(JobStatus.FETCHING.value, 0),
                transcribing=counts.get(JobStatus.TRANSCRIBING.value, 0),
                completed=counts.get(JobStatus.COMPLETED.value, 0),
                failed=counts.get(JobStatus.FAILED.value, 0),
                total=sum(counts.values()),
            )

    def mark_fetch_started(self, job_id: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.FETCHING
            job.last_error = None
            job.media_title = None
            job.source_media_path = None
            job.media_file_path = None
            job.media_duration_seconds = None
            job.source_media_id = None
            job.extractor_name = None
            job.transcript_text = None
            job.transcript_language = None
            job.transcript_segment_count = None
            job.transcript_segments_json = None
            job.fetch_completed_at = None
            job.audio_prepared_at = None
            job.transcription_started_at = None
            job.transcription_completed_at = None
            job.artifacts_cleaned_at = None
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
            job.source_media_path = fetched_media.local_path
            job.media_file_path = None
            job.media_duration_seconds = fetched_media.duration_seconds
            job.source_media_id = fetched_media.source_id
            job.extractor_name = fetched_media.extractor
            job.last_error = None
            job.fetch_completed_at = utc_now()
            job.audio_prepared_at = None
            job.artifacts_cleaned_at = None
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
            job.transcription_started_at = None
            job.transcription_completed_at = None
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def mark_audio_prepared(self, job_id: str, prepared_audio: PreparedAudio) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.media_file_path = prepared_audio.local_path
            job.audio_prepared_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def clear_source_media_path(self, job_id: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.source_media_path = None
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
            job.transcript_segments_json = json.dumps(
                [
                    {
                        "start_seconds": segment.start_seconds,
                        "end_seconds": segment.end_seconds,
                        "text": segment.text,
                    }
                    for segment in result.segments
                ]
            )
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
            job.transcript_text = None
            job.transcript_language = None
            job.transcript_segment_count = None
            job.transcript_segments_json = None
            job.transcription_completed_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def reset_for_retry(self, job_id: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.status = JobStatus.QUEUED
            job.last_error = None
            job.media_title = None
            job.source_media_path = None
            job.media_file_path = None
            job.media_duration_seconds = None
            job.source_media_id = None
            job.extractor_name = None
            job.transcript_text = None
            job.transcript_language = None
            job.transcript_segment_count = None
            job.transcript_segments_json = None
            job.fetch_started_at = None
            job.fetch_completed_at = None
            job.audio_prepared_at = None
            job.transcription_started_at = None
            job.transcription_completed_at = None
            job.artifacts_cleaned_at = None
            job.retry_count += 1
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def list_finished_jobs_before(self, cutoff: datetime, limit: int = 100) -> list[TranscriptJob]:
        with Session(self.engine) as session:
            statement = (
                select(TranscriptJob)
                .where(TranscriptJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]))
                .where(TranscriptJob.updated_at < cutoff)
                .where((TranscriptJob.source_media_path.is_not(None)) | (TranscriptJob.media_file_path.is_not(None)))
                .order_by(TranscriptJob.updated_at.asc())
                .limit(limit)
            )
            return list(session.exec(statement))

    def mark_artifacts_cleaned(self, job_id: str) -> TranscriptJob:
        with Session(self.engine) as session:
            job = session.get(TranscriptJob, job_id)
            if job is None:
                raise LookupError(f"Job {job_id} not found")
            job.source_media_path = None
            job.media_file_path = None
            job.artifacts_cleaned_at = utc_now()
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            return job


class AccessRepository:
    def __init__(self, engine) -> None:
        self.engine = engine

    def get_account(self, email: str) -> AccessAccount | None:
        normalized_email = email.strip().lower()
        with Session(self.engine) as session:
            return session.get(AccessAccount, normalized_email)

    def record_access_request(
        self,
        email: str,
        display_name: str | None = None,
        picture_url: str | None = None,
    ) -> AccessAccount:
        normalized_email = email.strip().lower()
        with Session(self.engine) as session:
            account = session.get(AccessAccount, normalized_email)
            created_request = False
            if account is None:
                account = AccessAccount(
                    email=normalized_email,
                    status=AccessStatus.PENDING,
                    role=AccessRole.MEMBER,
                    display_name=display_name,
                    picture_url=picture_url,
                )
                created_request = True
            else:
                if account.status == AccessStatus.PENDING:
                    account.display_name = display_name or account.display_name
                    account.picture_url = picture_url or account.picture_url
                account.updated_at = utc_now()
            session.add(account)
            if created_request:
                self._append_audit_event(
                    session,
                    account_email=normalized_email,
                    action=AccessAuditAction.REQUESTED,
                    note="Google access request created",
                    resulting_status=account.status,
                    resulting_role=account.role,
                )
            session.commit()
            session.refresh(account)
            return account

    def ensure_account(
        self,
        email: str,
        role: AccessRole,
        display_name: str | None = None,
        picture_url: str | None = None,
        approved_by_email: str | None = None,
    ) -> AccessAccount:
        normalized_email = email.strip().lower()
        with Session(self.engine) as session:
            account = session.get(AccessAccount, normalized_email)
            now = utc_now()
            should_log_grant = False
            if account is None:
                account = AccessAccount(
                    email=normalized_email,
                    status=AccessStatus.APPROVED,
                    role=role,
                    display_name=display_name,
                    picture_url=picture_url,
                    requested_at=now,
                    approved_at=now,
                    approved_by_email=approved_by_email,
                    updated_at=now,
                )
                should_log_grant = True
            else:
                should_log_grant = (
                    account.status != AccessStatus.APPROVED
                    or account.role != role
                    or (approved_by_email and account.approved_by_email != approved_by_email)
                )
                account.status = AccessStatus.APPROVED
                account.role = role
                account.display_name = display_name or account.display_name
                account.picture_url = picture_url or account.picture_url
                account.approved_at = account.approved_at or now
                account.approved_by_email = approved_by_email or account.approved_by_email
                account.updated_at = now
            session.add(account)
            if should_log_grant:
                self._append_audit_event(
                    session,
                    account_email=normalized_email,
                    action=AccessAuditAction.GRANTED,
                    actor_email=approved_by_email,
                    note="Google access granted",
                    resulting_status=account.status,
                    resulting_role=account.role,
                )
            session.commit()
            session.refresh(account)
            return account

    def record_login(self, email: str, display_name: str | None = None) -> AccessAccount:
        normalized_email = email.strip().lower()
        with Session(self.engine) as session:
            account = session.get(AccessAccount, normalized_email)
            if account is None:
                raise LookupError(f"Access account {normalized_email} not found")
            account.display_name = display_name or account.display_name
            account.last_login_at = utc_now()
            account.updated_at = utc_now()
            session.add(account)
            self._append_audit_event(
                session,
                account_email=normalized_email,
                action=AccessAuditAction.SIGNED_IN,
                actor_email=normalized_email,
                note="Google sign-in completed",
                resulting_status=account.status,
                resulting_role=account.role,
            )
            session.commit()
            session.refresh(account)
            return account

    def list_accounts(self, statuses: list[AccessStatus], limit: int = 100) -> list[AccessAccount]:
        with Session(self.engine) as session:
            statement = (
                select(AccessAccount)
                .where(AccessAccount.status.in_(statuses))
                .order_by(AccessAccount.updated_at.desc())
                .limit(limit)
            )
            return list(session.exec(statement))

    def list_audit_events(
        self,
        limit: int = 100,
        account_email: str | None = None,
        actions: list[AccessAuditAction] | None = None,
        query: str | None = None,
    ) -> list[AccessAuditEvent]:
        with Session(self.engine) as session:
            statement = select(AccessAuditEvent)
            if account_email:
                statement = statement.where(AccessAuditEvent.account_email == account_email.strip().lower())
            if actions:
                statement = statement.where(AccessAuditEvent.action.in_(actions))
            if query:
                normalized_query = f"%{query.strip().lower()}%"
                statement = statement.where(
                    or_(
                        func.lower(AccessAuditEvent.account_email).like(normalized_query),
                        func.lower(func.coalesce(AccessAuditEvent.actor_email, "")).like(normalized_query),
                        func.lower(func.coalesce(AccessAuditEvent.note, "")).like(normalized_query),
                    )
                )
            statement = statement.order_by(AccessAuditEvent.created_at.desc()).limit(limit)
            return list(session.exec(statement))

    def approve_account(
        self,
        email: str,
        approved_by_email: str,
        role: AccessRole = AccessRole.MEMBER,
    ) -> AccessAccount:
        normalized_email = email.strip().lower()
        with Session(self.engine) as session:
            account = session.get(AccessAccount, normalized_email)
            if account is None:
                account = AccessAccount(email=normalized_email)
            account.status = AccessStatus.APPROVED
            account.role = role
            account.approved_at = utc_now()
            account.approved_by_email = approved_by_email.strip().lower()
            account.updated_at = utc_now()
            session.add(account)
            self._append_audit_event(
                session,
                account_email=normalized_email,
                action=AccessAuditAction.GRANTED,
                actor_email=approved_by_email.strip().lower(),
                note="Admin approval recorded",
                resulting_status=account.status,
                resulting_role=account.role,
            )
            session.commit()
            session.refresh(account)
            return account

    def revoke_account(self, email: str, actor_email: str | None = None) -> AccessAccount:
        normalized_email = email.strip().lower()
        with Session(self.engine) as session:
            account = session.get(AccessAccount, normalized_email)
            if account is None:
                raise LookupError(f"Access account {normalized_email} not found")
            account.status = AccessStatus.REVOKED
            account.role = AccessRole.MEMBER
            account.updated_at = utc_now()
            session.add(account)
            self._append_audit_event(
                session,
                account_email=normalized_email,
                action=AccessAuditAction.REVOKED,
                actor_email=actor_email,
                note="Access revoked",
                resulting_status=account.status,
                resulting_role=account.role,
            )
            session.commit()
            session.refresh(account)
            return account

    def _append_audit_event(
        self,
        session: Session,
        account_email: str,
        action: AccessAuditAction,
        actor_email: str | None = None,
        note: str | None = None,
        resulting_status: AccessStatus | None = None,
        resulting_role: AccessRole | None = None,
    ) -> None:
        session.add(
            AccessAuditEvent(
                account_email=account_email.strip().lower(),
                action=action,
                actor_email=actor_email.strip().lower() if actor_email else None,
                note=note,
                resulting_status=resulting_status,
                resulting_role=resulting_role,
            )
        )
