# LinkedIn Transcript App

Local-first web app for turning a pasted video URL into a transcript using a Whisper-style transcription engine.

## Why this structure

The fastest route to a working MVP is a Python application that handles all three hard parts in one place:

- URL intake and validation
- media download and audio extraction
- local transcription and transcript export

That keeps the first version easy to run on one machine and avoids introducing a separate frontend or queue system before they are needed.

## Planned flow

1. User pastes a LinkedIn or other supported video URL.
2. The app creates a transcription job.
3. A worker downloads the media and extracts audio.
4. `faster-whisper` produces timestamped text.
5. The UI shows progress and exposes transcript output.

## Repository layout

```text
docs/                         Architecture, roadmap, branch strategy
src/lnkdn_transcripts/        Application code
src/lnkdn_transcripts/routes/ HTTP routes
src/lnkdn_transcripts/storage/ Persistence layer
src/lnkdn_transcripts/services/
src/lnkdn_transcripts/templates/
src/lnkdn_transcripts/static/
tests/                        Test suite
```

Detailed notes live in [`docs/architecture.md`](./docs/architecture.md) and [`docs/branching.md`](./docs/branching.md).

## MVP stack

- FastAPI for the web server and API
- Jinja templates for a minimal UI
- `yt-dlp` for media retrieval
- `ffmpeg` for audio extraction
- `faster-whisper` for local transcription
- SQLite for job and transcript metadata

## Local setup

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn lnkdn_transcripts.main:app --reload
```

The app expects Python 3.10+ and `ffmpeg` to be installed on the host machine. The current branch was verified with Python 3.12 on macOS.

### Google auth setup

Google account auth is optional and disabled by default. When enabled, the web app and JSON API require a signed-in Google session.

Set these environment variables before starting the app:

```bash
AUTH_ENABLED=true
SESSION_SECRET_KEY=replace-this-with-a-long-random-string
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
```

Optional hardening:

```bash
GOOGLE_ALLOWED_EMAIL_DOMAINS=twyd.ai
GOOGLE_ALLOWED_EMAILS=member@twyd.ai,ops@twyd.ai
GOOGLE_ADMIN_EMAILS=owner@twyd.ai
GOOGLE_REQUIRE_APPROVAL=true
SESSION_HTTPS_ONLY=true
```

Configure the Google OAuth redirect URI as:

```text
http://localhost:8000/auth/callback
```

With auth enabled:

- browser requests redirect to `/auth/login`
- API requests return `401 {"detail": "Authentication required"}`
- signed-in users can log out from the top navigation
- access can be limited to one or more Google Workspace domains
- access can also require admin approval, with bootstrap admins defined in environment config
- approved, pending, and revoked accounts are stored in SQLite for review

## Current branch status

`codex/access-audit-log` extends the persistent workflow:

- submit one video URL
- store a transcription job in SQLite
- fetch media locally with `yt-dlp`
- extract transcription-ready audio locally with `ffmpeg`
- transcribe fetched media locally with `faster-whisper`
- persist fetched artifact metadata, transcript output, segment timings, and processing errors
- download completed transcripts as TXT, Markdown, SRT, and VTT
- browse recent jobs from a dedicated history page
- queue submitted jobs for background processing instead of blocking the request
- normalize LinkedIn URLs more aggressively and reject non-post/non-video LinkedIn pages with clearer errors
- expose a dashboard with live status counts and dedicated active/failed/completed sections
- retry failed jobs from the dashboard, history page, or job detail page
- clean up raw downloaded media after audio extraction when configured
- run retention cleanup for old finished-job artifacts from the dashboard or API
- protect the app and API behind optional Google account sign-in
- support optional allowed-domain checks for Google Workspace accounts
- store pending, approved, and revoked Google accounts in SQLite
- expose an admin-only access page for approval and revocation
- expose admin-only JSON endpoints for listing, approving, and revoking access accounts
- store an audit trail for access requests, grants, sign-ins, and revocations
- fetch job status over JSON
- show transcript output in the browser

Jobs now move through the first full in-process lifecycle:

- `queued`
- `fetching`
- `fetched`
- `transcribing`
- `completed`
- `failed`

## Logging

The app emits structured-enough application logs with timestamps, logger name, and a clear event message for:

- app startup
- database initialization
- job creation
- fetch start and success
- fetch failures
- transcription start and success
- transcription failures
- job lookup failures

This is intentionally simple for local development and easy terminal debugging.

Additional auth events are logged for:

- unauthenticated route access
- Google login start and success
- rejected Google accounts
- pending access requests
- access approvals and revocations
- access audit events for requests, grants, sign-ins, and revocations
- logout and test-mode login

## API snapshot

```text
GET  /health
GET  /auth/login
GET  /auth/google
GET  /auth/callback
GET  /auth/logout
GET  /auth/access
POST /auth/access/approve
POST /auth/access/revoke
GET  /
GET  /dashboard
POST /jobs
POST /jobs/{job_id}/retry
POST /dashboard/cleanup
GET  /jobs/{job_id}
POST /api/jobs
GET  /api/dashboard
POST /api/jobs/{job_id}/retry
POST /api/maintenance/cleanup-artifacts
GET  /api/jobs/{job_id}
GET  /api/jobs
GET  /api/access/accounts
GET  /api/access/audit
POST /api/access/accounts/{account_email}/approve
POST /api/access/accounts/{account_email}/revoke
```

## Tests

Current automated coverage focuses on the first backend contract plus fetch and transcription behavior:

- healthcheck
- job creation through the JSON API
- successful fetch processing with persisted metadata
- successful transcription processing with persisted transcript output
- fetch failure persistence
- transcription failure persistence
- transcript export endpoints
- history page rendering
- queued job submission and later completion through the background runner
- LinkedIn-specific normalization and validation rules
- dashboard status counts and retry flow
- ffmpeg-style audio preparation and artifact cleanup
- Google-auth protected web and API access
- Google test-mode login, logout, and allowed-domain rejection
- approval-required Google sign-in, admin approval, and revocation flow
- admin-only access-management JSON API
- access audit history in the admin UI and API
- recent jobs listing
- 404 handling for missing jobs
- form submission and job detail rendering
