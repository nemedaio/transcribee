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

## Current branch status

`codex/dashboard-retries` extends the persistent workflow:

- submit one video URL
- store a transcription job in SQLite
- fetch media locally with `yt-dlp`
- transcribe fetched media locally with `faster-whisper`
- persist fetched artifact metadata, transcript output, segment timings, and processing errors
- download completed transcripts as TXT, Markdown, SRT, and VTT
- browse recent jobs from a dedicated history page
- queue submitted jobs for background processing instead of blocking the request
- normalize LinkedIn URLs more aggressively and reject non-post/non-video LinkedIn pages with clearer errors
- expose a dashboard with live status counts and dedicated active/failed/completed sections
- retry failed jobs from the dashboard, history page, or job detail page
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

## API snapshot

```text
GET  /health
GET  /
GET  /dashboard
POST /jobs
POST /jobs/{job_id}/retry
GET  /jobs/{job_id}
POST /api/jobs
GET  /api/dashboard
POST /api/jobs/{job_id}/retry
GET  /api/jobs/{job_id}
GET  /api/jobs
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
- recent jobs listing
- 404 handling for missing jobs
- form submission and job detail rendering
