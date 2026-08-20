"""The HTTP half of Google sign-in: authorization URL in, identity out.

Kept behind a Protocol so the routes never touch httpx directly and the tests
never touch Google: `tests/api/test_google_auth.py` swaps in a fake through
FastAPI's dependency override.

Flow (authorization code, backend as a confidential client):

    browser --> /auth/google/authorize --302--> accounts.google.com
    browser --> /auth/google/callback?code=... (after the user consents)
    backend --> oauth2.googleapis.com/token   (code + client secret)
    backend <-- id_token (a JWT signed by Google)

The client secret never leaves the backend, and the code is exchanged
server-to-server, so the browser never handles anything reusable.
"""

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import status

from app.core.config import Settings, get_settings
from app.core.exceptions import DomainError

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
# Google signs with either, and rotates which one appears in `iss`.
ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# openid gets the id_token at all; the other two fill in who the person is.
SCOPES = ("openid", "email", "profile")

REQUEST_TIMEOUT_SECONDS = 10.0


class GoogleAuthError(DomainError):
    """Google said no, or said something we could not verify."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "GOOGLE_AUTH_FAILED"


class GoogleNotConfiguredError(DomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "GOOGLE_OAUTH_NOT_CONFIGURED"


@dataclass(frozen=True)
class GoogleIdentity:
    """Who Google says this is. `sub` is the only field that never changes."""

    sub: str
    email: str
    email_verified: bool
    full_name: str | None
    picture: str | None


class GoogleOAuthClient(Protocol):
    def authorization_url(self, *, state: str) -> str: ...

    async def exchange_code(self, *, code: str) -> GoogleIdentity: ...


def identity_from_claims(claims: dict) -> GoogleIdentity:
    """Read an id_token payload. Raises GoogleAuthError if it is unusable."""
    sub = claims.get("sub")
    email = claims.get("email")

    if not sub or not email:
        raise GoogleAuthError("Google không trả về định danh hợp lệ")

    return GoogleIdentity(
        sub=str(sub),
        email=str(email),
        # Absent means unverified: this claim decides whether we are allowed to
        # merge into an existing account, so nothing is assumed in its absence.
        email_verified=claims.get("email_verified") is True,
        full_name=claims.get("name") or None,
        picture=claims.get("picture") or None,
    )


class GoogleOAuth:
    """Real client. One per process -- it caches Google's signing keys."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        token_endpoint: str = TOKEN_ENDPOINT,
        jwks_uri: str = JWKS_URI,
    ) -> None:
        self._settings = settings or get_settings()
        self._token_endpoint = token_endpoint
        self._jwks_client = jwt.PyJWKClient(jwks_uri, cache_keys=True)

    def authorization_url(self, *, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._settings.google_client_id,
                "redirect_uri": self._settings.google_redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "state": state,
                # Ask for the account chooser rather than silently reusing
                # whichever Google account the browser happens to be in.
                "prompt": "select_account",
            }
        )
        return f"{AUTHORIZATION_ENDPOINT}?{query}"

    async def exchange_code(self, *, code: str) -> GoogleIdentity:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(
                    self._token_endpoint,
                    data={
                        "code": code,
                        "client_id": self._settings.google_client_id,
                        "client_secret": self._settings.google_client_secret,
                        "redirect_uri": self._settings.google_redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
            except httpx.HTTPError as exc:
                raise GoogleAuthError("Không gọi được Google để đổi mã") from exc

        if response.status_code != status.HTTP_200_OK:
            # A used, expired, or forged code lands here.
            raise GoogleAuthError("Google từ chối mã đăng nhập")

        id_token = response.json().get("id_token")
        if not id_token:
            raise GoogleAuthError("Google không trả về id_token")

        return identity_from_claims(await self._verify(id_token))

    async def _verify(self, id_token: str) -> dict:
        """Check Google's signature, audience and issuer before believing anything.

        The token arrived over TLS straight from Google, so this is belt and
        braces -- but the alternative is trusting a JWT because of where it was
        found, which is the mistake behind a long line of auth bugs.
        """
        try:
            # PyJWKClient fetches over the network with urllib, which blocks.
            signing_key = await asyncio.to_thread(
                self._jwks_client.get_signing_key_from_jwt, id_token
            )
            return jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.google_client_id,
                issuer=list(ISSUERS),
            )
        except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
            raise GoogleAuthError("id_token của Google không hợp lệ") from exc


@lru_cache
def _shared_client() -> GoogleOAuth:
    """One client for the process, so Google's signing keys are fetched once."""
    return GoogleOAuth(get_settings())


def get_google_oauth_client() -> GoogleOAuthClient:
    """FastAPI dependency. Tests override this; nothing else constructs a client."""
    if not get_settings().google_oauth_enabled:
        raise GoogleNotConfiguredError(
            "Đăng nhập Google chưa được cấu hình trên máy chủ này"
        )
    return _shared_client()
