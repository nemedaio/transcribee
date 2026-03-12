from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from lnkdn_transcripts.services.fetcher import MediaFetcher
from lnkdn_transcripts.services.transcriber import MediaTranscriber
from lnkdn_transcripts.logging import get_logger
from lnkdn_transcripts.storage.models import TranscriptJob
from lnkdn_transcripts.storage.repo import JobRepository

logger = get_logger(__name__)


class InvalidVideoUrlError(ValueError):
    """Raised when a submitted URL is not suitable for a transcription job."""


@dataclass
class NormalizedVideoUrl:
    source_url: str
    normalized_url: str
    source_domain: str
    provider: str


class JobService:
    def __init__(
        self,
        repository: JobRepository,
        media_fetcher: MediaFetcher,
        media_transcriber: MediaTranscriber,
    ) -> None:
        self.repository = repository
        self.media_fetcher = media_fetcher
        self.media_transcriber = media_transcriber

    def create_job(self, raw_url: str) -> TranscriptJob:
        normalized = self._normalize_url(raw_url)
        job = TranscriptJob(
            source_url=normalized.source_url,
            normalized_url=normalized.normalized_url,
            source_domain=normalized.source_domain,
            provider=normalized.provider,
        )
        created_job = self.repository.create_job(job)
        logger.info(
            "jobs.create id=%s provider=%s domain=%s status=%s",
            created_job.id,
            created_job.provider,
            created_job.source_domain,
            created_job.status,
        )
        return self.process_fetch(created_job.id)

    def get_job(self, job_id: str) -> TranscriptJob | None:
        job = self.repository.get_job(job_id)
        if job is None:
            logger.warning("jobs.get_missing id=%s", job_id)
            return None
        logger.info("jobs.get id=%s status=%s", job.id, job.status)
        return job

    def list_recent_jobs(self, limit: int = 10) -> list[TranscriptJob]:
        jobs = self.repository.list_recent_jobs(limit=limit)
        logger.info("jobs.list count=%s", len(jobs))
        return jobs

    def process_fetch(self, job_id: str) -> TranscriptJob:
        job = self.repository.get_job(job_id)
        if job is None:
            raise LookupError(f"Job {job_id} not found")

        job = self.repository.mark_fetch_started(job.id)
        logger.info("jobs.fetch_start id=%s status=%s", job.id, job.status)

        try:
            fetched_media = self.media_fetcher.fetch(job)
        except Exception as exc:
            error_message = str(exc)
            failed_job = self.repository.mark_fetch_failed(job.id, error_message)
            logger.warning("jobs.fetch_failed id=%s error=%s", failed_job.id, failed_job.last_error)
            return failed_job

        fetched_job = self.repository.mark_fetch_succeeded(job.id, fetched_media)
        logger.info(
            "jobs.fetch_succeeded id=%s status=%s path=%s",
            fetched_job.id,
            fetched_job.status,
            fetched_job.media_file_path,
        )
        return self.process_transcription(fetched_job.id)

    def process_transcription(self, job_id: str) -> TranscriptJob:
        job = self.repository.get_job(job_id)
        if job is None:
            raise LookupError(f"Job {job_id} not found")
        if not job.media_file_path:
            failed_job = self.repository.mark_transcription_failed(job.id, "No local media file is available")
            logger.warning("jobs.transcription_failed id=%s error=%s", failed_job.id, failed_job.last_error)
            return failed_job

        job = self.repository.mark_transcription_started(job.id)
        logger.info("jobs.transcription_start id=%s status=%s", job.id, job.status)

        try:
            transcription_result = self.media_transcriber.transcribe(job.media_file_path)
        except Exception as exc:
            failed_job = self.repository.mark_transcription_failed(job.id, str(exc))
            logger.warning("jobs.transcription_failed id=%s error=%s", failed_job.id, failed_job.last_error)
            return failed_job

        completed_job = self.repository.mark_transcription_succeeded(job.id, transcription_result)
        logger.info(
            "jobs.transcription_succeeded id=%s status=%s language=%s",
            completed_job.id,
            completed_job.status,
            completed_job.transcript_language,
        )
        return completed_job

    def _normalize_url(self, raw_url: str) -> NormalizedVideoUrl:
        cleaned_url = raw_url.strip()
        parsed = urlsplit(cleaned_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            logger.warning("jobs.invalid_url submitted=%r", raw_url)
            raise InvalidVideoUrlError("Only absolute http(s) video URLs are supported")

        normalized_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
        source_domain = parsed.netloc.lower()
        provider = self._detect_provider(source_domain)
        return NormalizedVideoUrl(
            source_url=cleaned_url,
            normalized_url=normalized_url,
            source_domain=source_domain,
            provider=provider,
        )

    @staticmethod
    def _detect_provider(source_domain: str) -> str:
        if "linkedin.com" in source_domain:
            return "linkedin"
        return "generic"
