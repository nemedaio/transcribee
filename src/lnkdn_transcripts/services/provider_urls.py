from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from lnkdn_transcripts.logging import get_logger

logger = get_logger(__name__)


class InvalidVideoUrlError(ValueError):
    """Raised when a submitted URL is not suitable for a transcription job."""


@dataclass
class NormalizedVideoUrl:
    source_url: str
    normalized_url: str
    source_domain: str
    provider: str


class VideoUrlNormalizer:
    LINKEDIN_SUPPORTED_PREFIXES = (
        "/feed/update/",
        "/posts/",
        "/video/",
        "/embed/feed/update/",
        "/pulse/",
    )
    LINKEDIN_REJECTED_PREFIXES = (
        "/in/",
        "/pub/",
        "/jobs/",
        "/search/",
        "/school/",
        "/groups/",
        "/events/",
        "/learning/",
    )

    def normalize(self, raw_url: str) -> NormalizedVideoUrl:
        cleaned_url = raw_url.strip()
        parsed = urlsplit(cleaned_url)
        source_domain = parsed.netloc.lower()

        if parsed.scheme not in {"http", "https"} or not source_domain:
            logger.warning("providers.invalid_url submitted=%r", raw_url)
            raise InvalidVideoUrlError("Only absolute http(s) video URLs are supported")

        if source_domain.endswith("linkedin.com"):
            return self._normalize_linkedin(cleaned_url, parsed)

        normalized_url = urlunsplit((parsed.scheme, source_domain, self._clean_path(parsed.path), parsed.query, ""))
        return NormalizedVideoUrl(
            source_url=cleaned_url,
            normalized_url=normalized_url,
            source_domain=source_domain,
            provider="generic",
        )

    def _normalize_linkedin(self, source_url: str, parsed) -> NormalizedVideoUrl:
        cleaned_path = self._clean_path(parsed.path)

        if any(cleaned_path.startswith(prefix) for prefix in self.LINKEDIN_REJECTED_PREFIXES):
            raise InvalidVideoUrlError(
                "LinkedIn ingestion currently supports post and video URLs, not profile or directory pages"
            )

        if not self._is_supported_linkedin_path(cleaned_path):
            raise InvalidVideoUrlError(
                "LinkedIn ingestion currently supports feed updates, posts, company posts, pulse articles, and video URLs"
            )

        normalized_url = urlunsplit((parsed.scheme, "www.linkedin.com", cleaned_path, "", ""))
        logger.info("providers.linkedin_normalized url=%s normalized=%s", source_url, normalized_url)
        return NormalizedVideoUrl(
            source_url=source_url,
            normalized_url=normalized_url,
            source_domain="www.linkedin.com",
            provider="linkedin",
        )

    def _is_supported_linkedin_path(self, cleaned_path: str) -> bool:
        if any(cleaned_path.startswith(prefix) for prefix in self.LINKEDIN_SUPPORTED_PREFIXES):
            return True
        return cleaned_path.startswith("/company/") and "/posts" in cleaned_path

    @staticmethod
    def _clean_path(path: str) -> str:
        stripped = (path or "/").rstrip("/")
        return stripped or "/"
