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
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn lnkdn_transcripts.main:app --reload
```

The app expects `ffmpeg` to be installed on the host machine.

## Current status

This repository currently contains the bootstrap structure and a running skeleton app. The transcription pipeline modules are intentionally stubbed so we can implement them on focused branches.
