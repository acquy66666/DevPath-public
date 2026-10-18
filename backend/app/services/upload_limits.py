"""How many upload URLs one account may be handed, and for how many bytes.

A signed URL takes exactly the bytes it was signed for (since 16/10), so the
bucket can only hold what the tickets allowed. What that does not bound is the
number of tickets: before this, one signed-in account with a script could ask
for avatar URLs in a loop and fill the disk 5 MB at a time -- or, having made
itself an instructor (self-service), 2 GB at a time. A ticket nobody confirms
is only cleaned up by the orphan sweep, a day plus fourteen of quarantine
later, which is far too slow to save a disk.

So the count is kept where tickets are handed out, and always before one is
signed. Per account rather than per address: the account is what has to be
signed in to ask, and a computer lab behind one NAT is forty people changing
their pictures.

Admin banners are deliberately not here. The admin is who the disk alarm
wakes up; whoever holds an admin session can already take every course down
and lock every account, and a ticket limit would guard one window of a house
whose door is open.
"""

from __future__ import annotations

import math
import uuid

from fastapi import status

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.services.rate_limit import RateLimiter

HOUR_SECONDS = 60 * 60
DAY_SECONDS = 24 * HOUR_SECONDS

AVATAR_WINDOW_SECONDS = DAY_SECONDS
VIDEO_TICKET_WINDOW_SECONDS = HOUR_SECONDS
VIDEO_BYTES_WINDOW_SECONDS = DAY_SECONDS

AVATAR_KEY = "upload:avatar:user:{user}"
VIDEO_TICKETS_KEY = "upload:video:user:{user}"
VIDEO_BYTES_KEY = "upload:video-bytes:user:{user}"

GIGABYTE = 1024 * 1024 * 1024


class UploadRateLimitedError(DomainError):
    """Too many upload URLs, or too many bytes of them, for one account.

    One code for every upload: the page answers each the same way, by showing
    the wait. The message says which limit it was.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "UPLOAD_RATE_LIMITED"

    def __init__(self, message: str, *, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


def _wait(seconds: int) -> str:
    """A wait as people say it: minutes under an hour, hours above. Never 0."""
    if seconds < HOUR_SECONDS:
        return f"{seconds // 60 + 1} phút"
    return f"{math.ceil(seconds / HOUR_SECONDS)} giờ"


async def enforce_avatar_ticket_limit(limiter: RateLimiter, user_id: uuid.UUID) -> None:
    """Count one avatar ticket against the account's day."""
    limit = get_settings().avatar_upload_tickets_per_user
    wait = await limiter.count(AVATAR_KEY.format(user=user_id), limit, AVATAR_WINDOW_SECONDS)
    if wait:
        raise UploadRateLimitedError(
            f"Bạn đã xin tải ảnh đại diện lên {limit} lần trong 24 giờ. "
            f"Thử lại sau khoảng {_wait(wait)}.",
            retry_after=wait,
        )


async def enforce_video_ticket_limits(
    limiter: RateLimiter, user_id: uuid.UUID, *, size_bytes: int
) -> None:
    """Count one video ticket, then spend its declared size from the day's budget.

    The count first: a ticket refused for being one too many is not charged
    to the budget. The other way round, a request refused by the count would
    already have spent its bytes.
    """
    settings = get_settings()

    wait = await limiter.count(
        VIDEO_TICKETS_KEY.format(user=user_id),
        settings.video_upload_tickets_per_user,
        VIDEO_TICKET_WINDOW_SECONDS,
    )
    if wait:
        raise UploadRateLimitedError(
            f"Bạn đã xin tải video lên {settings.video_upload_tickets_per_user} lần "
            f"trong một giờ — quá nhiều so với bình thường. "
            f"Thử lại sau khoảng {_wait(wait)}.",
            retry_after=wait,
        )

    budget = settings.video_upload_bytes_per_user
    wait = await limiter.count(
        VIDEO_BYTES_KEY.format(user=user_id),
        budget,
        VIDEO_BYTES_WINDOW_SECONDS,
        amount=size_bytes,
    )
    if wait:
        gigabytes = f"{budget / GIGABYTE:g}".replace(".", ",")
        raise UploadRateLimitedError(
            f"Tệp này vượt hạn mức tải video của bạn: tối đa {gigabytes} GB "
            f"trong 24 giờ. Chọn tệp nhỏ hơn, hoặc thử lại sau khoảng {_wait(wait)}.",
            retry_after=wait,
        )
