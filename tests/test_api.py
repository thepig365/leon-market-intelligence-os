import asyncio

import httpx

from lmio.main import DASHBOARD_PAGES, app


def request(method: str, path: str) -> httpx.Response:
    async def perform() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path)

    return asyncio.run(perform())


def test_health_and_dashboard_are_readable() -> None:
    response = request("GET", "/health")
    assert response.status_code == 200
    assert response.json()["can_trade"] is False

    dashboard = request("GET", "/")
    assert dashboard.status_code == 200
    assert "不执行交易" in dashboard.text


def test_all_dashboard_pages_exist() -> None:
    for page in DASHBOARD_PAGES:
        response = request("GET", f"/dashboard/{page}")
        assert response.status_code == 200, page


def test_mutating_api_is_closed_without_admin_key() -> None:
    response = request("POST", "/api/v1/demo/run")

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_read_only_research_api_surface_is_available() -> None:
    paths = (
        "/api/v1/candidates",
        "/api/v1/research",
        "/api/v1/news",
        "/api/v1/ownership",
        "/api/v1/plans",
        "/api/v1/signals",
        "/api/v1/performance",
        "/api/v1/watchlists",
    )

    for path in paths:
        response = request("GET", path)
        assert response.status_code == 200, path


def test_feedback_write_is_protected() -> None:
    response = request(
        "POST",
        "/api/v1/feedback",
    )

    assert response.status_code == 503
