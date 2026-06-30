# VoxIntel
AI-powered meeting intelligence platform for transcription, speaker tracking, automated summaries, and cross-meeting search/analytics. (Sentiment/emotion analysis was scoped and deliberately skipped -- see Phase 5 below.)

## Phase 1: Auth, upload, dashboard

Auth, meeting upload/storage, and a dashboard -- the foundation later phases
(transcription, diarization, emotion detection, summarization) attach to.

- **Server/** -- FastAPI backend (auth, meetings CRUD, MinIO/S3 storage, Postgres via SQLAlchemy + Alembic)
- **Client/** -- React + Vite frontend (login/signup, dashboard, meeting detail)
- **docker/**, **docs/** -- reserved for deployment configs and documentation as the project grows

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

## Phase 3: Speaker diarization

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

## Phase 5: Sentiment/emotion analysis -- deliberately skipped

An earlier plan for this project included a phase that would tag transcript
segments (or speakers) with detected sentiment/emotion. It's skipped here, on
purpose, not because it's technically hard but because the risk/reward is bad
for a meeting-recording product specifically:

- **The underlying ML is shakier than it's usually presented as.** Voice- and
  text-based emotion recognition has well-documented accuracy and
  cross-cultural validity problems -- confidently-labeled "anger" or
  "frustration" output is often not measuring what it claims to measure, and
  errors aren't evenly distributed: published work on these models shows
  measurably worse accuracy for some accents, dialects, and demographic
  groups than others.
- **The privacy/workplace-surveillance exposure is real, not hypothetical.**
  This product processes recordings of people's actual work meetings. Adding
  a feature that algorithmically scores colleagues' emotional state during
  those meetings -- even with good intentions -- creates a plausible path to
  misuse (informal performance judgments, a chilling effect on candid
  discussion) that the rest of this project's features don't.
- **The regulatory ground is actively shifting under workplace emotion
  recognition specifically** (e.g. it's called out as a higher-scrutiny use
  case under the EU AI Act), which is a bad combination with the accuracy
  problem above -- it's exactly the kind of feature that looks like a fun demo
  and turns into a liability question in production.

Skipping it is the engineering decision here, not an oversight: the judgment
call was that "speaker talked for N minutes and said X" (Phases 3-4) is
useful and defensible, while "speaker was probably feeling Y" is neither
reliable enough nor safe enough to ship without a lot more validation than a
capstone-scale project can give it.

## Phase 4: AI summaries

The last link in the pipeline: once a meeting is transcribed and diarized,
`summarize_meeting` sends the transcript to Claude and turns it into
something a busy person could actually use.

- `summarize_meeting` is a third Celery task, chained automatically after
  `diarize_meeting` succeeds: `... -> diarized -> summarizing -> completed`
  (or `failed` at any stage). It's also manually triggerable any time a
  transcript exists, via `POST /meetings/{id}/summarize` -- e.g. the
  frontend's "Regenerate summary" button.
- It builds a timestamped, speaker-attributed transcript (resolving
  `speaker_stats.display_name` where set), sends it to the Claude API with
  **structured output** (`output_config.format` / JSON schema) so the
  response is always parseable JSON rather than free-text it has to
  regex out, and validates the result against Pydantic models -- with one
  retry if a response is somehow still malformed (truncation, refusal).
  See `app/worker/summarization.py`.
- Produces: an `executive_summary` + `detailed_summary`
  (`meeting_summaries`), `action_items` (description, owner, due date --
  never invented, only what the transcript actually states), `decisions`,
  and notable/risk `quotes` with a timestamp the frontend can jump the
  transcript view to.
- Long transcripts (beyond `SINGLE_PASS_CHAR_LIMIT`, ~60K characters) are
  handled with a map-reduce pass instead of one giant prompt: each chunk is
  summarized independently (action items/decisions/quotes extracted per
  chunk), then a final pass combines the partial summaries into one
  coherent executive/detailed summary.
- `GET /meetings/{id}/summary`, `/action-items` (+ `PATCH` to check one off),
  `/decisions`, and `/quotes` round out the API.
- **Setup required:** generate a key at
  https://console.anthropic.com/settings/keys and set `ANTHROPIC_API_KEY`
  in the root `.env` (see `.env.example`) -- **never commit a real key**.
  Without it, transcription and diarization still work fine; summarization
  just fails with a clear "ANTHROPIC_API_KEY is not set" error instead of a
  summary. `ANTHROPIC_MODEL` (default `claude-opus-4-8`) is also
  overridable if you want a cheaper/faster model for this step.

## Phase 6: Dashboard, search & analytics (current)

By Phase 4, every meeting individually has a transcript, speakers, and a
summary. Phase 6 doesn't add a new ML stage -- it rolls that *per-meeting*
data up into *cross-meeting* views: a home dashboard, search across
everything you've uploaded, per-speaker analytics over time, and a
downloadable report. No new core tables; mostly indexes and queries over
what already exists (migration `0006`).

- **`GET /dashboard/summary`** -- total meetings, total hours, meetings
  uploaded in the last 7 days, the most-talked speaker (named speakers
  only, see below), and the 5 most recent meetings.
- **`GET /meetings/search?q=&speaker=&from=&to=`** -- a meeting matches `q`
  if it's in the title *or* anywhere in its transcript; matches `speaker`
  if any of its speaker_stats rows' label or display name contains it.
  Paginated (`limit`/`offset`).
- **`GET /search/transcripts?q=`** -- segment-level results across all of
  a user's meetings, each with a timestamp and snippet, for "jump straight
  to where this was said." The frontend's search page links each result to
  `/meetings/{id}?t={seconds}`, which scrolls the transcript view to (and
  briefly highlights) the nearest segment.
- **`GET /analytics/speakers?from=&to=`** -- per-speaker total speaking
  time aggregated *across* meetings, with a date range. This only works
  for speakers with a `display_name` set (Phase 3's rename feature) --
  `SPEAKER_00` in one meeting and `SPEAKER_00` in another are not
  necessarily the same person, so unnamed rows are counted and excluded,
  never silently merged into a stranger's total. The response says how
  many were excluded; the frontend says so too.
- **`GET /meetings/{id}/report.pdf`** -- renders the summary, action
  items, decisions, quotes, and speaker breakdown to HTML, then to PDF via
  WeasyPrint. Needs a summary to exist first (400 if not).
- Full-text search uses Postgres's built-in `tsvector`/`GIN` index
  (migration `0006`) rather than `LIKE '%term%'` or a separate search
  service -- plenty for a project's worth of meetings, and the honest
  answer for "how would this scale" is "read replicas / materialized
  views," not "we'd add Elasticsearch." The search/dashboard/analytics
  query logic falls back to a portable `ILIKE` match when not running on
  Postgres (e.g. the SQLite-backed test suite) -- same behavior, different
  performance characteristics; see `app/search/service.py`.

## Running locally with Docker

```bash
cp .env.example .env   # then fill in HF_TOKEN and ANTHROPIC_API_KEY -- see Phase 3/4 setup above
docker compose up --build
```

This starts Postgres, MinIO, Redis, the API, the transcription+diarization
worker, and the frontend. Migrations run automatically on API/worker
startup. The worker image is significantly heavier than the API image (it
bundles `torch`, `whisper`, and `pyannote.audio`) -- expect the first
`--build` to take a long time (the combined dependency tree is large).
Both Whisper and Pyannote run on CPU; a real meeting's diarization takes
minutes, not seconds -- there's no GPU acceleration wired up (deliberately
kept out to avoid an NVIDIA-GPU/driver/nvidia-container-toolkit dependency
in the default setup).

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
make sure `ffmpeg` is on your PATH, set `HF_TOKEN` and `ANTHROPIC_API_KEY`
in `Server/.env` (see Phase 3/4 above), then run Celery directly:

```bash
pip install -r requirements-worker.txt
celery -A app.worker.tasks worker --loglevel=info --pool=solo
```

Run the test suite (no external services needed -- it uses SQLite and an
in-memory storage fake; the three tests that make real calls out [Whisper,
Pyannote, Claude] auto-skip unless their respective dependencies and
credentials -- `ffmpeg`, `HF_TOKEN`, `ANTHROPIC_API_KEY` -- are available,
and the one real-PDF-rendering report test skips if WeasyPrint's native
Pango/Cairo libraries aren't installed on your host -- they usually aren't
on plain Windows, see Phase 6 above):

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
