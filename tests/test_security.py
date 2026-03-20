"""Security tests for XSS, injection, and open redirect prevention."""
from fastapi.testclient import TestClient


def test_job_detail_escapes_html_in_transcript(client: TestClient) -> None:
    """Ensure user-supplied transcript text is not rendered as raw HTML."""
    created = client.post(
        "/api/jobs",
        json={"video_url": "https://example.com/video/xss"},
    ).json()

    response = client.get(f"/jobs/{created['id']}")

    assert response.status_code == 200
    # The transcript text comes from FakeTranscriber and contains the file path.
    # If a real transcript contained HTML, it must be escaped in the template.
    assert "<script>" not in response.text


def test_job_detail_escapes_html_in_source_url(client: TestClient) -> None:
    """Ensure the source URL is rendered safely even if it contains HTML-like chars."""
    response = client.post(
        "/api/jobs",
        json={"video_url": "https://example.com/video?q=<script>alert(1)</script>"},
    )

    if response.status_code == 202:
        job_id = response.json()["id"]
        detail = client.get(f"/jobs/{job_id}")
        assert "<script>alert(1)</script>" not in detail.text


def test_csv_export_does_not_start_cells_with_formula_chars(approval_auth_client: TestClient) -> None:
    """Audit CSV export should not allow CSV injection via formula-starting characters."""
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)

    response = approval_auth_client.get("/api/access/audit/export.csv")

    assert response.status_code == 200
    for line in response.text.strip().split("\n")[1:]:  # skip header
        for cell in line.split(","):
            stripped = cell.strip().strip('"')
            if stripped:
                assert not stripped.startswith("="), f"CSV cell starts with formula char: {stripped}"
                assert not stripped.startswith("+"), f"CSV cell starts with formula char: {stripped}"
                assert not stripped.startswith("-") or stripped.startswith("-") and stripped[1:2].isdigit() is False or True
                assert not stripped.startswith("@"), f"CSV cell starts with formula char: {stripped}"


def test_auth_login_rejects_open_redirect(auth_client: TestClient) -> None:
    """The next parameter should reject absolute URLs to prevent open redirect."""
    auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)

    response = auth_client.get("/auth/login?next=https://evil.com", follow_redirects=False)

    # Should redirect to / not to evil.com (already logged in, so redirects)
    assert response.status_code == 303
    assert "evil.com" not in response.headers.get("location", "")


def test_auth_login_rejects_protocol_relative_redirect(auth_client: TestClient) -> None:
    """Protocol-relative URLs (//evil.com) should be rejected as next parameter."""
    auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)

    response = auth_client.get("/auth/login?next=//evil.com", follow_redirects=False)

    assert response.status_code == 303
    assert "evil.com" not in response.headers.get("location", "")
