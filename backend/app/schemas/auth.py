"""Request and response bodies for /api/v1/auth."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES

# Long enough to be worth bcrypt, short enough not to push people towards
# reusing something they already have written down.
MIN_PASSWORD_LENGTH = 8

# users.full_name is VARCHAR(150).
FULL_NAME_MAX_LENGTH = 150


def password_fits_bcrypt(value: str) -> str:
    """Refuse anything bcrypt would silently truncate.

    Shared with the change-password form: one rule, one place, so the two can
    never drift into accepting different passwords.
    """
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Mật khẩu tối đa {MAX_PASSWORD_BYTES} byte (dấu tiếng Việt tính 2–3 byte)"
        )
    return value


def _normalise_email(value: str) -> str:
    """Trim and lowercase before EmailStr sees it.

    The unique index compares raw strings, so `A@x.com` and `a@x.com` would
    otherwise be two accounts.
    """
    return value.strip().lower() if isinstance(value, str) else value


class _EmailIn(BaseModel):
    email: EmailStr

    _normalise = field_validator("email", mode="before")(_normalise_email)


class RegisterIn(_EmailIn):
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    full_name: str = Field(min_length=1, max_length=FULL_NAME_MAX_LENGTH)

    _fits_bcrypt = field_validator("password")(password_fits_bcrypt)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Họ tên không được để trống")
        return stripped


class LoginIn(_EmailIn):
    # No length rule: an old account may predate any rule we add later, and the
    # answer to a wrong password is 401, not 422.
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    """Public shape of a user. Never carries password_hash or oauth_sub."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    avatar_url: str | None
    created_at: datetime
    # Whether a password can be used to sign in -- not the password, and not
    # whether one is any good.
    has_password: bool


class TokenOut(BaseModel):
    """The refresh token is deliberately absent -- it travels only in the cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
