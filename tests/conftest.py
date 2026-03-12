from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.services.audio import AudioPreparationError, PreparedAudio
from lnkdn_transcripts.main import create_app
from lnkdn_transcripts.services.background_jobs import InlineJobRunner, ManualJobRunner
from lnkdn_transcripts.services.fetcher import FetchedMedia, MediaFetchError
from lnkdn_transcripts.services.transcriber import TranscriptSegment, TranscriptionError, TranscriptionResult
from lnkdn_transcripts.storage.models import TranscriptJob


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


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_source_media=False,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media"),
        audio_preparer=FakeAudioPreparer(),
        media_transcriber=FakeTranscriber(),
        job_runner_factory=lambda processor: InlineJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fetch_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_source_media=False,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media", should_fail=True),
        audio_preparer=FakeAudioPreparer(),
        media_transcriber=FakeTranscriber(),
        job_runner_factory=lambda processor: InlineJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def transcription_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_source_media=False,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media"),
        audio_preparer=FakeAudioPreparer(),
        media_transcriber=FakeTranscriber(should_fail=True),
        job_runner_factory=lambda processor: InlineJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def queued_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_source_media=False,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media"),
        audio_preparer=FakeAudioPreparer(),
        media_transcriber=FakeTranscriber(),
        job_runner_factory=lambda processor: ManualJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def cleanup_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_source_media=False,
        artifact_retention_days=0,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media"),
        audio_preparer=FakeAudioPreparer(),
        media_transcriber=FakeTranscriber(),
        job_runner_factory=lambda processor: InlineJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def audio_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        retain_source_media=False,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media"),
        audio_preparer=FakeAudioPreparer(should_fail=True),
        media_transcriber=FakeTranscriber(),
        job_runner_factory=lambda processor: InlineJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        auth_enabled=True,
        auth_test_mode=True,
        session_secret_key="test-session-secret",
        google_client_id="test-google-client-id",
        google_client_secret="test-google-client-secret",
        retain_source_media=False,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media"),
        audio_preparer=FakeAudioPreparer(),
        media_transcriber=FakeTranscriber(),
        job_runner_factory=lambda processor: InlineJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def restricted_auth_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        auth_enabled=True,
        auth_test_mode=True,
        session_secret_key="test-session-secret",
        google_client_id="test-google-client-id",
        google_client_secret="test-google-client-secret",
        google_allowed_email_domains="twyd.ai",
        retain_source_media=False,
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(base_dir=tmp_path / "media"),
        audio_preparer=FakeAudioPreparer(),
        media_transcriber=FakeTranscriber(),
        job_runner_factory=lambda processor: InlineJobRunner(processor),
    )

    with TestClient(app) as test_client:
        yield test_client
