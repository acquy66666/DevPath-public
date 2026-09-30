"""Homepage banners on the wire."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.banner import BANNER_TITLE_MAX_LENGTH
from app.services.storage import ALLOWED_IMAGE_TYPES, FILENAME_MAX_LENGTH, MAX_BANNER_BYTES

LINK_MAX_LENGTH = 500
KEY_MAX_LENGTH = 512


def _title(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise ValueError("Tiêu đề banner không được để trống")
    return text


def _link(value: str | None) -> str | None:
    """A path on this site, or an absolute web address -- nothing else.

    A `javascript:` URL in an `href` runs when clicked, and `//host` is an
    absolute address pretending to be a path; neither gets through.
    """
    if value is None:
        return None
    link = value.strip()
    if not link:
        return None
    if link.startswith("/") and not link.startswith("//"):
        return link
    if link.startswith(("https://", "http://")):
        return link
    raise ValueError("Liên kết phải là đường dẫn trong trang (bắt đầu bằng /) hoặc địa chỉ http(s)")


class BannerOut(BaseModel):
    """What the homepage draws."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    image_url: str
    link_url: str | None


class AdminBannerOut(BannerOut):
    position: int
    is_active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    #: Derived: live, scheduled, ended, off.
    status: str
    created_at: datetime


class BannerUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=FILENAME_MAX_LENGTH)
    content_type: str
    size_bytes: int = Field(gt=0)

    @field_validator("content_type")
    @classmethod
    def only_images(cls, value: str) -> str:
        bare = value.split(";")[0].strip().lower()
        if bare not in ALLOWED_IMAGE_TYPES:
            raise ValueError(
                f"Định dạng ảnh không được hỗ trợ. Chấp nhận: {', '.join(ALLOWED_IMAGE_TYPES)}"
            )
        return bare

    @field_validator("size_bytes")
    @classmethod
    def within_limit(cls, value: int) -> int:
        if value > MAX_BANNER_BYTES:
            raise ValueError(f"Ảnh banner tối đa {MAX_BANNER_BYTES // (1024 * 1024)} MB")
        return value


class BannerUploadTicket(BaseModel):
    upload_url: str
    storage_key: str
    expires_in: int
    #: Must be sent back verbatim as the Content-Type of the PUT: it is signed.
    content_type: str


class _Period(BaseModel):
    @model_validator(mode="after")
    def _period(self):
        starts_at = getattr(self, "starts_at", None)
        ends_at = getattr(self, "ends_at", None)
        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise ValueError("Thời điểm gỡ phải sau thời điểm bắt đầu hiện")
        return self


class BannerCreate(_Period):
    title: str = Field(min_length=1, max_length=BANNER_TITLE_MAX_LENGTH)
    #: The key the upload ticket handed out.
    image_key: str = Field(min_length=1, max_length=KEY_MAX_LENGTH)
    link_url: str | None = Field(default=None, max_length=LINK_MAX_LENGTH)
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    _strip_title = field_validator("title")(_title)
    _check_link = field_validator("link_url")(_link)


class BannerUpdate(_Period):
    """Only what is sent changes; `null` clears a link or a bound."""

    title: str | None = Field(default=None, min_length=1, max_length=BANNER_TITLE_MAX_LENGTH)
    image_key: str | None = Field(default=None, min_length=1, max_length=KEY_MAX_LENGTH)
    link_url: str | None = Field(default=None, max_length=LINK_MAX_LENGTH)
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    _strip_title = field_validator("title")(_title)
    _check_link = field_validator("link_url")(_link)


class BannerOrderIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1)
