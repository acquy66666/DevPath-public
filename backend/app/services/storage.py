"""Object storage: signed upload URLs in, public playback URLs out.

Kept behind a Protocol for the same reason as `google_oauth.py`: the routes
never touch boto3, and the tests never touch Cloudflare. `tests/` swaps in a
fake through FastAPI's dependency override.

Why the browser uploads straight to R2 and not through this API:

    browser --> POST /lessons/{id}/video      (backend signs a URL)
    browser --> PUT https://<bucket>...       (the file itself, no backend)
    browser --> POST /video-assets/{id}/complete
    worker  --> ffmpeg --> HLS --> R2

A lecture video is hundreds of megabytes. Streaming that through FastAPI
would tie up a worker process for the whole upload and double the bandwidth
bill for no gain -- the signature already says who is allowed to write, and to
exactly which key.
"""

import mimetypes
import uuid
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Protocol

import boto3
from botocore.client import Config
from fastapi import status

from app.core.config import get_settings
from app.core.exceptions import DomainError

# Only formats ffmpeg can be trusted to open, and that a browser can produce
# from a file picker. The check is a courtesy to the instructor -- the real
# verdict comes from the transcode step.
ALLOWED_VIDEO_TYPES = (
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
)

# 2 GB. Above this a single PUT is the wrong shape and the upload wants the
# multipart API, which is a bigger flow than Phase 2 needs.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024


class StorageNotConfiguredError(DomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "STORAGE_NOT_CONFIGURED"


class StorageError(DomainError):
    """The bucket refused, or could not be reached."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "STORAGE_ERROR"


def original_video_key(video_asset_id: uuid.UUID, filename: str) -> str:
    """Where an uploaded video lands.

    The id, not the original filename, decides the path: two instructors both
    uploading `bai1.mp4` must not collide, and a filename from a browser can
    contain anything at all. The extension is kept because ffmpeg uses it as a
    hint and because it makes a bucket listing readable.
    """
    suffix = PurePosixPath(filename).suffix.lower()[:10]
    return f"{asset_prefix(video_asset_id)}/original{suffix}"


def asset_prefix(video_asset_id: uuid.UUID) -> str:
    """Everything belonging to one video -- original and HLS output alike."""
    return f"videos/{video_asset_id}"


def hls_prefix(video_asset_id: uuid.UUID) -> str:
    """Where ffmpeg's output goes: one manifest and its segments."""
    return f"{asset_prefix(video_asset_id)}/hls"


class ObjectStorage(Protocol):
    """What the rest of the app is allowed to ask of a bucket."""

    def presigned_put_url(self, key: str, content_type: str, expires_in: int) -> str:
        """A URL the browser may PUT exactly one object to, for a limited time."""
        ...

    def public_url(self, key: str) -> str:
        """Where a player reads a finished object from."""
        ...

    def download_file(self, key: str, destination: str) -> None: ...

    def upload_file(self, source: str, key: str, content_type: str | None = None) -> None: ...

    def delete_prefix(self, prefix: str) -> None:
        """Delete every object under a prefix. Used when a video is replaced."""
        ...


class R2Storage:
    """Cloudflare R2 through the S3 API."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_base_url: str,
    ) -> None:
        self._bucket = bucket
        self._public_base_url = public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # R2 has no regions, but SigV4 needs a region string in the
            # signature; "auto" is the one Cloudflare documents.
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def presigned_put_url(self, key: str, content_type: str, expires_in: int) -> str:
        """Sign a PUT for one key.

        `ContentType` is part of what gets signed, so the browser has to send
        back the same value -- a signed URL cannot be reused to upload
        something of a different kind under the same name.
        """
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )

    def public_url(self, key: str) -> str:
        return f"{self._public_base_url}/{key}"

    def download_file(self, key: str, destination: str) -> None:
        self._client.download_file(self._bucket, key, destination)

    def upload_file(self, source: str, key: str, content_type: str | None = None) -> None:
        guessed = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        self._client.upload_file(
            source, self._bucket, key, ExtraArgs={"ContentType": guessed}
        )

    def delete_prefix(self, prefix: str) -> None:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if keys:
                self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": keys})


@lru_cache
def _shared_storage() -> R2Storage:
    """One client per process: boto3 clients are thread-safe and expensive to build."""
    settings = get_settings()
    return R2Storage(
        endpoint_url=settings.storage_endpoint_url,
        access_key_id=settings.r2_access_key_id,
        secret_access_key=settings.r2_secret_access_key,
        bucket=settings.r2_bucket,
        public_base_url=settings.r2_public_base_url,
    )


def build_storage() -> ObjectStorage:
    """The storage the worker uses. Raises if the bucket was never configured."""
    if not get_settings().storage_enabled:
        raise StorageNotConfiguredError(
            "Lưu trữ tệp chưa được cấu hình trên máy chủ này"
        )
    return _shared_storage()


def get_storage() -> ObjectStorage:
    """FastAPI dependency. Tests override this; nothing else builds a client."""
    return build_storage()
