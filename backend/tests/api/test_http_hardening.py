"""What the API tells a browser about who may call it, and what it shows strangers.

CORS here guards one thing that matters: the API is called with credentials
(the refresh cookie rides along), so an origin the list does not name must get
no `Access-Control-Allow-Origin` at all -- not a reflected one, not a wildcard.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app

ALLOWED = "http://localhost:3000"
FOREIGN = "https://evil.example"


def preflight(origin: str, method: str = "PATCH", headers: str = "authorization,content-type"):
    return {
        "Origin": origin,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": headers,
    }


async def test_the_frontend_origin_may_call_with_credentials(client: AsyncClient) -> None:
    response = await client.options("/api/v1/courses/me", headers=preflight(ALLOWED))

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_a_foreign_origin_is_not_let_in(client: AsyncClient) -> None:
    response = await client.options("/api/v1/courses/me", headers=preflight(FOREIGN))

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_a_foreign_origin_gets_no_grant_on_a_simple_request_either(
    client: AsyncClient,
) -> None:
    """No preflight for a GET: the browser sends it and decides from the
    answer's headers whether the page may read it."""
    response = await client.get(
        "/api/v1/health", headers={"Origin": FOREIGN, "Cookie": "devpath_refresh=x"}
    )

    assert "access-control-allow-origin" not in response.headers


async def test_only_the_headers_the_frontend_sends_are_allowed(client: AsyncClient) -> None:
    """With credentials on, `allow_headers=["*"]` reflects whatever is asked
    for. The list is what `lib/api/client.ts` actually sends."""
    response = await client.options(
        "/api/v1/courses/me", headers=preflight(ALLOWED, headers="x-made-up")
    )

    assert response.status_code == 400


@pytest.fixture
def production_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(get_settings(), "env", "production")
    return create_app()


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
async def test_production_does_not_publish_the_api_schema(
    production_app: FastAPI, path: str
) -> None:
    """The schema is a map of every route and every field, handed to whoever
    asks. Useful while building; on the public server it only helps somebody
    looking for the route that was forgotten."""
    transport = ASGITransport(app=production_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 404


async def test_development_still_has_the_schema(client: AsyncClient) -> None:
    assert (await client.get("/openapi.json")).status_code == 200
