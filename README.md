# VoxIntel
AI-powered meeting intelligence platform for transcription, speaker tracking, emotion analysis, meeting analytics, and automated summaries.

## Phase 1 (current)

Auth, meeting upload/storage, and a dashboard -- the foundation later phases
(transcription, diarization, emotion detection, summarization) attach to.

- **Server/** -- FastAPI backend (auth, meetings CRUD, MinIO/S3 storage, Postgres via SQLAlchemy + Alembic)
- **Client/** -- React + Vite frontend (login/signup, dashboard, meeting detail)
- **ai-services/** -- reserved for later phases (transcription, diarization, emotion, summarization)
- **docker/**, **docs/** -- reserved for deployment configs and documentation as the project grows

## Running locally with Docker

```bash
docker compose up --build
```

This starts Postgres, MinIO, the API, and the frontend. Migrations run automatically on API startup.

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API | http://localhost:8001 (docs at `/docs`) |
| MinIO console | http://localhost:9001 (login: `voxintel` / `voxintel123`) |
| Postgres | localhost:5433 (user/db: `voxintel`) |

> Host ports for Postgres (5433) and the API (8001) are non-default to avoid clashing with
> other local projects. Adjust the `ports:` mappings in `docker-compose.yml` (and
> `VITE_API_URL` for the client) if you'd rather use the defaults.

## Running the backend without Docker

This still needs Postgres and MinIO running somewhere -- the easiest way is to
let docker-compose run just those two and run the API itself on your host
(faster iteration than rebuilding the image on every change):

```bash
docker compose up -d postgres minio   # leaves api/client containers out

cd Server
python -m venv .venv
.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env     # already points at localhost:5433 / localhost:9000, matching the ports above
alembic upgrade head
uvicorn app.main:app --reload
```

Run the test suite (no external services needed -- it uses SQLite and an in-memory storage fake):

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
