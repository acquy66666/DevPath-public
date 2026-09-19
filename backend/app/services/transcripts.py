"""Video transcripts: what an instructor uploads, and the words the chatbot reads.

    instructor --> PUT /lessons/{id}/transcript   (checked here, stored on R2)
    publish / re-upload --> ingest worker --> reads it back --> chunks --> doc_chunks

**Through the API, not a signed URL.** Videos and avatars go straight from the
browser to the bucket because a lecture is hundreds of megabytes (see
`services/storage.py`). A transcript is a few dozen kilobytes, and passing it
through here buys the one thing a signed URL cannot: the file is read before it
is kept. A subtitle saved in Windows-1258, or a text file renamed `.srt`, is
refused with a sentence the instructor can act on -- instead of being accepted,
ingested, and quoted back to students as gibberish weeks later.

**The original is stored, not the extracted text.** The timings are useless to
retrieval but not to everything else -- subtitles in the player are on the
list of features to add if there is time -- and a stored original can always be
re-read by a better parser, where stored text cannot be un-flattened.

**It belongs to the video asset**, which is where `transcript_key` lives:
replacing the video replaces the asset, and the transcript of the old recording
goes with it rather than being quietly attached to a new one it may not match.
"""

import re
import uuid
from pathlib import PurePosixPath

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import User, VideoAsset
from app.schemas.video import TranscriptOut, TranscriptUpload
from app.services import curriculum as curriculum_service
from app.services.storage import (
    TRANSCRIPT_FORMATS,
    ObjectStorage,
    delete_quietly,
    transcript_key,
)
from app.services.tasks import TaskQueue

CONTENT_TYPES = {
    "srt": "application/x-subrip; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
}


class TranscriptUnreadableError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "TRANSCRIPT_UNREADABLE"


class TranscriptEmptyError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "TRANSCRIPT_EMPTY"


class LessonHasNoVideoError(DomainError):
    """A transcript is the words of a video. Without one there is nothing to
    hang it on -- and nothing for a student to have watched."""

    status_code = status.HTTP_409_CONFLICT
    code = "LESSON_HAS_NO_VIDEO"


class TranscriptNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "TRANSCRIPT_NOT_FOUND"


# --- Reading a file ----------------------------------------------------------


def transcript_format(filename: str) -> str | None:
    """`srt`, `txt`, or None for anything else. Decided by the extension."""
    return TRANSCRIPT_FORMATS.get(PurePosixPath(filename).suffix.lower())


# 00:03:21,440 --> 00:03:24,100, with the dot some tools write instead of the
# comma, one-digit hours, and whatever positioning a cue carries after it.
_TIMING = re.compile(
    r"^\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}"
)
# <i>, </b>, <font color="...">; and the ASS-style {\an8} some editors add.
_TAGS = re.compile(r"<[^>]*>|\{\\[^}]*\}")
_SPACES = re.compile(r"[ \t]+")
_BLANK_RUNS = re.compile(r"\n{3,}")


def _normalise(raw: str) -> str:
    """One set of line endings, no byte order mark, and a refusal of anything
    that was not UTF-8 by the time it got here."""
    if "\ufffd" in raw:
        # The browser decodes the file as UTF-8 before sending it; a file in
        # another encoding arrives with U+FFFD where its letters were.
        raise TranscriptUnreadableError(
            "Tệp không ở bảng mã UTF-8 nên chữ tiếng Việt bị vỡ. "
            "Mở tệp bằng trình soạn thảo, lưu lại với bảng mã UTF-8 rồi tải lên lại."
        )
    return raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _srt_text(raw: str) -> str:
    lines = raw.split("\n")
    spoken: list[str] = []
    seen_timing = False
    in_cue = False

    for index, line in enumerate(lines):
        if _TIMING.match(line):
            seen_timing = in_cue = True
            continue
        if not in_cue:
            # Anything before the first cue: a header, a stray title.
            continue

        stripped = line.strip()
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if stripped.isdigit() and _TIMING.match(following):
            # The next cue's number, not something anybody said.
            continue

        words = _SPACES.sub(" ", _TAGS.sub("", stripped)).strip()
        # A rolling auto-caption repeats the line before it as it scrolls.
        if words and (not spoken or spoken[-1] != words):
            spoken.append(words)

    if not seen_timing:
        raise TranscriptUnreadableError(
            "Tệp .srt không có dòng thời gian nào (dạng 00:00:01,000 --> 00:00:04,000). "
            "Nếu đây là văn bản thường, đổi đuôi tệp thành .txt rồi tải lên lại."
        )
    return " ".join(spoken)


def _txt_text(raw: str) -> str:
    lines = [_SPACES.sub(" ", line).strip() for line in raw.split("\n")]
    return _BLANK_RUNS.sub("\n\n", "\n".join(lines)).strip()


def transcript_text(raw: str, fmt: str) -> str:
    """The words in a transcript file, ready for the chunker.

    Raises TranscriptUnreadableError for a file that is not what it claims to
    be, and TranscriptEmptyError for one that is but says nothing.
    """
    normalised = _normalise(raw)
    text = _srt_text(normalised) if fmt == "srt" else _txt_text(normalised)
    if not text:
        raise TranscriptEmptyError("Tệp không có câu thoại nào để chatbot đọc.")
    return text


def format_of_key(key: str) -> str:
    """The format a stored transcript was uploaded as, from its object key."""
    return transcript_format(key) or "txt"


# --- Managing a lesson's transcript -------------------------------------------


async def _video_of(
    session: AsyncSession, lesson_id: uuid.UUID, user: User
) -> tuple[VideoAsset, bool, uuid.UUID]:
    """The lesson's video, whether its course is live, and the course id."""
    lesson, _, course = await curriculum_service.lesson_for_management(
        session, lesson_id, user
    )
    # Imported here, not at the top: services/video.py imports this module to
    # describe an asset's transcript. The error is the video upload's own.
    from app.services.video import LessonNotVideoError

    if lesson.type != "video":
        raise LessonNotVideoError("Chỉ bài học dạng video mới có transcript")
    if lesson.video_asset is None:
        raise LessonHasNoVideoError("Tải video lên trước, rồi mới gắn transcript cho nó")
    return lesson.video_asset, course.status == "published", course.id


async def put_transcript(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    storage: ObjectStorage,
    queue: TaskQueue,
    data: TranscriptUpload,
) -> TranscriptOut:
    """Check a transcript, keep it, and have a live course re-read.

    Stored before the row points at it, so a failed upload leaves the lesson
    exactly as it was. Re-uploading replaces: `.srt` and `.txt` live under
    different keys, so switching format deletes the other one.
    """
    asset, published, course_id = await _video_of(session, lesson_id, user)

    fmt = transcript_format(data.filename)
    text = transcript_text(data.content, fmt)

    key = transcript_key(asset.id, fmt)
    storage.upload_bytes(data.content.encode("utf-8"), key, CONTENT_TYPES[fmt])

    previous = asset.transcript_key
    asset.transcript_key = key
    await session.commit()
    # Postgres fills `updated_at` itself, so the UPDATE leaves it expired, and
    # the next reader of this asset in the session would trip on lazy IO.
    await session.refresh(asset)

    if previous is not None and previous != key:
        delete_quietly(storage, previous)

    # After the commit, like every enqueue: the worker opens its own connection.
    # A draft course is ingested when it is published, and not before.
    if published:
        queue.enqueue_ingest(course_id)

    return TranscriptOut(format=fmt, characters=len(text), ingest_queued=published)


async def delete_transcript(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    user: User,
    storage: ObjectStorage,
    queue: TaskQueue,
) -> None:
    """Take the transcript off a video. On a live course the lesson's chunks
    go on the next ingest, which is queued here."""
    asset, published, course_id = await _video_of(session, lesson_id, user)

    if asset.transcript_key is None:
        raise TranscriptNotFoundError("Video này chưa có transcript")

    previous = asset.transcript_key
    asset.transcript_key = None
    await session.commit()
    await session.refresh(asset)

    delete_quietly(storage, previous)
    if published:
        queue.enqueue_ingest(course_id)
