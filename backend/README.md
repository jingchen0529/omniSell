# OmniSell Video Lab Backend

FastAPI backend for a TikTok video script extraction and remake workspace.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

In development, the API now starts an embedded project worker automatically by default, so queued video jobs begin processing even if you only run `uvicorn`.

If you want a separate dedicated worker process, run it in a second terminal:

```bash
python -m app.worker
```

If you only want runtime dependencies:

```bash
pip install -r requirements.txt
```

Default database config points to local MySQL:

- host: `127.0.0.1`
- port: `3306`
- user: `root`
- password: empty
- database: `omni-sell`

The backend creates the database if needed, initializes tables on startup, and all table names use the fixed `os_` prefix.

Seeded development account:

- email: `demo@omnisell.local`
- password: `demo123456`

Core API areas:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/refresh`

Project processing now uses a database-backed job queue. The API only enqueues jobs; the actual video analysis pipeline runs in the separate `app.worker` process.

API docs:

- http://127.0.0.1:8000/docs

## Video Analysis

Real video parsing uses:

- `yt-dlp` for remote video download
- `ffprobe` / `ffmpeg` for media inspection and audio extraction
- subtitle tracks when the source already provides them
- local `faster-whisper` transcription by default when subtitles are unavailable
- optionally an OpenAI-compatible transcription endpoint when you set `VIDEO_TRANSCRIPTION_PROVIDER=openai`

Relevant environment variables:

- `VIDEO_ANALYSIS_PROVIDER=real`
- `VIDEO_TRANSCRIPTION_PROVIDER=faster_whisper`
- `VIDEO_TRANSCRIPTION_LANGUAGE=zh`
- `FFMPEG_BINARY=ffmpeg`
- `FFPROBE_BINARY=ffprobe`
- `YT_DLP_BINARY=yt-dlp`
- `FASTER_WHISPER_MODEL_SIZE=small`
- `FASTER_WHISPER_DEVICE=auto`
- `FASTER_WHISPER_COMPUTE_TYPE=int8`
- `FASTER_WHISPER_DOWNLOAD_ROOT=storage/models`
- `OPENAI_API_BASE=https://api.openai.com/v1`
- `OPENAI_API_KEY=...`
- `OPENAI_AUDIO_MODEL=whisper-1`
- `OPENAI_TRANSCRIPTION_LANGUAGE=zh`
- `OPENAI_REQUEST_TIMEOUT_SECONDS=120`
- `PROJECT_JOB_POLL_INTERVAL_SECONDS=2`
- `PROJECT_JOB_LEASE_SECONDS=1800`
- `PROJECT_JOB_WORKER_ID=worker-a`
- `PROJECT_JOB_RUN_EMBEDDED_WORKER=true`

If you use local `faster-whisper`, the first run will download the selected Whisper model into `FASTER_WHISPER_DOWNLOAD_ROOT`.

If you use a third-party OpenAI-compatible gateway instead, set `VIDEO_TRANSCRIPTION_PROVIDER=openai` plus both `OPENAI_API_BASE` and `OPENAI_API_KEY`. The backend currently calls the legacy OpenAI Python client's `Audio.transcribe` API, so the provider must support the same multipart transcription contract.
