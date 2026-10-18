"""A NUL character in anything a client sends is a 422, on every route.

Postgres cannot store `\\0` in a text or varchar column, and cannot compare
one either: an INSERT, an UPDATE *and* a SELECT whose parameter holds it all
fail with asyncpg's CharacterNotInRepertoireError. Before 17/10 that was a 500
on every form -- signing up included, no account needed -- and on a search or a
slug in the URL (`docs/report/assets/phase-6/nul-everywhere.txt`).

The rule lives in one place, `app.core.no_nul.refuse_nul`: an app-wide
dependency, the first thing every route depends on. This file holds it to
every route at once, the way `test_authorization_matrix` holds authorization:

* every route that reads a body refuses a NUL in it,
* every route refuses a NUL in its query string and in its path,
* and it does so **before anything else** -- the database, the rate limiter and
  authentication are made to fail the test if they are reached. So a refused
  request has cost nothing: no row, no counter, no paid model call.

A route added tomorrow is in the sweep the day it is written.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI, params
from fastapi.routing import APIRoute, APIWebSocketRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.no_nul import find_nul
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models import User
from app.services.rate_limit import get_rate_limiter

API = "/api/v1"
NUL_ERROR = "string_contains_nul"


def served_routes(app: FastAPI) -> dict[str, APIRoute | APIWebSocketRoute]:
    """`METHOD /path` -> route, for every route the app serves under /api/v1.

    The path is the one under `API`: FastAPI keeps the routes of an included
    router un-prefixed (`test_authorization_matrix` walks them the same way).
    """

    def walk(routes):
        for route in routes:
            if isinstance(route, APIRoute | APIWebSocketRoute):
                yield route
            elif hasattr(route, "original_router"):
                yield from walk(route.original_router.routes)

    found = {}
    for route in walk(app.routes):
        for method in getattr(route, "methods", None) or {"WS"}:
            found[f"{method} {route.path.removeprefix(API)}"] = route
    return found


ROUTES = served_routes(create_app())
HTTP_ROUTES = sorted(key for key, route in ROUTES.items() if isinstance(route, APIRoute))
BODY_ROUTES = sorted(key for key in HTTP_ROUTES if ROUTES[key].body_field is not None)
PATH_ROUTES = sorted(key for key in HTTP_ROUTES if "{" in key)


def with_ids(path: str, value: str | None = None) -> str:
    """The URL of `path`, every `{param}` filled with `value` or with a fresh
    well-formed id."""
    return API + re.sub(r"\{\w+\}", lambda _: value or str(uuid.uuid4()), path)


def refusal(response) -> dict:
    """The one error of a NUL refusal, after checking it is one."""
    assert response.status_code == 422, response.text[:300]
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR", detail
    errors = detail["errors"]
    assert len(errors) == 1 and errors[0]["type"] == NUL_ERROR, (
        f"refused, but not by the NUL rule: {errors}"
    )
    return errors[0]


# --- the walker ---------------------------------------------------------------


def test_a_value_without_nul_has_no_location() -> None:
    for value in (None, True, 0, 1.5, "", "chữ thường", [], {}, {"a": ["b", {"c": 1}]}):
        assert find_nul(value) is None, value


def test_the_location_is_where_a_client_would_look() -> None:
    assert find_nul("a\x00") == ()
    assert find_nul({"a": [1, {"b": "x\x00y"}]}) == ("a", 1, "b")
    assert find_nul([0, "", "\x00"]) == (2,)


def test_a_key_counts_as_much_as_a_value() -> None:
    """An object key can end up stored too -- a JSONB payload keeps them."""
    assert find_nul({"ok": "", "k\x00": 1}) == ("k\x00",)


def test_the_first_nul_in_document_order_is_the_one_reported() -> None:
    assert find_nul(["\x00a", "\x00b"]) == (0,)
    assert find_nul({"first": {"x": "\x00"}, "second": "\x00"}) == ("first", "x")


def test_a_backslash_followed_by_u0000_is_six_ordinary_characters() -> None:
    """The JSON text `"\\\\u0000"` is a backslash and five letters -- legal text,
    nothing to refuse. Only `"\\u0000"` decodes to the character itself."""
    assert find_nul(json.loads('{"a": "\\\\u0000"}')) is None
    assert find_nul(json.loads('{"a": "\\u0000"}')) == ("a",)


def test_depth_does_not_matter() -> None:
    """Python's json module parses deeper documents than Python recursion
    allows to walk: a recursive walker would turn a deep body into a 500."""
    value: object = "\x00"
    for _ in range(100_000):
        value = [value]
    assert find_nul(value) == (0,) * 100_000


# --- the sweep ----------------------------------------------------------------


def test_the_sweep_sees_the_routes_it_should() -> None:
    """A walker that found nothing would make every sweep below pass."""
    assert "POST /auth/register" in BODY_ROUTES
    assert "PATCH /users/me" in BODY_ROUTES
    assert "GET /courses/by-slug/{slug}" in PATH_ROUTES
    assert len(BODY_ROUTES) > 50 and len(HTTP_ROUTES) > 150


@pytest.mark.parametrize("key", BODY_ROUTES)
def test_every_body_is_json(key: str) -> None:
    """The rule reads the JSON body FastAPI has already parsed. A form body
    would not be read: a route that takes one has to teach `refuse_nul` first."""
    assert not isinstance(ROUTES[key].body_field.field_info, params.Form), key


@pytest.fixture
async def guarded_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """A client for an app whose database and rate limiter fail the test.

    The NUL rule has to answer before either is reached: that is what makes a
    refused request free. Nobody signs in either -- the rule comes before
    authentication, so the refusal is the same for everybody.
    """

    async def no_database():
        raise AssertionError("the request reached the database")
        yield  # pragma: no cover

    def no_rate_limiter():
        raise AssertionError("the request reached the rate limiter")

    app.dependency_overrides[get_db] = no_database
    app.dependency_overrides[get_rate_limiter] = no_rate_limiter
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("key", BODY_ROUTES)
async def test_every_route_that_reads_a_body_refuses_a_nul_in_it(
    guarded_client: AsyncClient, key: str
) -> None:
    method, path = key.split(" ", 1)
    response = await guarded_client.request(method, with_ids(path), json={"probe": "a\x00b"})

    assert refusal(response)["loc"] == ["body", "probe"]


@pytest.mark.parametrize("key", HTTP_ROUTES)
async def test_every_route_refuses_a_nul_in_its_query_string(
    guarded_client: AsyncClient, key: str
) -> None:
    method, path = key.split(" ", 1)
    response = await guarded_client.request(method, with_ids(path) + "?probe=a%00b")

    assert refusal(response)["loc"] == ["query", "probe"]


@pytest.mark.parametrize("key", PATH_ROUTES)
async def test_every_route_refuses_a_nul_in_its_path(guarded_client: AsyncClient, key: str) -> None:
    method, path = key.split(" ", 1)
    response = await guarded_client.request(method, with_ids(path, "a%00b"))

    assert refusal(response)["loc"][0] == "path"


async def test_the_websocket_refuses_a_nul_before_its_handshake(app: FastAPI) -> None:
    """The one WebSocket route has no body, but it has a path and a query
    string. A refused handshake closes with 1008, as FastAPI closes one whose
    parameters fail validation -- not 4401, which is the handler's own answer
    to a stranger, reached only once the rule has let the request through.

    Spoken in plain ASGI: httpx has no WebSocket client, and Starlette's
    TestClient is deprecated with the httpx this project locks."""
    path = f"{API}/submissions/{uuid.uuid4()}/events"
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"probe=a%00b",
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
        "subprotocols": [],
    }
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "websocket.connect"}

    async def send(message: dict) -> None:
        sent.append(message)

    await app(scope, receive, send)

    assert [message["type"] for message in sent] == ["websocket.close"], sent
    assert sent[0]["code"] == 1008


async def test_a_route_that_reads_no_body_does_not_judge_one(
    guarded_client: AsyncClient,
) -> None:
    """Nothing reads it, so nothing stores it: no reason to parse it either."""
    response = await guarded_client.request("GET", f"{API}/health", json={"probe": "a\x00b"})

    assert response.status_code == 200, response.text


# --- through to the database ----------------------------------------------------


async def test_signing_up_with_a_nul_is_a_422_and_creates_nobody(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The case measured on 16/10: a 500, open to anybody with no account."""
    email = "nul-dang-ky@example.com"
    response = await api_client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "mật-khẩu-đủ-dài", "full_name": "Thử\x00 NUL"},
    )

    assert refusal(response)["loc"] == ["body", "full_name"]
    assert await db_session.scalar(select(User).where(User.email == email)) is None


async def test_a_nul_in_a_profile_edit_changes_nothing(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user = User(
        email="nul-ho-so@example.com",
        full_name="Học Viên A",
        password_hash=hash_password("mật-khẩu-đủ-dài"),
    )
    db_session.add(user)
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}

    response = await api_client.patch(
        f"{API}/users/me", json={"full_name": "Tên\x00"}, headers=headers
    )

    assert refusal(response)["loc"] == ["body", "full_name"]
    await db_session.refresh(user)
    assert user.full_name == "Học Viên A"


async def test_a_backslash_u0000_is_kept_as_typed(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Somebody writing about JSON escapes may well type `\\u0000`. That is six
    characters a text column holds without complaint, and they stay."""
    typed = "Gạch chéo \\u0000 thật"
    response = await api_client.post(
        f"{API}/auth/register",
        json={
            "email": "nul-gach-cheo@example.com",
            "password": "mật-khẩu-đủ-dài",
            "full_name": typed,
        },
    )

    assert response.status_code == 201, response.text
    user = await db_session.scalar(select(User).where(User.email == "nul-gach-cheo@example.com"))
    assert user.full_name == typed and "\x00" not in user.full_name
