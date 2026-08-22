"""Video upload: what the browser asks for, and what it gets back."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.storage import ALLOWED_VIDEO_TYPES, MAX_UPLOAD_BYTES

FILENAME_MAX_LENGTH = 255


class VideoUploadRequest(BaseModel):
    """The browser describes the file; the backend decides where it may go.

    The size is declared rather than measured because the backend never sees
    the bytes. It is a courtesy check -- it saves an instructor from waiting
    out a 4 GB upload that was never going to be accepted -- not a limit. The
    limit that holds is the one configured on the bucket.
    """

    filename: str = Field(min_length=1, max_length=FILENAME_MAX_LENGTH)
    content_type: str
    size_bytes: int = Field(gt=0)

    @field_validator("content_type")
    @classmethod
    def only_video_types(cls, value: str) -> str:
        # Browsers append charset parameters to some types; compare the bare type.
        bare = value.split(";")[0].strip().lower()
        if bare not in ALLOWED_VIDEO_TYPES:
            allowed = ", ".join(ALLOWED_VIDEO_TYPES)
            raise ValueError(f"Định dạng video không được hỗ trợ. Chấp nhận: {allowed}")
        return bare

    @field_validator("size_bytes")
    @classmethod
    def within_limit(cls, value: int) -> int:
        if value > MAX_UPLOAD_BYTES:
            gigabytes = MAX_UPLOAD_BYTES // (1024 * 1024 * 1024)
            raise ValueError(f"Video tối đa {gigabytes} GB")
        return value


class VideoUploadTicket(BaseModel):
    """Everything the browser needs to do the upload itself.

    `upload_url` carries the signature in its query string, so it is a secret
    for as long as it lives -- short-lived by design, and never logged.
    """

    video_asset_id: uuid.UUID
    upload_url: str
    storage_key: str
    expires_in: int
    # The browser must send this exact value as its Content-Type header: it is
    # part of what was signed.
    content_type: str


class VideoAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    duration_s: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    # Filled in by the service once the transcode finishes; None until then.
    hls_url: str | None = None
