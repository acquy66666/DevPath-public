"""Request bodies for the endpoints a signed-in person aims at their own account."""

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import (
    FULL_NAME_MAX_LENGTH,
    MIN_PASSWORD_LENGTH,
    password_fits_bcrypt,
)


class ProfileUpdateIn(BaseModel):
    """The name is the only editable field for now.

    Email is deliberately absent: a new address has to be proven before it can
    be trusted, which is a flow of its own rather than a field in this form.
    Role is absent for a blunter reason -- nobody promotes themselves by
    editing their profile.
    """

    full_name: str = Field(min_length=1, max_length=FULL_NAME_MAX_LENGTH)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Họ tên không được để trống")
        return stripped


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)

    _fits_bcrypt = field_validator("new_password")(password_fits_bcrypt)
