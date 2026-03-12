from fastapi.testclient import TestClient


def test_api_requires_authentication_when_google_auth_is_enabled(auth_client: TestClient) -> None:
    response = auth_client.get("/api/jobs")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_api_accepts_authenticated_requests_when_google_auth_is_enabled(auth_client: TestClient) -> None:
    auth_client.get("/auth/test-login?email=owner@twyd.ai&next=/api/jobs")

    response = auth_client.post("/api/jobs", json={"video_url": "https://example.com/video/1"})

    assert response.status_code == 202
    assert response.json()["status"] == "completed"


def test_access_accounts_api_requires_admin(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post(
        "/api/access/accounts/member@twyd.ai/approve",
        json={"role": "member"},
    )
    approval_auth_client.get("/auth/logout", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)

    response = approval_auth_client.get("/api/access/accounts")

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required"}


def test_admin_can_list_pending_access_accounts_via_api(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)

    response = approval_auth_client.get("/api/access/accounts?status=pending")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["email"] == "member@twyd.ai"
    assert response.json()[0]["status"] == "pending"


def test_admin_can_approve_access_account_via_api(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)

    response = approval_auth_client.post(
        "/api/access/accounts/member@twyd.ai/approve",
        json={"role": "member"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "member@twyd.ai"
    assert response.json()["status"] == "approved"
    assert response.json()["role"] == "member"
    assert response.json()["approved_by_email"] == "owner@twyd.ai"


def test_admin_can_revoke_access_account_via_api(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post(
        "/api/access/accounts/member@twyd.ai/approve",
        json={"role": "member"},
    )

    response = approval_auth_client.post("/api/access/accounts/member@twyd.ai/revoke")

    assert response.status_code == 200
    assert response.json()["email"] == "member@twyd.ai"
    assert response.json()["status"] == "revoked"
    assert response.json()["role"] == "member"


def test_revoking_unknown_access_account_returns_404(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)

    response = approval_auth_client.post("/api/access/accounts/missing@twyd.ai/revoke")

    assert response.status_code == 404
    assert response.json() == {"detail": "Access account not found"}


def test_admin_can_list_access_audit_events_via_api(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post(
        "/api/access/accounts/member@twyd.ai/approve",
        json={"role": "member"},
    )
    approval_auth_client.post("/api/access/accounts/member@twyd.ai/revoke")

    response = approval_auth_client.get("/api/access/audit?account_email=member@twyd.ai")

    assert response.status_code == 200
    actions = [event["action"] for event in response.json()]
    assert "requested" in actions
    assert "granted" in actions
    assert "revoked" in actions
    revoked_event = next(event for event in response.json() if event["action"] == "revoked")
    assert revoked_event["actor_email"] == "owner@twyd.ai"


def test_admin_can_filter_access_audit_events_via_api(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post(
        "/api/access/accounts/member@twyd.ai/approve",
        json={"role": "member"},
    )
    approval_auth_client.post("/api/access/accounts/member@twyd.ai/revoke")

    response = approval_auth_client.get("/api/access/audit?action=revoked&search=owner")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["action"] == "revoked"
    assert response.json()[0]["actor_email"] == "owner@twyd.ai"


def test_admin_can_export_access_audit_events_as_csv(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post(
        "/api/access/accounts/member@twyd.ai/approve",
        json={"role": "member"},
    )

    response = approval_auth_client.get("/api/access/audit/export.csv?action=granted")

    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('"access-audit.csv"')
    assert "account_email,action,actor_email" in response.text
    assert "member@twyd.ai,granted,owner@twyd.ai" in response.text


def test_access_audit_api_requires_admin(approval_auth_client: TestClient) -> None:
    approval_auth_client.get("/auth/test-login?email=owner@twyd.ai", follow_redirects=False)
    approval_auth_client.post(
        "/api/access/accounts/member@twyd.ai/approve",
        json={"role": "member"},
    )
    approval_auth_client.get("/auth/logout", follow_redirects=False)
    approval_auth_client.get("/auth/test-login?email=member@twyd.ai", follow_redirects=False)

    response = approval_auth_client.get("/api/access/audit")

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required"}


def test_create_job_persists_and_returns_metadata(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={"video_url": "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "completed"
    assert body["provider"] == "linkedin"
    assert body["source_domain"] == "www.linkedin.com"
    assert body["normalized_url"].startswith("https://www.linkedin.com/")
    assert body["media_title"] == "Test media title"
    assert body["source_media_path"] is None
    assert body["media_duration_seconds"] == 83
    assert body["media_file_path"].endswith(".wav")
    assert body["extractor_name"] == "fake"
    assert body["transcript_text"].endswith(".wav")
    assert body["transcript_language"] == "en"
    assert body["transcript_segment_count"] == 2
    assert body["fetch_started_at"] is not None
    assert body["fetch_completed_at"] is not None
    assert body["audio_prepared_at"] is not None
    assert body["transcription_started_at"] is not None
    assert body["transcription_completed_at"] is not None
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


def test_fetch_failure_is_persisted(fetch_failing_client: TestClient) -> None:
    response = fetch_failing_client.post("/api/jobs", json={"video_url": "https://example.com/video/1"})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "failed"
    assert body["last_error"] == "download failed"
    assert body["source_media_path"] is None
    assert body["media_file_path"] is None
    assert body["fetch_started_at"] is not None
    assert body["fetch_completed_at"] is not None
    assert body["audio_prepared_at"] is None
    assert body["transcription_started_at"] is None
    assert body["transcription_completed_at"] is None


def test_transcription_failure_is_persisted(transcription_failing_client: TestClient) -> None:
    response = transcription_failing_client.post("/api/jobs", json={"video_url": "https://example.com/video/1"})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "failed"
    assert body["last_error"] == "transcription failed"
    assert body["source_media_path"] is None
    assert body["media_file_path"] is not None
    assert body["transcript_text"] is None
    assert body["fetch_started_at"] is not None
    assert body["fetch_completed_at"] is not None
    assert body["audio_prepared_at"] is not None
    assert body["transcription_started_at"] is not None
    assert body["transcription_completed_at"] is not None


def test_audio_extraction_failure_is_persisted(audio_failing_client: TestClient) -> None:
    response = audio_failing_client.post("/api/jobs", json={"video_url": "https://example.com/video/1"})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "failed"
    assert body["last_error"] == "audio extraction failed"
    assert body["source_media_path"] is not None
    assert body["media_file_path"] is None
    assert body["audio_prepared_at"] is None
    assert body["transcription_started_at"] is None


def test_get_missing_job_returns_404(client: TestClient) -> None:
    response = client.get("/api/jobs/missing-job-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_create_job_rejects_invalid_url(client: TestClient) -> None:
    response = client.post("/api/jobs", json={"video_url": "linkedin.com/not-absolute"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Only absolute http(s) video URLs are supported"}


def test_export_txt_returns_transcript_download(client: TestClient) -> None:
    created = client.post("/api/jobs", json={"video_url": "https://example.com/video/1"}).json()

    response = client.get(f"/jobs/{created['id']}/exports/txt")

    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('.txt"')
    assert created["transcript_text"] == response.text


def test_export_srt_returns_segment_timestamps(client: TestClient) -> None:
    created = client.post("/api/jobs", json={"video_url": "https://example.com/video/1"}).json()

    response = client.get(f"/jobs/{created['id']}/exports/srt")

    assert response.status_code == 200
    assert "00:00:00,000 --> 00:00:01,200" in response.text
    assert "Transcript" in response.text


def test_export_rejects_incomplete_transcript(transcription_failing_client: TestClient) -> None:
    created = transcription_failing_client.post(
        "/api/jobs",
        json={"video_url": "https://example.com/video/1"},
    ).json()

    response = transcription_failing_client.get(f"/jobs/{created['id']}/exports/txt")

    assert response.status_code == 409
    assert response.json() == {"detail": "Transcript is not available for export yet"}


def test_queued_job_can_be_completed_later(queued_client: TestClient) -> None:
    response = queued_client.post("/api/jobs", json={"video_url": "https://example.com/video/1"})

    assert response.status_code == 202
    queued_job = response.json()
    assert queued_job["status"] == "queued"

    queued_client.app.state.job_runner.run_all()

    refreshed = queued_client.get(f"/api/jobs/{queued_job['id']}")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "completed"


def test_linkedin_url_is_normalized_without_tracking_noise(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={
            "video_url": "https://es.linkedin.com/feed/update/urn:li:activity:1234567890/?trk=public_post&lipi=abc#fragment"
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["provider"] == "linkedin"
    assert body["normalized_url"] == "https://www.linkedin.com/feed/update/urn:li:activity:1234567890"


def test_linkedin_company_posts_url_is_allowed(client: TestClient) -> None:
    response = client.post(
        "/api/jobs",
        json={"video_url": "https://www.linkedin.com/company/openai/posts/?feedView=all&trk=public_post_share"},
    )

    assert response.status_code == 202
    assert response.json()["normalized_url"] == "https://www.linkedin.com/company/openai/posts"


def test_linkedin_profile_url_is_rejected(client: TestClient) -> None:
    response = client.post("/api/jobs", json={"video_url": "https://www.linkedin.com/in/example-person/"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "LinkedIn ingestion currently supports post and video URLs, not profile or directory pages"
    }


def test_dashboard_counts_reflect_queued_completed_and_failed_jobs(queued_client: TestClient) -> None:
    queued_client.post("/api/jobs", json={"video_url": "https://example.com/completed"})
    queued_client.app.state.job_runner.run_all()

    queued_client.app.state.media_transcriber.should_fail = True
    queued_client.post("/api/jobs", json={"video_url": "https://example.com/failed"})
    queued_client.app.state.job_runner.run_all()

    queued_client.app.state.media_transcriber.should_fail = False
    queued_client.post("/api/jobs", json={"video_url": "https://example.com/queued"})

    response = queued_client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "queued": 1,
        "fetching": 0,
        "transcribing": 0,
        "completed": 1,
        "failed": 1,
        "total": 3,
    }


def test_retry_failed_job_requeues_and_completes(queued_client: TestClient) -> None:
    queued_client.app.state.media_transcriber.should_fail = True
    created = queued_client.post("/api/jobs", json={"video_url": "https://example.com/retry"}).json()
    queued_client.app.state.job_runner.run_all()

    failed = queued_client.get(f"/api/jobs/{created['id']}").json()
    assert failed["status"] == "failed"

    queued_client.app.state.media_transcriber.should_fail = False
    response = queued_client.post(f"/api/jobs/{created['id']}/retry")

    assert response.status_code == 202
    retried = response.json()
    assert retried["status"] == "queued"
    assert retried["retry_count"] == 1
    assert retried["source_media_path"] is None
    assert retried["media_file_path"] is None
    assert retried["transcript_text"] is None

    queued_client.app.state.job_runner.run_all()
    completed = queued_client.get(f"/api/jobs/{created['id']}").json()
    assert completed["status"] == "completed"
    assert completed["retry_count"] == 1


def test_retry_non_failed_job_is_rejected(queued_client: TestClient) -> None:
    created = queued_client.post("/api/jobs", json={"video_url": "https://example.com/queued"}).json()

    response = queued_client.post(f"/api/jobs/{created['id']}/retry")

    assert response.status_code == 409
    assert response.json() == {"detail": "Only failed jobs can be retried"}


def test_cleanup_artifacts_clears_finished_job_files(cleanup_client: TestClient) -> None:
    created = cleanup_client.post("/api/jobs", json={"video_url": "https://example.com/cleanup"}).json()

    response = cleanup_client.post("/api/maintenance/cleanup-artifacts")

    assert response.status_code == 200
    assert response.json()["jobs_cleaned"] == 1
    assert response.json()["files_deleted"] >= 1

    refreshed = cleanup_client.get(f"/api/jobs/{created['id']}").json()
    assert refreshed["media_file_path"] is None
    assert refreshed["artifacts_cleaned_at"] is not None
