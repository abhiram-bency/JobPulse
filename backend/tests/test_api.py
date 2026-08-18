import httpx


def _post_sync(client, request_queue):
    request_queue.clear()
    request_queue.enqueue(httpx.Response(200, text=_seed_feed()))
    response = client.post("/api/v1/sync")
    assert response.status_code == 200
    return response.json()


def _seed_feed():
    from tests.fixtures.rss import DEFAULT_FEED

    return DEFAULT_FEED


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["app"] == "JobPulse"
    assert len(body["sources"]) == 1
    assert body["sources"][0]["name"] == "Himalayas RSS"


def test_sources(client):
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    sources = response.json()
    assert len(sources) == 1
    assert sources[0]["enabled"] is True


def test_jobs_empty_then_populated(client, request_queue):
    empty = client.get("/api/v1/jobs")
    assert empty.status_code == 200
    assert empty.json()["total"] == 0

    _post_sync(client, request_queue)

    listing = client.get("/api/v1/jobs")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert {job["title"] for job in body["items"]} == {
        "Python Backend Engineer",
        "Frontend Developer",
    }


def test_get_single_job(client, request_queue):
    _post_sync(client, request_queue)
    job_id = client.get("/api/v1/jobs").json()["items"][0]["id"]
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["id"] == job_id
    missing = client.get("/api/v1/jobs/999999")
    assert missing.status_code == 404


def test_jobs_search_and_filter(client, request_queue):
    _post_sync(client, request_queue)

    search = client.get("/api/v1/jobs", params={"search": "frontend"})
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["title"] == "Frontend Developer"

    location = client.get("/api/v1/jobs", params={"location": "Remote"})
    assert location.json()["total"] == 1

    company = client.get("/api/v1/jobs", params={"company": "acme"})
    assert company.json()["total"] == 1
    assert company.json()["items"][0]["company"] == "Acme"


def test_jobs_pagination(client, request_queue):
    _post_sync(client, request_queue)
    page = client.get("/api/v1/jobs", params={"page": 1, "page_size": 1})
    body = page.json()
    assert body["page"] == 1
    assert len(body["items"]) == 1
    assert body["total"] == 2


def test_sync_runs_endpoints(client, request_queue):
    _post_sync(client, request_queue)
    runs = client.get("/api/v1/sync-runs")
    assert runs.status_code == 200
    assert runs.json()["total"] == 1

    run_id = runs.json()["items"][0]["id"]
    detail = client.get(f"/api/v1/sync-runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "success"


def test_sync_failure_response(client, request_queue):
    request_queue.clear()
    for _ in range(5):
        request_queue.enqueue(httpx.Response(429, text="rate limited"))
    response = client.post("/api/v1/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "429" in body["error_message"]

    # jobs are not fabricated on failure
    assert client.get("/api/v1/jobs").json()["total"] == 0


def test_unknown_source_sync_404(client):
    response = client.post("/api/v1/sync", json={"source_id": 999})
    assert response.status_code == 404