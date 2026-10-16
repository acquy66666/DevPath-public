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

import logging
import mimetypes
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import status

from app.core.config import get_settings
from app.core.exceptions import DomainError

logger = logging.getLogger(__name__)

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

# Avatars ride the same signed-PUT path, with their own limits. SVG is
# deliberately absent: it is a document format that can carry script, and the
# bucket serves an object back with whatever content type it was handed.
ALLOWED_IMAGE_TYPES = (
    "image/jpeg",
    "image/png",
    "image/webp",
)

# 5 MB. An avatar is drawn at 96 px; anything larger is a photo straight off a
# phone, and the answer to that is to resize it rather than to store it.
MAX_AVATAR_BYTES = 5 * 1024 * 1024
#: A banner is drawn full width, so it may be larger than a face in a circle.
MAX_BANNER_BYTES = 8 * 1024 * 1024

# Transcripts, keyed by extension. No .vtt yet: nothing has asked for it, and
# a format accepted is a format that has to keep parsing correctly.
TRANSCRIPT_FORMATS = {".srt": "srt", ".txt": "txt"}

# Characters, not bytes: the transcript arrives as text in a JSON body. Two
# hours of speech transcribed is around 150 000; a million is a file that is
# not a transcript.
TRANSCRIPT_MAX_CHARS = 1_000_000

# Past this a filename is not worth reading. Every upload flow cuts it here.
FILENAME_MAX_LENGTH = 255


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


def transcript_key(video_asset_id: uuid.UUID, fmt: str) -> str:
    """Where a video's transcript lives: beside the video, so replacing the
    video (which deletes everything under its prefix) takes it along."""
    return f"{asset_prefix(video_asset_id)}/transcript.{fmt}"


def avatar_prefix(user_id: uuid.UUID) -> str:
    """Everything one account has ever used as a picture."""
    return f"avatars/{user_id}"


def avatar_key(user_id: uuid.UUID, filename: str) -> str:
    """Where one uploaded avatar lands.

    A fresh random name every time, rather than a fixed `avatar.png`: this URL
    is public and gets cached by the CDN and by every browser that has drawn
    it, so reusing the key would leave people looking at the old picture for as
    long as the cache lives. The previous object is deleted once the new one is
    confirmed, so the randomness costs nothing.

    The account id is in the path because it is what the upload is checked
    against later -- a key outside your own prefix is not yours to claim.
    """
    suffix = PurePosixPath(filename).suffix.lower()[:10]
    return f"{avatar_prefix(user_id)}/{uuid.uuid4().hex}{suffix}"


#: Every homepage banner picture, whoever uploaded it: banners belong to the
#: platform, not to an account.
BANNER_PREFIX = "banners"


def banner_key(filename: str) -> str:
    """Where one banner picture lands -- a fresh name each time, like avatars,
    so a replaced picture is never served from a stale cache."""
    suffix = PurePosixPath(filename).suffix.lower()[:10]
    return f"{BANNER_PREFIX}/{uuid.uuid4().hex}{suffix}"


#: `DeleteObjects` takes at most this many keys per request.
DELETE_BATCH = 1000


@dataclass(frozen=True)
class StoredObject:
    """One object as a bucket listing describes it."""

    key: str
    size: int
    last_modified: datetime


class ObjectStorage(Protocol):
    """What the rest of the app is allowed to ask of a bucket."""

    def presigned_put_url(
        self, key: str, content_type: str, expires_in: int, *, size_bytes: int
    ) -> str:
        """A URL the browser may PUT exactly one object to, of exactly this
        type and size, for a limited time."""
        ...

    def public_url(self, key: str) -> str:
        """Where a player reads a finished object from."""
        ...

    def download_file(self, key: str, destination: str) -> None: ...

    def upload_file(self, source: str, key: str, content_type: str | None = None) -> None: ...

    def upload_bytes(self, data: bytes, key: str, content_type: str) -> None:
        """Store a small object the API already holds in memory -- a transcript."""
        ...

    def read_bytes(self, key: str) -> bytes:
        """Fetch a small object whole. Not for videos."""
        ...

    def delete_prefix(self, prefix: str) -> None:
        """Delete every object under a prefix. Used when a video is replaced."""
        ...

    def list_objects(self, prefix: str) -> Iterator[StoredObject]:
        """Every object under a prefix, with its size and last change."""
        ...

    def delete_keys(self, keys: Sequence[str]) -> list[str]:
        """Delete exactly these keys. Returns the ones the bucket refused."""
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

    def presigned_put_url(
        self, key: str, content_type: str, expires_in: int, *, size_bytes: int
    ) -> str:
        """Sign a PUT for one key.

        `ContentType` is part of what gets signed, so the browser has to send
        back the same value -- a signed URL cannot be reused to upload
        something of a different kind under the same name.

        So is `ContentLength`, which is what turns the size the browser
        declared from a courtesy into a limit. Unsigned, a ticket for a 200 KB
        avatar took any body nginx let through (2 GB), and on a VPS where the
        bucket shares a disk with Postgres that is a way to stop the site. The
        browser cannot choose the header -- it sends the file's real length --
        so a file that is not the declared size, or a body sent chunked with no
        length at all, is refused with 403 before anything is stored
        (`docs/report/assets/phase-6/signed-upload-length.txt`).
        """
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
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

    def upload_bytes(self, data: bytes, key: str, content_type: str) -> None:
        # Wrapped, unlike the presigning above: this is a request the API makes
        # on the instructor's behalf, and a bucket that refuses should reach
        # them as a 502 with a sentence, not as a 500 with a traceback.
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Kho lưu trữ không nhận tệp") from exc

    def read_bytes(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Không đọc được {key} từ kho lưu trữ") from exc

    def delete_prefix(self, prefix: str) -> None:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if keys:
                self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": keys})

    def list_objects(self, prefix: str) -> Iterator[StoredObject]:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield StoredObject(
                    key=item["Key"], size=item["Size"], last_modified=item["LastModified"]
                )

    def delete_keys(self, keys: Sequence[str]) -> list[str]:
        """Unlike `delete_prefix`, reads the answer: `DeleteObjects` reports a
        key it could not delete in the response body rather than by raising,
        and the sweeper must not forget an object that is still there."""
        refused: list[str] = []
        for start in range(0, len(keys), DELETE_BATCH):
            batch = keys[start : start + DELETE_BATCH]
            response = self._client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
            )
            refused.extend(error["Key"] for error in response.get("Errors", []))
        return refused


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


def get_storage_factory() -> Callable[[], ObjectStorage]:
    """FastAPI dependency for a route that needs the bucket only sometimes.

    Drafting quiz questions reads it for a video's transcript and never for an
    article. `get_storage` would refuse the whole request on a server with no
    bucket configured -- including every article, which never needed one.
    """
    return build_storage


def delete_quietly(storage: ObjectStorage, prefix: str) -> None:
    """Delete objects nobody points at any more, and forgive a failure.

    Best effort on purpose: an orphaned object costs a fraction of a cent of
    storage, while a raised exception here would cost the caller the upload
    they just finished. Forgiven, not hidden: the warning is how anybody finds
    out that every delete has been failing for a month.
    """
    try:
        storage.delete_prefix(prefix)
    except Exception as exc:
        logger.warning("could not delete stale objects under %s: %s", prefix, exc)
