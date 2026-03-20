from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from yt_dlp import YoutubeDL

from transcribee.config import Settings
from transcribee.logging import get_logger
from transcribee.storage.models import TranscriptJob

logger = get_logger(__name__)


class MediaFetchError(RuntimeError):
    """Raised when remote media cannot be fetched locally."""


@dataclass
class FetchedMedia:
    title: str | None
    duration_seconds: int | None
    local_path: str
    extractor: str | None
    source_id: str | None


class MediaFetcher(Protocol):
    def fetch(self, job: TranscriptJob) -> FetchedMedia:
        """Fetch media for a job and return local artifact details."""


class YtDlpMediaFetcher:
    def __init__(self, settings: Settings) -> None:
        self.media_dir = Path(settings.media_dir or Path(settings.data_dir) / "media")
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, job: TranscriptJob) -> FetchedMedia:
        output_template = str(self.media_dir / job.id / "%(id)s.%(ext)s")
        Path(output_template).parent.mkdir(parents=True, exist_ok=True)
        options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_template,
        }

        logger.info("fetcher.start job_id=%s url=%s", job.id, job.normalized_url)
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(job.normalized_url, download=True)
                resolved = self._resolve_info(info)
                prepared_path = downloader.prepare_filename(resolved)
        except Exception as exc:  # pragma: no cover - exercised via service tests with stubs
            raise MediaFetchError(str(exc)) from exc

        media = FetchedMedia(
            title=resolved.get("title"),
            duration_seconds=resolved.get("duration"),
            local_path=prepared_path,
            extractor=resolved.get("extractor_key") or resolved.get("extractor"),
            source_id=resolved.get("id"),
        )
        logger.info("fetcher.complete job_id=%s path=%s", job.id, media.local_path)
        return media

    @staticmethod
    def _resolve_info(info: dict) -> dict:
        if "entries" in info:
            entries = info.get("entries") or []
            if not entries:
                raise MediaFetchError("No downloadable media entries were found")
            return entries[0]
        return info
