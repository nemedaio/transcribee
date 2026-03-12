from fastapi.testclient import TestClient


def test_form_submission_redirects_to_job_page(client: TestClient) -> None:
    response = client.post(
        "/jobs",
        data={"video_url": "https://www.linkedin.com/posts/example-video"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/jobs/")


def test_job_page_renders_created_job(client: TestClient) -> None:
    created = client.post(
        "/api/jobs",
        json={"video_url": "https://example.com/watch?v=42#fragment"},
    ).json()

    response = client.get(f"/jobs/{created['id']}")

    assert response.status_code == 200
    assert created["id"] in response.text
    assert "completed" in response.text
    assert "https://example.com/watch?v=42" in response.text
    assert "Test media title" in response.text
    assert created["media_file_path"] in response.text
    assert created["transcript_text"] in response.text
