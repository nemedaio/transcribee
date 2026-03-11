# Branch Strategy

Use short-lived feature branches off `main`. Because this repository is a new build, the clean sequence is:

1. `codex/bootstrap`
2. `codex/job-models`
3. `codex/media-fetcher`
4. `codex/whisper-transcriber`
5. `codex/web-ui`
6. `codex/exports-and-history`

## Rules

- Keep `main` always runnable.
- One feature branch per vertical slice.
- Merge only after the branch passes its own smoke test.
- Rebase small branches instead of letting them drift.

## What each branch should deliver

### `codex/bootstrap`

- repository layout
- local app skeleton
- docs and setup instructions

### `codex/job-models`

- SQLite schema
- job lifecycle
- status API

### `codex/media-fetcher`

- URL validation
- `yt-dlp` integration
- extracted audio artifacts

### `codex/whisper-transcriber`

- `faster-whisper` integration
- chunking strategy
- transcript persistence

### `codex/web-ui`

- polished single-page flow
- progress polling
- transcript result page

### `codex/exports-and-history`

- download transcript formats
- recent jobs view
- retention cleanup
