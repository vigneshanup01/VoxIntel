# VoxIntel
AI-powered meeting intelligence platform for transcription, speaker tracking, emotion analysis, meeting analytics, and automated summaries.

## Phase 1: Auth, upload, dashboard

Auth, meeting upload/storage, and a dashboard -- the foundation later phases
(transcription, diarization, emotion detection, summarization) attach to.

- **Server/** -- FastAPI backend (auth, meetings CRUD, MinIO/S3 storage, Postgres via SQLAlchemy + Alembic)
- **Client/** -- React + Vite frontend (login/signup, dashboard, meeting detail)

## Phase 2: Speech-to-text

Audio in, transcript out. Upload still returns immediately -- transcription
runs in a background worker so a multi-minute Whisper job never blocks the
HTTP request.

- A Celery worker (`Server/app/worker/`) picks up a job per upload, downloads
  the file from MinIO, transcribes it with `openai-whisper`, and writes
  timestamped rows to `transcript_segments`. `meetings.status` flips
  `uploaded -> processing -> transcribed` (then Phase 3 takes it further; see
  below) or `failed`, with the error stored on the row.
- Redis is the broker between the API and the worker.
- The worker has its own image (`Server/Dockerfile.worker`) with `ffmpeg` and
  `torch`/`whisper` installed -- the API image stays lean and never imports
  either.
- `GET /meetings/{id}/status` and `GET /meetings/{id}/transcript` let the
  frontend poll progress and fetch results.

## Phase 3: Speaker diarization (current)

*Who* said each thing, not just *what* was said. Transcription (Whisper) and
diarization (Pyannote) are two independent pipelines over the same audio --
neither model knows about the other -- so they're aligned afterward by
timestamp overlap.

- `diarize_meeting` is a second Celery task, chained automatically after
  `transcribe_meeting` succeeds: `uploaded -> processing -> transcribed ->
  diarizing -> completed` (or `failed` at any stage, with the error stored
  on the row).
- It runs `pyannote/speaker-diarization-3.1` on the same audio file, writes
  raw `(speaker_label, start, end)` turns to `speaker_segments`, then assigns
  a speaker to each `transcript_segments` row by **maximum time overlap**
  (not closest start time -- see `app/worker/alignment.py`, the most heavily
  unit-tested module in the backend).
- Per-speaker stats (total speaking time, turn count, % of meeting) are
  computed and stored in `speaker_stats`. `meetings.duration_seconds` also
  gets filled in here (via `ffprobe`), finally putting real data in that
  Phase 1 placeholder column.
- Diarization tells you "3 distinct voices, here's when each talks" -- it
  has **no idea who anyone is**. Labels like `SPEAKER_00` are only
  consistent *within* one meeting. `speaker_stats.display_name` lets a user
  manually rename "SPEAKER_00" -> "John" after the fact; that's the entire
  "who's who" feature here, not real speaker recognition (a separate,
  harder, unbuilt feature).
- `GET /meetings/{id}/speakers` and `PATCH /meetings/{id}/speakers/{label}`
  (rename) round out the API. The existing transcript endpoint now returns
  a populated `speaker_label` per segment once diarization finishes.
- **Setup required:** `pyannote/speaker-diarization-3.1` is gated on
  Hugging Face. Copy the root `.env.example` to `.env` and follow the steps
  in it (free HF account, accept the model's terms, generate a token) to
  set `HF_TOKEN`. Without it, transcription still works fine -- diarization
  just fails with a clear error instead of a name.

- **ai-services/** -- reserved for later phases (emotion, summarization)
- **docker/**, **docs/** -- reserved for deployment configs and documentation as the project grows

## Running locally with Docker

```bash
cp .env.example .env   # then fill in HF_TOKEN -- see Phase 3 setup above
docker compose up --build
```

This starts Postgres, MinIO, Redis, the API, the transcription+diarization
worker, and the frontend. Migrations run automatically on API/worker
startup. The worker image is significantly heavier than the API image (it
bundles `torch`, `whisper`, and `pyannote.audio`) -- expect the first
`--build` to take a long time (the combined dependency tree is large).

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8001 (docs at `/docs`) |
| MinIO console | http://localhost:9001 (login: `voxintel` / `voxintel123`) |
| Postgres | localhost:5433 (user/db: `voxintel`) |
| Redis | localhost:6379 |

> Host ports for Postgres (5433) and the API (8001) are non-default to avoid clashing with
> other local projects. Adjust the `ports:` mappings in `docker-compose.yml` (and
> `VITE_API_URL` for the client) if you'd rather use the defaults.

The Whisper model (`base` by default, see `WHISPER_MODEL_SIZE`) and the
Pyannote pipeline both download on the worker's first job and are cached
afterward in the `whisper_cache` / `hf_cache` volumes.

## Running the backend without Docker

This still needs Postgres, MinIO, and Redis running somewhere -- the easiest
way is to let docker-compose run those and run the API/worker on your host
(faster iteration than rebuilding the image on every change):

```bash
docker compose up -d postgres minio redis   # leaves api/worker/client containers out

cd Server
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env     # already points at localhost:5433 / localhost:9000 / localhost:6379
alembic upgrade head
uvicorn app.main:app --reload
```

To also run the worker on your host, install its (heavier) requirements,
make sure `ffmpeg` is on your PATH, set `HF_TOKEN` in `Server/.env` (see
Phase 3 above), then run Celery directly:

```bash
pip install -r requirements-worker.txt
celery -A app.worker.tasks worker --loglevel=info --pool=solo
```

Run the test suite (no external services needed -- it uses SQLite and an
in-memory storage fake; the two tests that run real model inference
[Whisper, Pyannote] auto-skip unless their respective dependencies,
`ffmpeg`, and -- for Pyannote -- `HF_TOKEN` are all available):

```bash
pytest
```

## Running the frontend without Docker

```bash
cd Client
npm install
cp .env.example .env
npm run dev
```
