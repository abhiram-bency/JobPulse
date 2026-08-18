# Decisions

## Decision 1 — Why this ingestion strategy?

The challenge explicitly permits a public job RSS/API as the live demo source and forbids scraping a real LinkedIn account or bypassing access controls. I therefore chose **Himalayas RSS** (`https://himalayas.app/jobs/rss`): it is a legitimate, public, unauthenticated RSS 2.0 feed with a stable structure (`guid`, `link`, `pubDate`, `content:encoded`), no API key, and enough real data (~100 jobs) to make the demo convincing. No HTML scraping was needed, because a well-formed feed already demonstrates every part of the pipeline the challenge asks about — fetching, parsing, normalization, validation, deduplication, retries, and failure detection.

A **source adapter** (`JobSource` ABC + `HimalayasRSSSource`) keeps the rest of the application unaware of source-specific RSS details, so a second provider (e.g. RemoteOK) is a drop-in rather than a rewrite. The implementation deliberately prioritizes **reliability over aggressive scraping**: bounded retries with exponential backoff, `Retry-After` support, a minimum request interval, and — most importantly — a design that **never deletes valid data** because one sync returned zero jobs. This is the behavior the challenge's systems-thinking questions are probing.

## Decision 2 — Trade-off

I implemented **one production-quality source adapter** rather than several shallow providers. This concentrates effort on the pipeline, resilience, tests, and UI. With another week I would: add a second provider (RemoteOK) plus contract tests for source schemas, and add a retention/expiry policy for stale listings. I also used **synchronous ingestion** (no Celery/Redis): for a single low-volume feed that is simpler to reason about, easier to test, and fully sufficient — a queue would only add operational complexity without a clear win here.

## Decision 3 — AI usage

This project was built with the assistance of an AI coding agent (opencode).

- **Where AI was used:** scaffolding, architecture planning, and the first pass of most backend, test, and frontend code.
- **What code was generated:** the FastAPI application (config, DB layer, models, schemas, ingestion pipeline, API routes), the React dashboard, the Docker setup, the Alembic migration, and the pytest suite.
- **What was manually reviewed and changed:** the entire pipeline was verified end-to-end against the live feed and PostgreSQL. Specific manual fixes included: correcting stats semantics so `jobs_found = created + updated + skipped`, fixing the dependency-injection chain so mock fetchers actually take effect in tests, fixing a timezone normalization bug for SQLite-vs-Postgres, aligning the health endpoint with `/api/v1/health`, and correcting the RSS fixture builder (CDATA must not be double-escaped). Ports were chosen to avoid conflicts with other local projects.
- **What tests were added:** 54 tests covering the fetcher (timeout, 429, 500, retry exhaustion), parser, normalizer, validator, deduplicator, the full sync service (success, partial-invalid, suspicious zero-result, failure-preserves-data), and all API endpoints. Every test uses mocked HTTP.
- **What I would still do before submitting:** a final human pass over the frontend at 390px/1440px in a real browser, and a review of the DECISIONS.md claims against the final code.