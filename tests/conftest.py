from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from transcribee.config import Settings
from transcribee.services.audio import AudioPreparationError, PreparedAudio
from transcribee.main import create_app
from transcribee.services.background_jobs import InlineJobRunner, JobRunner, ManualJobRunner
from transcribee.services.fetcher import FetchedMedia, MediaFetchError
from transcribee.services.transcriber import TranscriptSegment, TranscriptionError, TranscriptionResult
from transcribee.storage.models import TranscriptJob


@dataclass
class FakeMediaFetcher:
    base_dir: Path
    should_fail: bool = False

    def fetch(self, job: TranscriptJob) -> FetchedMedia:
        if self.should_fail:
            raise MediaFetchError("download failed")
        source_path = self.base_dir / job.id / "download.mp4"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("fake-media", encoding="utf-8")
        return FetchedMedia(
            title="Test media title",
            duration_seconds=83,
            local_path=str(source_path),
            extractor="fake",
            source_id="media-123",
        )


@dataclass
class FakeAudioPreparer:
    should_fail: bool = False

    def prepare(self, source_media_path: str) -> PreparedAudio:
        if self.should_fail:
            raise AudioPreparationError("audio extraction failed")
        source_path = Path(source_media_path)
        audio_path = source_path.with_suffix(".wav")
        audio_path.write_text("fake-audio", encoding="utf-8")
        return PreparedAudio(local_path=str(audio_path))


@dataclass
class FakeTranscriber:
    should_fail: bool = False

    def transcribe(self, media_file_path: str) -> TranscriptionResult:
        if self.should_fail:
            raise TranscriptionError("transcription failed")
        return TranscriptionResult(
            text=f"Transcript for {media_file_path}",
            language="en",
            segments=[
                TranscriptSegment(start_seconds=0.0, end_seconds=1.2, text="Transcript"),
                TranscriptSegment(start_seconds=1.2, end_seconds=2.8, text=f"for {media_file_path}"),
            ],
        )


def _build_test_client(
    tmp_path: Path,
    *,
    fetcher_fail: bool = False,
    audio_fail: bool = False,
    transcriber_fail: bool = False,
    runner_factory: Callable[[Callable[[str], None]], JobRunner] | None = None,
    **settings_overrides,
) -> TestClient:
    base_settings = dict(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_source_media=False,
        log_level="DEBUG",
    )
    base_settings.update(settings_overrides)
    app = create_app(
        Settings(**base_settings),
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media", should_fail=fetcher_fail),
        audio_preparer=FakeAudioPreparer(should_fail=audio_fail),
        media_transcriber=FakeTranscriber(should_fail=transcriber_fail),
        job_runner_factory=runner_factory or (lambda processor: InlineJobRunner(processor)),
    )
    return TestClient(app)


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(tmp_path) as test_client:
        yield test_client


@pytest.fixture
def fetch_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(tmp_path, fetcher_fail=True) as test_client:
        yield test_client


@pytest.fixture
def transcription_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(tmp_path, transcriber_fail=True) as test_client:
        yield test_client


@pytest.fixture
def queued_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(
        tmp_path, runner_factory=lambda processor: ManualJobRunner(processor)
    ) as test_client:
        yield test_client


@pytest.fixture
def cleanup_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(tmp_path, artifact_retention_days=0) as test_client:
        yield test_client


@pytest.fixture
def audio_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(tmp_path, audio_fail=True) as test_client:
        yield test_client


_AUTH_SETTINGS = dict(
    auth_enabled=True,
    auth_test_mode=True,
    session_secret_key="test-session-secret",
    google_client_id="test-google-client-id",
    google_client_secret="test-google-client-secret",
)


@pytest.fixture
def auth_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(tmp_path, **_AUTH_SETTINGS) as test_client:
        yield test_client


@pytest.fixture
def restricted_auth_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(
        tmp_path, **_AUTH_SETTINGS, google_allowed_email_domains="twyd.ai"
    ) as test_client:
        yield test_client


_APPROVAL_SETTINGS = dict(
    **_AUTH_SETTINGS,
    google_allowed_email_domains="twyd.ai",
    google_admin_emails="owner@twyd.ai",
    google_require_approval=True,
)


@pytest.fixture
def approval_auth_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(tmp_path, **_APPROVAL_SETTINGS) as test_client:
        yield test_client


@pytest.fixture
def audit_cleanup_client(tmp_path) -> Generator[TestClient, None, None]:
    with _build_test_client(
        tmp_path, **_APPROVAL_SETTINGS, access_audit_retention_days=0
    ) as test_client:
        yield test_client
