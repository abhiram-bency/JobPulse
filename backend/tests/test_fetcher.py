import httpx
import pytest

from app.ingestion.fetcher import (
    FetchConnectionError,
    FetchError,
    FetchHTTPError,
    FetchTimeoutError,
    HTTPFetcher,
)
from tests.fixtures.rss import DEFAULT_FEED


def make_fetcher(queue, *, max_retries=3):
    client = httpx.AsyncClient(transport=httpx.MockTransport(queue.handler))
    return HTTPFetcher(
        client=client,
        minimum_request_interval_seconds=0.0,
        base_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
        max_retries=max_retries,
        timeout_seconds=1.0,
    )


@pytest.mark.asyncio
async def test_successful_fetch(request_queue):
    fetcher = make_fetcher(request_queue)
    result = await fetcher.fetch("https://example.test/rss")
    assert result.status_code == 200
    assert result.text == DEFAULT_FEED


@pytest.mark.asyncio
async def test_429_then_success_retries(request_queue):
    request_queue.enqueue(httpx.Response(429, text="rate limited", headers={"retry-after": "0"}))
    fetcher = make_fetcher(request_queue, max_retries=2)
    result = await fetcher.fetch("https://example.test/rss")
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_500_then_success_retries(request_queue):
    request_queue.enqueue(httpx.Response(500, text="oops"))
    fetcher = make_fetcher(request_queue, max_retries=2)
    result = await fetcher.fetch("https://example.test/rss")
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_429_exhausted_raises_http_error(request_queue):
    for _ in range(5):
        request_queue.enqueue(httpx.Response(429, text="rate limited"))
    fetcher = make_fetcher(request_queue, max_retries=2)
    with pytest.raises(FetchHTTPError) as excinfo:
        await fetcher.fetch("https://example.test/rss")
    assert excinfo.value.status_code == 429
    assert excinfo.value.retries_exhausted is True


@pytest.mark.asyncio
async def test_404_not_retried(request_queue):
    request_queue.enqueue(httpx.Response(404, text="missing"))
    request_queue.enqueue(httpx.Response(200, text=DEFAULT_FEED))
    fetcher = make_fetcher(request_queue, max_retries=2)
    with pytest.raises(FetchHTTPError) as excinfo:
        await fetcher.fetch("https://example.test/rss")
    assert excinfo.value.status_code == 404
    assert excinfo.value.retries_exhausted is False


@pytest.mark.asyncio
async def test_timeout_exhausted(request_queue):
    def boom(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    fetcher = HTTPFetcher(
        client=client,
        max_retries=1,
        base_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
        minimum_request_interval_seconds=0.0,
        timeout_seconds=1.0,
    )
    with pytest.raises(FetchTimeoutError):
        await fetcher.fetch("https://example.test/rss")


@pytest.mark.asyncio
async def test_connection_error_exhausted(request_queue):
    def boom(request):
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    fetcher = HTTPFetcher(
        client=client,
        max_retries=1,
        base_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
        minimum_request_interval_seconds=0.0,
        timeout_seconds=1.0,
    )
    with pytest.raises(FetchConnectionError):
        await fetcher.fetch("https://example.test/rss")


@pytest.mark.asyncio
async def test_timeout_then_success(request_queue):
    attempts = {"count": 0}

    def sometimes(request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, text=DEFAULT_FEED)

    client = httpx.AsyncClient(transport=httpx.MockTransport(sometimes))
    fetcher = HTTPFetcher(
        client=client,
        max_retries=2,
        base_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
        minimum_request_interval_seconds=0.0,
        timeout_seconds=1.0,
    )
    result = await fetcher.fetch("https://example.test/rss")
    assert result.status_code == 200
    assert attempts["count"] == 2