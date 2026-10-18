"""No NUL character gets past the edge of the API.

Postgres text and varchar cannot hold `\\0`, and cannot be *compared* with one
either: an INSERT, an UPDATE and a plain SELECT whose parameter holds it all
fail with asyncpg's CharacterNotInRepertoireError (jsonb refuses it too, with
another SQLSTATE). Left alone that is a 500 -- on signing up, with no account
needed, on a catalogue search, on a slug in the URL. Measured 16/10 in
`docs/report/assets/phase-6/nul-everywhere.txt`.

So it is refused where a request comes in, by one rule instead of a check in
every schema: `refuse_nul` is a dependency of the whole app (`main.py`), which
makes it the first thing every route depends on. It looks at the path, the
query string and the JSON body FastAPI has already parsed, and answers a NUL in
any of them with the 422 every validation error gets. Because it runs before
the database session, the rate limiter and authentication, a refused request
has cost nothing. That part was measured too: before, a question to the course
assistant with a NUL in it paid for an embedding and a Gemini answer, streamed
the answer with HTTP 200, and only then failed to store it.

Not looked at: headers, which the HTTP server refuses with a 400 when a line
holds a NUL, before the app sees them; and cookies, of which the API reads two
-- a refresh token that is hashed before any query, an OAuth state that is
compared and never stored. A cookie set by some other page on the domain is
not the client's choice, so refusing on it would break requests for nothing.
"""

from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from starlette.requests import HTTPConnection, Request

NUL = "\x00"
ERROR_TYPE = "string_contains_nul"
MESSAGE = "Không được chứa ký tự NUL (\\0)"

Location = tuple[str | int, ...]


def find_nul(value: object) -> Location | None:
    """Where the first string holding a NUL sits inside a parsed JSON value --
    `("answers", 2)` -- or None when there is none. Keys count as strings; the
    first is the first in document order.

    A loop, not recursion: Python's json module parses documents nested deeper
    than Python recursion can walk, and a RecursionError here is a 500. For
    the same reason the location is kept as a chain of (parent, step) pairs
    and only spelt out once something is found.
    """
    pending: list[tuple[tuple | None, object]] = [(None, value)]
    while pending:
        trail, item = pending.pop()
        if isinstance(item, str):
            if NUL in item:
                return _spell(trail)
        elif isinstance(item, dict):
            # Pushed backwards so they come off in document order, each key
            # just before its own value.
            for key, child in reversed(item.items()):
                step = (trail, key)
                pending.append((step, child))
                pending.append((step, key))
        elif isinstance(item, list):
            for index in range(len(item) - 1, -1, -1):
                pending.append(((trail, index), item[index]))
    return None


def _spell(trail: tuple | None) -> Location:
    steps: list[str | int] = []
    while trail is not None:
        trail, step = trail
        steps.append(step)
    return tuple(reversed(steps))


def _is_json(content_type: str | None) -> bool:
    """The test FastAPI applies before it parses a body as JSON. Without a
    Content-Type it does not parse at all (strict content type)."""
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    maintype, _, subtype = media_type.partition("/")
    return maintype == "application" and (subtype == "json" or subtype.endswith("+json"))


async def _json_body(request: Request) -> object:
    """The body FastAPI parsed for this route, or None if it parsed none.

    A route that reads no body never has one parsed, so a NUL in it reaches
    nothing and is not judged. Starlette caches the parsed body on the
    request: this is the same object the route validates, not a second parse.
    """
    route = request.scope.get("route")
    if getattr(route, "body_field", None) is None:
        return None
    if not _is_json(request.headers.get("content-type")) or not await request.body():
        return None
    try:
        return await request.json()
    except ValueError:
        return None  # FastAPI has already answered a body it could not parse


async def refuse_nul(connection: HTTPConnection) -> None:
    """The rule, as a dependency of the whole app. See the module docstring."""
    found: Location | None = None
    for name, value in connection.path_params.items():
        if isinstance(value, str) and NUL in value:
            found = ("path", name)
            break
    if found is None:
        for name, value in connection.query_params.multi_items():
            if NUL in name or NUL in value:
                found = ("query", name)
                break
    if found is None and isinstance(connection, Request):
        location = find_nul(await _json_body(connection))
        if location is not None:
            found = ("body", *location)
    if found is None:
        return

    errors = [{"type": ERROR_TYPE, "loc": found, "msg": MESSAGE}]
    if isinstance(connection, Request):
        raise RequestValidationError(errors)
    # A WebSocket handshake: FastAPI closes it with 1008, as it does one whose
    # parameters fail validation.
    raise WebSocketRequestValidationError(errors)
