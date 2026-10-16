"""Video upload: what the browser asks for, and what it gets back."""

import uuid
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.storage import (
    ALLOWED_VIDEO_TYPES,
    FILENAME_MAX_LENGTH,
    MAX_UPLOAD_BYTES,
    TRANSCRIPT_FORMATS,
    TRANSCRIPT_MAX_CHARS,
)


class VideoUploadRequest(BaseModel):
    """The browser describes the file; the backend decides where it may go.

    The size is declared rather than measured because the backend never sees
    the bytes. It is signed into the upload URL, so the bucket holds the PUT
    to exactly this length: checking it here is the limit, and it saves an
    instructor from waiting out a 4 GB upload that was never going to be
    accepted.
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

    # `srt` or `txt` when an instructor has uploaded one, else None. Only the
    # format, not the file: the curriculum builder needs to say "có transcript",
    # and nothing a student sees reads it.
    transcript_format: Literal["srt", "txt"] | None = None


class TranscriptUpload(BaseModel):
    """A transcript, as the text the browser read out of the file.

    Text rather than bytes because the browser has already decoded it as UTF-8
    -- which is exactly what lets the service spot a file that was not.
    """

    filename: str = Field(min_length=1, max_length=FILENAME_MAX_LENGTH)
    content: str = Field(min_length=1, max_length=TRANSCRIPT_MAX_CHARS)

    @field_validator("filename")
    @classmethod
    def srt_or_txt(cls, value: str) -> str:
        if PurePosixPath(value).suffix.lower() not in TRANSCRIPT_FORMATS:
            raise ValueError("Chỉ nhận tệp .srt hoặc .txt")
        return value


class TranscriptOut(BaseModel):
    """What was kept, told back so the instructor can tell it was read right."""

    format: Literal["srt", "txt"]
    #: Characters the chatbot will read -- after timings and tags are gone.
    characters: int
    #: True when the course is live and an ingest was queued; False for a
    #: draft, which is ingested when it is published.
    ingest_queued: bool
