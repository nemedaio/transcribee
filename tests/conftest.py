from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.main import create_app


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        log_level="DEBUG",
    )
    app = create_app(settings)

    with TestClient(app) as test_client:
        yield test_client
