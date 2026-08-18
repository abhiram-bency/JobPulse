"""HTTP fetching with bounded retries, exponential backoff and rate limiting.

Design constraints (from the challenge):
- never retry infinitely
- respect ``Retry-After`` when the server provides it
- enforce a minimum request interval so the source is not hammered
- retry connection errors, timeouts, 429 and 5xx only
"""

import asyncio
import email.utils
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.logging import get_logger

logger = get_logger("jobpulse.ingestion.fetcher")

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class FetchError(Exception):
    """Base class for every fetch failure."""


class FetchTimeoutError(FetchError):
    """The source did not respond within the configured timeout."""


class FetchConnectionError(FetchError):
    """The source could not be reached (DNS, refused, reset)."""


class FetchHTTPError(FetchError):
    def __init__(
        self,
        status_code: int,
        message: str = "",
        retry_after: str | None = None,
        retries_exhausted: bool = True,
    ) -> None:
        self.status_code = status_code
        self.retry_after = retry_after
        self.retries_exhausted = retries_exhausted
        default = f"source returned HTTP {status_code}"
        if retry_after:
            default += f" (retry-after: {retry_after})"
        super().__init__(message or default)


@dataclass
class FetchResult:
    text: str
    status_code: int
    content_type: str | None = None
    retry_after: str | None = None


class HTTPFetcher:
    """A single shared client, so connection pooling and rate limiting work."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 30.0,
        max_retry_after_seconds: float = 60.0,
        minimum_request_interval_seconds: float = 5.0,
        user_agent: str = "JobPulse/1.0",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._base_backoff_seconds = base_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._max_retry_after_seconds = max_retry_after_seconds
        self._min_interval_seconds = minimum_request_interval_seconds
        self._user_agent = user_agent
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )
        self._owns_client = client is None
        self._last_request_at = 0.0

    async def fetch(self, url: str) -> FetchResult:
        attempt = 0
        while True:
            attempt += 1
            await self._respect_rate_limit()
            self._last_request_at = time.monotonic()

            try:
                response = await self._client.get(url)
            except httpx.TimeoutException as exc:
                if attempt > self._max_retries:
                    raise FetchTimeoutError(f"request timed out after {self._timeout_seconds}s") from exc
                await self._sleep_backoff(attempt)
                continue
            except httpx.TransportError as exc:
                if attempt > self._max_retries:
                    raise FetchConnectionError(f"connection error: {exc}") from exc
                await self._sleep_backoff(attempt)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt > self._max_retries:
                    retry_after = response.headers.get("retry-after")
                    raise FetchHTTPError(
                        response.status_code, retry_after=retry_after, retries_exhausted=True
                    )
                await self._sleep_after_rate_limit(response.headers.get("retry-after"), attempt)
                continue

            if response.status_code >= 400:
                raise FetchHTTPError(
                    response.status_code,
                    f"source returned HTTP {response.status_code}; not retrying",
                    retry_after=response.headers.get("retry-after"),
                    retries_exhausted=False,
                )

            return FetchResult(
                text=response.text,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                retry_after=response.headers.get("retry-after"),
            )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # -- helpers ---------------------------------------------------------------

    async def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _backoff_seconds(self, attempt: int) -> float:
        base = self._base_backoff_seconds * (2 ** (attempt - 1))
        delay = min(base, self._max_backoff_seconds)
        return delay * (0.5 + random.random() / 2)

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = self._backoff_seconds(attempt)
        logger.warning("fetch failed; retrying in %.1fs (attempt %d)", delay, attempt + 1)
        await asyncio.sleep(delay)

    async def _sleep_after_rate_limit(self, retry_after_header: str | None, attempt: int) -> None:
        delay = self._parse_retry_after(retry_after_header)
        if delay is None:
            delay = self._backoff_seconds(attempt)
        delay = min(delay, self._max_retry_after_seconds)
        logger.warning("rate-limited; waiting %.1fs before retry (attempt %d)", delay, attempt + 1)
        await asyncio.sleep(delay)

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return float(value.strip())
        except ValueError:
            pass
        try:
            retry_at = email.utils.parsedate_to_datetime(value)
        except (ValueError, TypeError, IndexError, OverflowError):
            return None
        if retry_at is None or retry_at.tzinfo is None:
            return None
        delta = retry_at - datetime.now(retry_at.tzinfo)
        return max(delta.total_seconds(), 0.0)