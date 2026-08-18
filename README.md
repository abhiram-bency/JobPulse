# JobPulse

A small, production-minded **job ingestion dashboard**. JobPulse ingests remote jobs from a legitimate public RSS feed, normalizes and deduplicates them into PostgreSQL, and exposes them through a FastAPI backend with a polished React dashboard.

This is the Part 1 implementation ("Getting Data Out of a Platform That Doesn't Want You To") of the Acdyon Technologies take-home, built against a **low-risk public source** as the challenge explicitly requires — not a live LinkedIn account and no anti-bot techniques.

---

## What is JobPulse?

- Fetches jobs from a public job feed (Himalayas RSS).
- Parses the RSS/Atom payload, validates every record, normalizes to a canonical shape, and deduplicates before persisting.
- Tracks every ingestion run (`sync_runs`) with real statistics — nothing is fabricated.
- Handles source failures gracefully: timeouts, HTTP 429, 5xx, malformed XML, empty responses, and parser-drift anomalies. **Valid data is never silently deleted.**
- Exposes jobs, sources, sync runs, and health through a REST API.
- Provides a responsive dashboard with source health, KPI cards, search/filter/pagination, a manual sync button, and a step-by-step sync progress view.

## Architecture

```
                Himalayas RSS (public feed)
                      |
                      v
                HTTP Fetcher          timeouts, bounded retries, exponential
                Retry / Backoff       backoff, rate limiting, Retry-After
                      |
                      v
                 RSS Parser            RSS 2.0 / Atom -> RawJob
                      |
                      v
                  Validator            required: title + url; bad records skipped
                      |
                      v
                 Normalizer            canonical NormalizedJob, deterministic
                                       fingerprint fallback for missing IDs
                      |
                      v
                Deduplicator           (source_id, external_id) upsert:
                                       created / updated / skipped
                      |
                      v
                 PostgreSQL            sources, jobs, sync_runs
                      |
                      v
                   FastAPI             /api/v1/jobs|sources|sync-runs|sync|health
                      |
                      v
                   Frontend            React + Vite + TypeScript dashboard
```

Source adapters are pluggable. `JobSource` is an abstract interface
(`backend/app/sources/base.py`) and `HimalayasRSSSource` is the single
production implementation — a second provider only needs to implement the
same three methods (`fetch`, `parse`, `normalize`).

## Why Himalayas?

The challenge says: "Run your live demo against one low-risk source — a public job-board RSS/API, or a sandbox you control."

`https://himalayas.app/jobs/rss` is a public, well-formed RSS 2.0 feed of remote jobs with:
- **no API key** and no authentication,
- a **predictable structure** (`guid`, `link`, `pubDate`, `description`, `content:encoded`),
- **enough real data** (≈100 listings) for a convincing demo,
- explicit `ttl` guidance we can respect.

Direct HTML scraping of a social platform is deliberately **not** attempted. That is both a compliance requirement of the challenge and unnecessary for demonstrating the ingestion architecture.

## Data flow

```
RSS → Fetch → Parse → Validate → Normalize → Deduplicate → PostgreSQL → FastAPI → Frontend
```

1. **Fetch** — `httpx.AsyncClient` with timeouts, a descriptive User-Agent, connection limits, bounded retries with exponential backoff, `Retry-After` support, and a configurable minimum request interval.
2. **Parse** — stdlib `xml.etree` parses RSS 2.0 and Atom into source-agnostic `RawJob` entries. Malformed XML raises a typed parse error instead of crashing the sync.
3. **Validate** — every record must have a title and a URL. Invalid records are counted, logged, and skipped; one bad record never aborts the sync.
4. **Normalize** — cleans text, strips HTML from descriptions, derives company from the `/companies/<slug>/` URL path (the feed emits a placeholder company), and generates a deterministic fingerprint (`sha256`) when the source lacks a stable ID.
5. **Deduplicate** — `UNIQUE(source_id, external_id)` in the database plus an application-level upsert that classifies each job as **created / updated / skipped**.
6. **Persist** — PostgreSQL stores `sources`, `jobs`, and `sync_runs`.
7. **Serve** — FastAPI exposes jobs with pagination/search/filters, source health, sync history, and a live sync endpoint.
8. **Present** — the React dashboard renders source health, KPIs, the job list, and sync feedback.

## Failure handling

| Failure | Behavior |
|---|---|
| Connection error / timeout | Bounded retries with exponential backoff; then sync marked **failed** with a descriptive message. |
| HTTP 429 | Honors `Retry-After` (capped), retries, then marks the sync **failed**; `last_failure_at` is recorded. |
| HTTP 5xx | Retried (bounded); client errors (4xx) are **not** retried. |
| Malformed XML | Sync **failed**; existing jobs untouched. |
| Empty feed (0 entries) | Marked **suspicious** — previous data is preserved, never deleted. |
| >50% invalid records | Marked **suspicious** as a likely parser/schema change; the few valid records are still stored. |
| Source disabled/missing | API returns a clear 409/404. |

**Data preservation is structural:** a sync can only insert or update rows. Nothing is ever deleted because of a single bad ingestion. The challenge's "100 jobs → 0 jobs" scenario therefore always leaves the 100 jobs intact and surfaces a warning.

## Repository layout

```
jobpulse/
├── backend/
│   ├── app/
│   │   ├── api/routes/     # jobs, sources, sync-runs, sync, health
│   │   ├── core/           # settings, logging, time helpers
│   │   ├── db/             # engine + session
│   │   ├── models/         # Source, Job, SyncRun (SQLAlchemy)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── sources/        # JobSource ABC + HimalayasRSSSource
│   │   └── ingestion/      # fetcher, parser, validator, normalizer,
│   │                       # deduplicator, service
│   ├── alembic/            # migrations
│   └── tests/              # pytest suite (all HTTP is mocked)
├── frontend/               # Vite + React + TypeScript dashboard
├── docker-compose.yml
├── .env.example
├── README.md
└── DECISIONS.md
```

## Local setup

Prerequisites: Python 3.11+, Node 20+, Docker + Docker Compose.

### Option A — everything via Docker (recommended)

```bash
cp .env.example .env
docker compose up -d --build
```

Then open http://localhost:5174 (frontend), http://localhost:8001/docs (API).

Ports: PostgreSQL `55432`, backend `8001`, frontend `5174`. These were chosen
to avoid colliding with other projects already bound to the common ports.

### Option B — run pieces locally

```bash
# 1. Database (PostgreSQL on port 55432)
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt   # Windows
# .venv/bin/pip install -r requirements-dev.txt     # macOS/Linux
$env:DATABASE_URL = "postgresql+psycopg://jobpulse:jobpulse@localhost:55432/jobpulse"
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --port 8001

# 3. Frontend (dev server on 5174, proxies /api to :8001)
cd frontend
npm install
npm run dev
```

## Testing

All HTTP is mocked — tests never touch the real feed.

```bash
cd backend
.venv\Scripts\python -m pytest -q
```

54 tests cover:
- **Source/fetcher**: success, timeout, HTTP 429, HTTP 500, retry-then-success, retry exhaustion, non-retried 404, connection errors.
- **Parser**: valid RSS, empty feed, malformed XML, unrecognized root, Atom, namespace extras, missing optional fields, date parsing.
- **Normalization**: deterministic fingerprints, HTML stripping, slug-derived companies, guid vs. fingerprint IDs.
- **Validation**: missing title/url skipped without killing the batch.
- **Deduplication**: create / update / skip, in-batch duplicates, DB unique constraint.
- **Ingestion**: successful sync, partial invalid records, suspicious zero-result, data preservation after failure, high-invalid-ratio detection, disabled source, concurrent sync serialization.
- **API**: jobs list/detail, filters, pagination, sync run history, health, sync failure response.

## Deployment

The `docker-compose.yml` stack is the deployment unit:

- `db` — PostgreSQL 16 with a persistent volume and healthcheck.
- `backend` — runs `alembic upgrade head` on startup, then serves Uvicorn. Everything from `.env` is passed as environment variables.
- `frontend` — production build served by nginx, which proxies `/api` to the backend.

Deploy to any Docker host with:

```bash
docker compose up -d --build
```

For a managed environment, the same images can be pushed and run with the
same environment variables (`DATABASE_URL`, `HIMALAYAS_FEED_URL`,
`FETCH_*`, `MINIMUM_REQUEST_INTERVAL_SECONDS`, `CORS_ORIGINS`).

## Configuration

All settings live in `backend/app/core/config.py` (pydantic-settings) and are overridable via environment variables — see `.env.example` for the full list, including:

- `FETCH_TIMEOUT_SECONDS`, `FETCH_MAX_RETRIES`, `FETCH_BASE_BACKOFF_SECONDS`, `FETCH_MAX_BACKOFF_SECONDS`
- `MINIMUM_REQUEST_INTERVAL_SECONDS` — responsible-traffic rate limiting
- `MIN_VALID_JOBS_THRESHOLD`, `MAX_INVALID_RATIO`, `ANOMALY_MIN_TOTAL_ENTRIES` — suspicious-result detection

## Limitations

- **Single source.** Only Himalayas RSS is implemented. The `JobSource` interface makes a second source straightforward to add but it does not exist yet.
- **Feed quirk:** Himalayas does not publish a real company name in RSS (`himalayasJobs:companyName` is the literal placeholder `name`), so company is derived from the URL slug. Company names are therefore best-effort.
- **Synchronous ingestion.** There is no queue/worker; a manual `POST /api/v1/sync` runs inline. That is intentional for this challenge (simple > complex) and acceptable for a single low-volume source.
- **In-process lock.** Concurrent syncs of the same source are serialized only within one backend process; horizontally scaling the API would require a distributed lock.
- **No auth.** The dashboard is single-user and unauthenticated.
- **No deletion logic.** Jobs are never removed by a sync; there is no retention/expiry policy for old listings (an intentional, conservative default).