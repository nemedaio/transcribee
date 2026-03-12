from collections.abc import Generator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.main import create_app
from lnkdn_transcripts.services.fetcher import FetchedMedia, MediaFetchError
from lnkdn_transcripts.services.transcriber import TranscriptSegment, TranscriptionError, TranscriptionResult
from lnkdn_transcripts.storage.models import TranscriptJob


@dataclass
class FakeMediaFetcher:
    should_fail: bool = False

    def fetch(self, job: TranscriptJob) -> FetchedMedia:
        if self.should_fail:
            raise MediaFetchError("download failed")
        return FetchedMedia(
            title="Test media title",
            duration_seconds=83,
            local_path=f"/tmp/{job.id}.m4a",
            extractor="fake",
            source_id="media-123",
        )


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
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(),
        media_transcriber=FakeTranscriber(),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fetch_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(should_fail=True),
        media_transcriber=FakeTranscriber(),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def transcription_failing_client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        media_dir=str(tmp_path / "media"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        log_level="DEBUG",
    )
    app = create_app(
        settings,
        media_fetcher=FakeMediaFetcher(),
        media_transcriber=FakeTranscriber(should_fail=True),
    )

    with TestClient(app) as test_client:
        yield test_client
