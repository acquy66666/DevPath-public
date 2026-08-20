from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"]
    assert body["env"]


async def test_unknown_route_uses_the_shared_error_envelope(client: AsyncClient) -> None:
    """Every error must come back as {"detail": {"code", "message"}}."""
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "NOT_FOUND"
    assert detail["message"]
