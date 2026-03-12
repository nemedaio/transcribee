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

`codex/media-fetcher` extends the first persistent workflow:

- submit one video URL
- store a transcription job in SQLite
- fetch media locally with `yt-dlp`
- persist fetched artifact metadata and fetch errors
- fetch job status over JSON
- show a basic job detail page in the browser

Jobs now move through fetch states immediately in-process:

- `queued`
- `fetching`
- `fetched`
- `failed`

Transcription lands on the next branch.

## Logging

The app emits structured-enough application logs with timestamps, logger name, and a clear event message for:

- app startup
- database initialization
- job creation
- fetch start and success
- fetch failures
- job lookup failures

This is intentionally simple for local development and easy terminal debugging.

## API snapshot

```text
GET  /health
GET  /
POST /jobs
GET  /jobs/{job_id}
POST /api/jobs
GET  /api/jobs/{job_id}
GET  /api/jobs
```

## Tests

Current automated coverage focuses on the first backend contract plus media fetch behavior:

- healthcheck
- job creation through the JSON API
- successful fetch processing with persisted metadata
- fetch failure persistence
- recent jobs listing
- 404 handling for missing jobs
- form submission and job detail rendering
