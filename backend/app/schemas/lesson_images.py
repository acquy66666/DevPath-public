"""Pictures inside an article lesson: what the editor asks for, what it gets."""

from pydantic import BaseModel, Field, field_validator

from app.services.storage import LESSON_IMAGE_TYPES, MAX_LESSON_IMAGE_BYTES


class LessonImageUploadIn(BaseModel):
    """The browser describes the picture; the backend decides where it goes.

    No filename: the key is random and its extension comes from the type, so a
    name would only be one more string to validate. The size is signed into
    the URL, so the bucket takes exactly this many bytes.
    """

    content_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)

    @field_validator("content_type")
    @classmethod
    def only_picture_types(cls, value: str) -> str:
        bare = value.split(";")[0].strip().lower()
        if bare not in LESSON_IMAGE_TYPES:
            raise ValueError("Ảnh trong bài đọc phải là PNG, JPEG, WebP hoặc GIF")
        return bare

    @field_validator("size_bytes")
    @classmethod
    def within_limit(cls, value: int) -> int:
        if value > MAX_LESSON_IMAGE_BYTES:
            megabytes = MAX_LESSON_IMAGE_BYTES // (1024 * 1024)
            raise ValueError(f"Ảnh trong bài đọc tối đa {megabytes} MB")
        return value


class LessonImageUploadTicket(BaseModel):
    """Where to PUT the picture, and the address to write into the article.

    `upload_url` carries its signature in the query string: a secret for the
    hour it lives. `public_url` is what the Markdown names once the PUT has
    succeeded; nothing else needs confirming, because the article saving that
    address is what claims the picture (`services/orphans.py`).
    """

    upload_url: str
    storage_key: str
    public_url: str
    expires_in: int
    # Must be sent back verbatim as the Content-Type of the PUT: it is signed.
    content_type: str
