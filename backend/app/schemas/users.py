"""Request bodies for the endpoints a signed-in person aims at their own account."""

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import (
    FULL_NAME_MAX_LENGTH,
    MIN_PASSWORD_LENGTH,
    password_fits_bcrypt,
)
from app.services.storage import (
    ALLOWED_IMAGE_TYPES,
    FILENAME_MAX_LENGTH,
    MAX_AVATAR_BYTES,
)

# Long enough for any key this app mints, short enough that a forged one
# cannot be used to push a novel through the validator.
STORAGE_KEY_MAX_LENGTH = 512


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

class AvatarUploadIn(BaseModel):
    """The browser describes the picture; the backend decides where it may go.

    The size is declared rather than measured, exactly as for a video: the
    bytes go straight to the bucket and never pass through here. It is worth
    checking anyway -- refusing a 40 MB photo now is kinder than refusing it
    after the upload.
    """

    filename: str = Field(min_length=1, max_length=FILENAME_MAX_LENGTH)
    content_type: str
    size_bytes: int = Field(gt=0)

    @field_validator("content_type")
    @classmethod
    def only_image_types(cls, value: str) -> str:
        # Browsers append charset parameters to some types; compare the bare type.
        bare = value.split(";")[0].strip().lower()
        if bare not in ALLOWED_IMAGE_TYPES:
            allowed = ", ".join(ALLOWED_IMAGE_TYPES)
            raise ValueError(f"Định dạng ảnh không được hỗ trợ. Chấp nhận: {allowed}")
        return bare

    @field_validator("size_bytes")
    @classmethod
    def within_limit(cls, value: int) -> int:
        if value > MAX_AVATAR_BYTES:
            megabytes = MAX_AVATAR_BYTES // (1024 * 1024)
            raise ValueError(f"Ảnh đại diện tối đa {megabytes} MB")
        return value


class AvatarUploadTicket(BaseModel):
    """Everything the browser needs to put the picture in the bucket itself.

    `upload_url` carries its signature in the query string, so it is a secret
    for the short while it lives -- and never worth logging.
    """

    upload_url: str
    storage_key: str
    expires_in: int
    # Must be sent back verbatim as the Content-Type of the PUT: it is signed.
    content_type: str


class AvatarConfirmIn(BaseModel):
    """The key from the ticket, handed back once the PUT succeeded.

    Trusting the client with a key is safe only because the service checks it
    against the caller's own prefix before believing a word of it.
    """

    storage_key: str = Field(min_length=1, max_length=STORAGE_KEY_MAX_LENGTH)
