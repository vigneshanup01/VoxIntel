# VoxIntel
AI-powered meeting intelligence platform for transcription, speaker tracking, emotion analysis, meeting analytics, and automated summaries.

## Phase 1: Auth, upload, dashboard

Auth, meeting upload/storage, and a dashboard -- the foundation later phases
(transcription, diarization, emotion detection, summarization) attach to.

- **Server/** -- FastAPI backend (auth, meetings CRUD, MinIO/S3 storage, Postgres via SQLAlchemy + Alembic)
- **Client/** -- React + Vite frontend (login/signup, dashboard, meeting detail)

## Phase 2: Speech-to-text (current)

Audio in, transcript out. Upload still returns immediately -- transcription
runs in a background worker so a multi-minute Whisper job never blocks the
HTTP request.

- A Celery worker (`Server/app/worker/`) picks up a job per upload, downloads
  the file from MinIO, transcribes it with `openai-whisper`, and writes
  timestamped rows to `transcript_segments`. `meetings.status` flips
  `uploaded -> processing -> transcribed` (or `failed`, with the error stored
  on the row) as it goes.
- Redis is the broker between the API and the worker.
- The worker has its own image (`Server/Dockerfile.worker`) with `ffmpeg` and
  `torch`/`whisper` installed -- the API image stays lean and never imports
  either.
- `GET /meetings/{id}/status` and `GET /meetings/{id}/transcript` let the
  frontend poll progress and fetch results; the meeting detail page polls
  every 3s while processing and renders the transcript once ready (or the
  stored error message if it failed).

- **ai-services/** -- reserved for later phases (diarization, emotion, summarization)
- **docker/**, **docs/** -- reserved for deployment configs and documentation as the project grows

## Running locally with Docker

```bash
docker compose up --build
```

This starts Postgres, MinIO, Redis, the API, the transcription worker, and the
frontend. Migrations run automatically on API/worker startup. The worker
image is significantly heavier than the API image (it bundles `torch` +
`whisper`) -- expect the first `--build` to take a while.

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

The Whisper model (`base` by default, see `WHISPER_MODEL_SIZE` in
docker-compose.yml) downloads on the worker's first job and is cached in the
`whisper_cache` volume afterward.

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

To also run the worker on your host, install its (heavier) requirements and
make sure `ffmpeg` is on your PATH, then run Celery directly:

```bash
pip install -r requirements-worker.txt
celery -A app.worker.tasks worker --loglevel=info --pool=solo
```

Run the test suite (no external services needed -- it uses SQLite and an
in-memory storage fake; the one test that runs real Whisper inference
auto-skips unless `openai-whisper` and `ffmpeg` are both available):

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
