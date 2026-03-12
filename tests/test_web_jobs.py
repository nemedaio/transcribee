from fastapi.testclient import TestClient


def test_login_page_renders_google_sign_in(auth_client: TestClient) -> None:
    response = auth_client.get("/auth/login")

    assert response.status_code == 200
    assert "Continue with Google" in response.text


def test_protected_web_route_redirects_to_login_when_auth_is_enabled(auth_client: TestClient) -> None:
    response = auth_client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login?next=%2F"


def test_google_test_login_creates_session_for_dashboard(auth_client: TestClient) -> None:
    response = auth_client.get(
        "/auth/test-login?email=owner@twyd.ai&next=/dashboard",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "owner@twyd.ai" in response.text
    assert "Job Dashboard" in response.text


def test_logout_clears_google_auth_session(auth_client: TestClient) -> None:
    auth_client.get("/auth/test-login?email=owner@twyd.ai&next=/dashboard", follow_redirects=True)

    logout_response = auth_client.get("/auth/logout", follow_redirects=False)
    redirected = auth_client.get("/dashboard", follow_redirects=False)

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/auth/login"
    assert redirected.status_code == 303
    assert redirected.headers["location"] == "/auth/login?next=%2Fdashboard"


def test_restricted_google_domain_is_rejected(restricted_auth_client: TestClient) -> None:
    response = restricted_auth_client.get("/auth/test-login?email=owner@example.com", follow_redirects=False)

    assert response.status_code == 403
    assert response.json() == {"detail": "Only Google accounts from twyd.ai can sign in"}


def test_unapproved_google_user_creates_pending_request(approval_auth_client: TestClient) -> None:
    response = approval_auth_client.get(
        "/auth/test-login?email=member@twyd.ai&next=/dashboard",
        follow_redirects=False,
    )

    requested_account = approval_auth_client.app.state.access_repository.get_account("member@twyd.ai")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Access request submitted. An admin needs to approve your account."
    }
    assert requested_account is not None
    assert requested_account.status.value == "pending"


def test_admin_can_approve_pending_google_user(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)

    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai&next=/auth/access", follow_redirects=True)
    access_page = approval_auth_client.get("/auth/access")
    approve_response = approval_auth_client.post(
        "/auth/access/approve",
        data={"email": "member@twyd.ai", "role": "member"},
        follow_redirects=False,
    )
    approval_auth_client.get("/auth/logout", follow_redirects=False)

    member_login = approval_auth_client.get(
        "/auth/test-login?email=member@twyd.ai&next=/dashboard",
        follow_redirects=False,
    )
    dashboard = approval_auth_client.get("/dashboard")

    assert access_page.status_code == 200
    assert "member@twyd.ai" in access_page.text
    assert approve_response.status_code == 303
    assert member_login.status_code == 303
    assert member_login.headers["location"] == "/dashboard"
    assert dashboard.status_code == 200
    assert "Job Dashboard" in dashboard.text


def test_admin_can_revoke_google_user_access(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post("/auth/access/approve", data={"email": "member@twyd.ai", "role": "member"})
    approval_auth_client.post("/auth/access/revoke", data={"email": "member@twyd.ai"}, follow_redirects=False)
    approval_auth_client.get("/auth/logout", follow_redirects=False)

    response = approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)

    assert response.status_code == 403
    assert response.json() == {"detail": "Your access has been revoked. Contact an administrator."}


def test_member_cannot_open_access_admin_page(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post("/auth/access/approve", data={"email": "member@twyd.ai", "role": "member"})
    approval_auth_client.get("/auth/logout", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)

    response = approval_auth_client.get("/auth/access")

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required"}


def test_access_admin_page_renders_recent_audit_events(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post("/auth/access/approve", data={"email": "member@twyd.ai", "role": "member"})

    response = approval_auth_client.get("/auth/access")

    assert response.status_code == 200
    assert "Recent audit events" in response.text
    assert "member@twyd.ai" in response.text


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
    assert "Not retained" in response.text


def test_history_page_renders_recent_jobs_and_export_links(client: TestClient) -> None:
    client.post("/api/jobs", json={"video_url": "https://example.com/video/1"})

    response = client.get("/history")

    assert response.status_code == 200
    assert "Transcript History" in response.text
    assert "TXT" in response.text
    assert "SRT" in response.text


def test_dashboard_page_renders_counts_and_retry_controls(queued_client: TestClient) -> None:
    queued_client.post("/api/jobs", json={"video_url": "https://example.com/completed"})
    queued_client.app.state.job_runner.run_all()

    queued_client.app.state.media_transcriber.should_fail = True
    queued_client.post("/api/jobs", json={"video_url": "https://example.com/failed"})
    queued_client.app.state.job_runner.run_all()

    queued_client.app.state.media_transcriber.should_fail = False
    queued_client.post("/api/jobs", json={"video_url": "https://example.com/queued"})

    response = queued_client.get("/dashboard")

    assert response.status_code == 200
    assert "Job Dashboard" in response.text
    assert "Retry job" in response.text
    assert "Queued" in response.text
    assert "Completed" in response.text


def test_dashboard_page_renders_cleanup_control(cleanup_client: TestClient) -> None:
    cleanup_client.post("/api/jobs", json={"video_url": "https://example.com/video/1"})

    response = cleanup_client.get("/dashboard")

    assert response.status_code == 200
    assert "Run cleanup" in response.text
