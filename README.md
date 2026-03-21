# Transcribee

[![CI](https://github.com/nemedaio/transcribee/actions/workflows/ci.yml/badge.svg)](https://github.com/nemedaio/transcribee/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

Free, local-first video transcription. Paste a URL, get a transcript — no paywall, no cloud dependency, no data leaving your machine.

Built to make LinkedIn video transcripts accessible to everyone.

## How it works

1. Paste a video URL (LinkedIn, YouTube, or any site supported by yt-dlp)
2. Transcribee downloads the media and extracts audio locally
3. A local Whisper model (or cloud API if you prefer) produces timestamped text
4. Download your transcript as TXT, Markdown, SRT, or VTT

Everything runs on your computer. No subscriptions, no usage limits.

## Quick start

### CLI (fastest)

```bash
pip install transcribee[faster-whisper]
transcribee https://www.linkedin.com/posts/some-video-post
```

That's it. Transcript prints to stdout. Save to file with `-o transcript.txt`. Export as SRT with `-f srt`.

```bash
transcribee https://linkedin.com/posts/... -o output.srt -f srt
transcribee https://youtube.com/watch?v=... -f json
transcribee https://example.com/video --model base  # smaller/faster model
```

### Web UI

```bash
pip install transcribee[faster-whisper]
uvicorn transcribee.main:app
```

Open http://localhost:8000 — paste a URL or batch-paste up to 20 at once.

### Docker

```bash
git clone https://github.com/nemedaio/transcribee.git
cd transcribee
cp .env.example .env
docker compose up
```

> Requires Python 3.10+ and [ffmpeg](https://ffmpeg.org/) on your machine (Docker includes both).

## Transcription backends

Transcribee supports 5 backends. Set `TRANSCRIBER_BACKEND` in your `.env` file.

### Local (free, runs on your machine)

| Backend | Install | Notes |
|---------|---------|-------|
| `faster-whisper` (default) | `pip install -e ".[faster-whisper]"` | Fast, low memory. Recommended for most users. |
| `openai-whisper` | `pip install -e ".[openai-whisper]"` | Original OpenAI Whisper. |
| `whisper-cpp` | `pip install -e ".[whisper-cpp]"` | C++ implementation, good for CPU-only machines. |

### Cloud API (bring your own key)

| Backend | Install | Env vars |
|---------|---------|----------|
| `openai-api` | `pip install -e ".[openai-api]"` | `OPENAI_API_KEY` |
| `deepgram` | `pip install -e "."` | `DEEPGRAM_API_KEY` |

Example `.env` for a cloud backend:
```bash
TRANSCRIBER_BACKEND=openai-api
OPENAI_API_KEY=sk-...
```

API keys are read from environment variables only — never stored in the database or exposed in the UI.

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSCRIBER_BACKEND` | `faster-whisper` | Which transcription engine to use |
| `WHISPER_MODEL` | `large-v3-turbo` | Model name (~1.5 GB, works on 16GB Macs) |
| `MAX_UPLOAD_MINUTES` | `30` | Max audio duration to process |

For smaller machines or faster startup, use a smaller model:
```bash
WHISPER_MODEL=base      # ~140 MB
WHISPER_MODEL=small     # ~460 MB
WHISPER_MODEL=medium    # ~1.5 GB
```

## Features

- Paste any video URL and get a transcript
- Batch transcription — paste up to 20 URLs at once
- Live progress tracking with animated status updates
- Export transcripts as TXT, Markdown, SRT, VTT
- LinkedIn URL normalization (strips tracking params, validates post URLs)
- Job dashboard with status counts and retry controls
- Background job processing
- Artifact retention cleanup
- Optional Google OAuth with admin access controls and audit trail

## Running tests

```bash
pip install -e ".[dev,faster-whisper]"
pytest
```

111 tests covering the backend factory, all export formats, URL normalization, security (XSS, CSV injection, open redirect), batch endpoints, and the full job pipeline.

## API

Transcribee exposes both a browser UI and a JSON API:

```
POST /api/jobs              Submit a video URL for transcription
POST /api/jobs/batch        Submit up to 20 URLs at once
GET  /api/jobs              List recent jobs
GET  /api/jobs/{id}         Get job status and transcript
POST /api/jobs/{id}/retry   Retry a failed job
GET  /api/dashboard         Job status counts
```

## Google auth (optional)

Authentication is disabled by default. To protect your instance:

```bash
AUTH_ENABLED=true
SESSION_SECRET_KEY=replace-with-a-long-random-string
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

Optional hardening:

```bash
GOOGLE_ALLOWED_EMAIL_DOMAINS=yourdomain.com
GOOGLE_ADMIN_EMAILS=admin@yourdomain.com
GOOGLE_REQUIRE_APPROVAL=true
```

## License

[MIT](LICENSE)
