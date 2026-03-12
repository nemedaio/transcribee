from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.logging import get_logger
from lnkdn_transcripts.storage.models import CleanupSummary, TranscriptJob

logger = get_logger(__name__)


class ArtifactCleanupService:
    def __init__(self, settings: Settings) -> None:
        self.media_root = Path(settings.media_dir or Path(settings.data_dir) / "media")
        self.retain_source_media = settings.retain_source_media
        self.retention_days = settings.artifact_retention_days

    def cleanup_source_media(self, path: str | None) -> int:
        if self.retain_source_media or not path:
            return 0
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink()
            logger.info("artifacts.source_deleted path=%s", file_path)
            return 1
        return 0

    def retention_cutoff(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=self.retention_days)

    def cleanup_job_artifacts(self, job: TranscriptJob) -> CleanupSummary:
        deleted_files = 0
        deleted_dirs = 0
        candidate_paths = [job.source_media_path, job.media_file_path]
        parent_dirs: set[Path] = set()

        for candidate in candidate_paths:
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists():
                if path.is_file():
                    path.unlink()
                    deleted_files += 1
                    logger.info("artifacts.file_deleted job_id=%s path=%s", job.id, path)
                parent_dirs.add(path.parent)

        for directory in sorted(parent_dirs, reverse=True):
            if directory.exists() and directory.is_dir():
                shutil.rmtree(directory, ignore_errors=True)
                deleted_dirs += 1
                logger.info("artifacts.dir_deleted job_id=%s path=%s", job.id, directory)

        return CleanupSummary(jobs_cleaned=1, files_deleted=deleted_files, directories_deleted=deleted_dirs)
