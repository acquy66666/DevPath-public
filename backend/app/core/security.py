"""Password hashing and token issuing.

bcrypt directly rather than passlib: passlib is unmaintained and breaks
against bcrypt 4.x.

Two different kinds of token live here and they are deliberately not the same
shape:

* the **access token** is a short-lived signed JWT, verified with nothing but
  the secret -- no database round trip on every request;
* the **refresh token** is an opaque random string. It is long-lived and can be
  revoked, and a JWT cannot be revoked without a lookup anyway, so there is no
  reason to make it one. Only its SHA-256 hash reaches the database
  (see `docs/database-design.md`, `refresh_tokens`).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt hashes at most 72 bytes and silently ignores the rest, which would
# let two different long passwords open the same account.
MAX_PASSWORD_BYTES = 72

JWT_ALGORITHM = "HS256"

# 48 bytes -> 64 url-safe characters. Well past guessing range, and short
# enough to sit in a cookie without thought.
REFRESH_TOKEN_BYTES = 48


class TokenError(Exception):
    """An access token was missing, malformed, expired, or wrongly signed.

    One exception for every failure mode on purpose: the caller turns this into
    a single 401 and never tells an attacker which part was wrong.
    """


@dataclass(frozen=True)
class AccessTokenPayload:
    user_id: uuid.UUID
    role: str


def hash_password(plain: str) -> str:
    """Return a salted bcrypt hash. Raises ValueError if the password is too long."""
    encoded = plain.encode("utf-8")

    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password is {len(encoded)} bytes; bcrypt accepts at most "
            f"{MAX_PASSWORD_BYTES}."
        )

    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Check a password against a stored hash. Never raises -- a bad input is a bad password."""
    encoded = plain.encode("utf-8")

    # hash_password refused to hash anything this long, so no stored hash can
    # possibly match it. Falling through to bcrypt would compare a truncation.
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False

    try:
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except ValueError:
        # Corrupted or hand-edited hash: a failed login, not a 500.
        return False


def create_access_token(
    user_id: uuid.UUID,
    role: str,
    *,
    expires_in: timedelta | None = None,
) -> str:
    """Sign a short-lived access token carrying the user's id and role."""
    settings = get_settings()
    ttl = expires_in if expires_in is not None else timedelta(
        minutes=settings.access_token_ttl_minutes
    )
    issued_at = datetime.now(tz=UTC)

    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "iat": issued_at,
            "exp": issued_at + ttl,
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> AccessTokenPayload:
    """Verify signature and expiry. Raises TokenError on anything unusable.

    `algorithms` is pinned to one value: without it a token could name its own
    algorithm and `alg: none` would verify against an empty signature.
    """
    settings = get_settings()

    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    try:
        return AccessTokenPayload(user_id=uuid.UUID(claims["sub"]), role=claims["role"])
    except (KeyError, ValueError, TypeError) as exc:
        # Correctly signed but not shaped like one of ours -- an old token from
        # before a claim change, say.
        raise TokenError("Access token is missing the expected claims") from exc


def generate_refresh_token() -> str:
    """A fresh opaque refresh token. Returned to the client once, never stored raw."""
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(raw: str) -> str:
    """SHA-256 hex of a refresh token -- exactly the 64 chars the column holds.

    Plain SHA-256 rather than bcrypt: the token is 384 bits of `secrets`
    randomness, so there is no weak password to slow a guesser down against,
    and every refresh would otherwise pay for a bcrypt round.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
