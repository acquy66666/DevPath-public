"""The real Google adapter, against a Google that runs on localhost.

Everything here exercises the production code path -- httpx posting to a token
endpoint, PyJWKClient fetching signing keys, PyJWT verifying an RS256 signature
-- with a stand-in server holding the other end. That is the point: a fake
injected higher up (as in tests/api/test_google_auth.py) proves the routes work
but would happily pass on a build where RS256 cannot be verified at all,
because PyJWT needs `cryptography` for that and it is an optional extra.
"""

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings
from app.services.google_oauth import GoogleAuthError, GoogleOAuth

CLIENT_ID = "client-id.apps.googleusercontent.com"
KEY_ID = "test-signing-key"

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks() -> dict[str, Any]:
    """What Google publishes at /oauth2/v3/certs, for our one test key."""
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(SIGNING_KEY.public_key()))
    return {"keys": [{**jwk, "kid": KEY_ID, "alg": "RS256", "use": "sig"}]}


def id_token(*, key: rsa.RSAPrivateKey = SIGNING_KEY, **overrides: Any) -> str:
    now = datetime.now(tz=UTC)
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "someone@gmail.com",
        "email_verified": True,
        "name": "Some One",
        "picture": "https://lh3.googleusercontent.com/a",
        "iat": now,
        "exp": now + timedelta(hours=1),
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": KEY_ID})


class FakeGoogleServer:
    """Serves the two endpoints the adapter talks to, on a real socket."""

    def __init__(self, token_response: dict | None, status_code: int = 200) -> None:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 — name fixed by BaseHTTPRequestHandler
                self._send(200, jwks())

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("content-length", 0))
                outer.token_requests.append(self.rfile.read(length).decode())
                self._send(outer.status_code, outer.token_response or {})

            def _send(self, status: int, body: dict) -> None:
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args: Any) -> None:
                """Quiet: the default handler prints every request to stderr."""

        self.token_response = token_response
        self.status_code = status_code
        self.token_requests: list[str] = []
        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeGoogleServer":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def client(self) -> GoogleOAuth:
        return GoogleOAuth(
            Settings(google_client_id=CLIENT_ID, google_client_secret="client-secret"),
            token_endpoint=f"{self.url}/token",
            jwks_uri=f"{self.url}/certs",
        )


async def test_a_valid_code_becomes_an_identity() -> None:
    with FakeGoogleServer({"id_token": id_token()}) as google:
        identity = await google.client().exchange_code(code="the-code")

    assert identity.sub == "1234567890"
    assert identity.email == "someone@gmail.com"
    assert identity.email_verified is True
    assert identity.full_name == "Some One"


async def test_the_exchange_sends_the_code_and_the_client_secret() -> None:
    """The secret is what makes the code worth anything, and it goes
    server-to-server -- never through the browser."""
    with FakeGoogleServer({"id_token": id_token()}) as google:
        await google.client().exchange_code(code="the-code")
        sent = google.token_requests[0]

    assert "code=the-code" in sent
    assert "client_secret=client-secret" in sent
    assert "grant_type=authorization_code" in sent


async def test_a_token_signed_with_another_key_is_refused() -> None:
    """The signature check is the whole reason to fetch Google's keys."""
    with FakeGoogleServer({"id_token": id_token(key=OTHER_KEY)}) as google:
        with pytest.raises(GoogleAuthError):
            await google.client().exchange_code(code="c")


async def test_a_token_for_another_audience_is_refused() -> None:
    """A valid Google token issued to a different app must not open this one."""
    with FakeGoogleServer({"id_token": id_token(aud="someone-elses-app")}) as google:
        with pytest.raises(GoogleAuthError):
            await google.client().exchange_code(code="c")


async def test_a_token_from_another_issuer_is_refused() -> None:
    with FakeGoogleServer({"id_token": id_token(iss="https://evil.example.com")}) as google:
        with pytest.raises(GoogleAuthError):
            await google.client().exchange_code(code="c")


async def test_an_expired_token_is_refused() -> None:
    expired = datetime.now(tz=UTC) - timedelta(minutes=5)
    with FakeGoogleServer({"id_token": id_token(exp=expired)}) as google:
        with pytest.raises(GoogleAuthError):
            await google.client().exchange_code(code="c")


async def test_a_rejected_code_is_refused() -> None:
    """Google answers 400 for a code that is stale, already used, or forged."""
    with FakeGoogleServer({"error": "invalid_grant"}, status_code=400) as google:
        with pytest.raises(GoogleAuthError):
            await google.client().exchange_code(code="already-used")


async def test_a_response_without_an_id_token_is_refused() -> None:
    with FakeGoogleServer({"access_token": "ya29.a0"}) as google:
        with pytest.raises(GoogleAuthError):
            await google.client().exchange_code(code="c")


async def test_an_unreachable_google_is_an_error_not_a_hang() -> None:
    with FakeGoogleServer({"id_token": id_token()}) as google:
        client = google.client()
    # Server is down now: the port is closed, the connection is refused.

    with pytest.raises(GoogleAuthError):
        await client.exchange_code(code="c")
