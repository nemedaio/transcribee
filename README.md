# Transcribee

Free, local-first video transcription. Paste a URL, get a transcript — no paywall, no cloud dependency, no data leaving your machine.

Built to make LinkedIn video transcripts accessible to everyone.

## How it works

1. Paste a video URL (LinkedIn, YouTube, or any site supported by yt-dlp)
2. Transcribee downloads the media and extracts audio locally
3. A local Whisper model (or cloud API if you prefer) produces timestamped text
4. Download your transcript as TXT, Markdown, SRT, or VTT

Everything runs on your computer. No subscriptions, no usage limits.

## Quick start

```bash
git clone https://github.com/nemedaio/transcribee.git
cd transcribee
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[faster-whisper]"
uvicorn transcribee.main:app
```

Open http://localhost:8000 and paste a video URL.

> Requires Python 3.10+ and [ffmpeg](https://ffmpeg.org/) installed on your machine.

## Transcription backends

Transcribee supports multiple backends. Set `TRANSCRIBER_BACKEND` in your `.env` file.

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

Example `.env` for OpenAI API:
```bash
TRANSCRIBER_BACKEND=openai-api
OPENAI_API_KEY=sk-...
```

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
- LinkedIn URL normalization (strips tracking params, validates post URLs)
- Export transcripts as TXT, Markdown, SRT, VTT
- Job dashboard with status tracking and retry controls
- Background job processing
- Artifact retention cleanup
- Optional Google OAuth authentication with admin access controls
- Audit trail for access management

## Running tests

```bash
pip install -e ".[dev,faster-whisper]"
pytest
```

## API

Transcribee exposes both a browser UI and a JSON API:

```
POST /api/jobs              Submit a video URL for transcription
GET  /api/jobs              List recent jobs
GET  /api/jobs/{id}         Get job status and transcript
POST /api/jobs/{id}/retry   Retry a failed job
GET  /api/dashboard         Job status counts
```

## License

[MIT](LICENSE)
