# Engineering Decisions

## 1. Ingestion Strategy

The obvious alternative was scraping a real platform like LinkedIn, which the challenge frames but explicitly forbids for the live demo. Beyond the rule, it's a poor engineering bet: it breaks on every layout change, invites anti-bot/access restrictions mid-run, and buys nothing the challenge actually needs — every part of the pipeline it asks about (fetching, parsing, normalization, validation, deduplication, retries, failure detection) is equally demonstrable against a well-formed public feed, without the fragility.

I ingest from **Himalayas' public RSS feed** — no auth, no key, a stable structure (`guid`, `link`, `pubDate`, `content:encoded`), and real data. Source-specific logic sits behind `JobSource`, an abstract base class: it provides a concrete `fetch()` (shared HTTP client, retries, backoff) and requires each provider to implement `parse()`/`normalize()` — so Himalayas' quirks (its `companyName` field is a literal placeholder; real company names are derived from the job URL slug) live entirely inside `HimalayasRSSSource` and never leak into the ingestion service. Requests are also throttled with a minimum interval between calls, so the fetcher doesn't poll the source any more aggressively than necessary even outside of a failure/retry scenario.

## 2. Time-Constrained Trade-off

**Constraint:** limited time, one source to prove the architecture against.
**Decision:** build one source adapter to production quality — full retry/backoff, anomaly detection, and a matching test suite — instead of spreading the same time across several shallow providers, and run ingestion synchronously rather than adding Celery/Redis.
**Benefit:** the time went into what's actually graded: how the system behaves when the source misbehaves.
**Cost:** the `JobSource` abstraction is designed for additional providers, but I didn't validate it against a second real provider within the deadline, so I can't yet prove the interface generalizes past Himalayas. Synchronous ingestion is appropriate at this scale; concurrent multi-source or scheduled ingestion would justify a worker/queue model.
**With a real week:** add a second provider with contract tests against both source schemas, a periodic scheduler instead of the current manual `POST /api/v1/sync` trigger, and a retention policy for listings that stop appearing in the feed.

## 3. AI-Assisted Development and Verification

I built this with an AI coding agent (OpenCode) generating the first pass of the backend, ingestion pipeline, tests, and React frontend. From there the loop was: run it against the real Himalayas feed and PostgreSQL, find where behavior didn't match intent, diagnose why, and fix it — not just accept and move on. Concrete examples:

- **Stats accounting was wrong.** The generated sync service had incorrect `jobs_found` accounting; I corrected the bookkeeping so the API statistics remain internally consistent (`jobs_found = created + updated + skipped`).
- **The retry/failure tests weren't exercising the intended retry logic.** The mock fetcher was wired in a way that let the real dependency take effect instead of the test double, so `test_fetcher.py` was silently passing without ever hitting the mocked 429/500 paths. I fixed the injection so those tests actually exercise the intended failure behavior.
- **A timezone bug** between SQLite (dev) and Postgres (prod) surfaced during local-vs-deployed testing; naive and aware datetimes were being compared, and I fixed it in normalization.
- **The RSS test fixture was double-escaping CDATA**, masking a real parser edge case; I rebuilt it to match what the live feed actually sends.

The fetcher retries transient 429/5xx failures but does not retry non-retryable 4xx responses; backoff is bounded and jittered rather than unbounded. More importantly, a zero-result or high-invalid-ratio sync is marked suspicious rather than treated as "the source now has no jobs": a fetch or parse failure exits before any write happens, and even on a successful-but-suspicious fetch, the write path only creates or updates records that pass validation — there is no delete path in ingestion. So a failed, blocked, malformed, or suspicious sync cannot remove previously valid jobs from the database. Dedicated tests enforce this behavior rather than merely asserting it in the documentation.