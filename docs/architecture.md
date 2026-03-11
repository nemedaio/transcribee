# Architecture

## Product goal

Accept one video URL, process it locally, and return a transcript through a simple browser UI.

## Technical shape

This project starts as a Python monolith with a thin HTML frontend.

### Why this is the right first version

- The hardest integration points are Python-native (`faster-whisper`, `yt-dlp`, `ffmpeg`).
- The UI only needs one form, one job-status view, and one transcript result view.
- Deployment can stay local-first without Docker or a cloud queue in the first pass.

## Modules

### `routes/`

- `web.py`: browser-facing pages and form submission
- `api.py`: machine-friendly endpoints for job status and transcript fetch
- `health.py`: health and dependency checks

### `services/`

- `jobs.py`: job creation and state transitions
- `fetcher.py`: URL validation and media download
- `transcriber.py`: whisper model loading and inference
- `exporters.py`: text, markdown, and subtitle exports

### `storage/`

- `models.py`: SQLModel job/transcript records
- `repo.py`: database access helpers

## Data flow

1. `POST /jobs` receives a URL.
2. `jobs.py` persists a pending job in SQLite.
3. Worker logic calls `fetcher.py` to download media.
4. Extracted audio is passed to `transcriber.py`.
5. Transcript and timestamps are stored and exposed to the UI.

## Planned milestones

### Milestone 1

- Single-page form
- Manual submit
- Background job execution in-process
- Plain text transcript output

### Milestone 2

- Better progress reporting
- Subtitle export (`.srt`, `.vtt`)
- Job history

### Milestone 3

- Provider-specific extractors
- Authentication for private personal usage
- Batch ingestion
