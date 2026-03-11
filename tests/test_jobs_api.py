from fastapi.testclient import TestClient


def test_create_job_persists_and_returns_metadata(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={"video_url": "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["provider"] == "linkedin"
    assert body["source_domain"] == "www.linkedin.com"
    assert body["normalized_url"].startswith("https://www.linkedin.com/")
    assert body["id"]


def test_list_jobs_returns_most_recent_first(client: TestClient) -> None:
    first = client.post("/api/jobs", json={"video_url": "https://example.com/video/1"}).json()
    second = client.post("/api/jobs", json={"video_url": "https://example.com/video/2"}).json()

    response = client.get("/api/jobs")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == second["id"]
    assert body[1]["id"] == first["id"]


def test_get_missing_job_returns_404(client: TestClient) -> None:
    response = client.get("/api/jobs/missing-job-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_create_job_rejects_invalid_url(client: TestClient) -> None:
    response = client.post("/api/jobs", json={"video_url": "linkedin.com/not-absolute"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Only absolute http(s) video URLs are supported"}
