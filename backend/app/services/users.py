"""User account changes people make to themselves."""

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.users import AvatarUploadIn, AvatarUploadTicket
from app.services.auth import (
    ClientInfo,
    IssuedTokens,
    enforce_password_change_limit,
    replace_all_sessions,
)
from app.services.rate_limit import RateLimiter
from app.services.storage import (
    ObjectStorage,
    avatar_key,
    avatar_prefix,
    delete_quietly,
)
from app.services.upload_limits import enforce_avatar_ticket_limit


class RoleChangeNotAllowedError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "ROLE_CHANGE_NOT_ALLOWED"


class PasswordNotSetError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "PASSWORD_NOT_SET"


class InvalidCurrentPasswordError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_CURRENT_PASSWORD"


class PasswordUnchangedError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "PASSWORD_UNCHANGED"


class AvatarKeyNotOwnedError(DomainError):
    """A confirmed key that points outside the caller's own avatar folder."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "AVATAR_KEY_NOT_OWNED"


async def promote_to_instructor(session: AsyncSession, user: User) -> User:
    """Turn a student into an instructor, at their own request.

    Teaching is opt-in and self-service: this platform has no application queue
    for it, and an admin gate would only be a queue nobody drains. What keeps
    it honest is downstream -- a new instructor's courses still start as drafts
    and go through review before anyone can see them.

    Asking again once you already are one is not an error: two tabs and two
    clicks should not produce a scary message.
    """
    if user.role == "instructor":
        return user

    if user.role != "student":
        # An admin already outranks this in every check, so "promoting" them
        # would take rights away. Refuse rather than answer 200 and do nothing.
        raise RoleChangeNotAllowedError(
            "Chỉ tài khoản học viên mới có thể tự nâng cấp thành giảng viên"
        )

    user.role = "instructor"
    await session.commit()
    return user


async def update_profile(session: AsyncSession, user: User, *, full_name: str) -> User:
    """Edit the caller's own profile. Only the fields in the schema can move."""
    user.full_name = full_name
    await session.commit()
    return user


async def change_password(
    session: AsyncSession,
    user: User,
    *,
    current_password: str,
    new_password: str,
    limiter: RateLimiter,
    client: ClientInfo | None = None,
) -> IssuedTokens:
    """Replace the password, then start the sessions over.

    The current password is required even though the caller is already signed
    in: an access token can be fifteen minutes old and belong to whoever sat
    down at an unlocked laptop, while the password is something only its owner
    knows.

    Returns a fresh token pair -- every other session of this user has just
    been revoked, including the refresh token this device was holding.
    """
    if user.password_hash is None:
        # A Google-only account. There is nothing to verify against, and
        # setting a first password is a different flow with its own checks.
        raise PasswordNotSetError(
            "Tài khoản này đăng nhập bằng Google nên chưa có mật khẩu để đổi"
        )

    # Before bcrypt, and whether or not the guess turns out right: the limit
    # is on guessing, and a right guess is a guess too.
    await enforce_password_change_limit(limiter, user.id)

    if not verify_password(current_password, user.password_hash):
        raise InvalidCurrentPasswordError("Mật khẩu hiện tại không đúng")

    if verify_password(new_password, user.password_hash):
        raise PasswordUnchangedError("Mật khẩu mới phải khác mật khẩu hiện tại")

    user.password_hash = hash_password(new_password)
    tokens = await replace_all_sessions(session, user, client)
    await session.commit()
    return tokens


async def create_avatar_upload_ticket(
    user: User, storage: ObjectStorage, data: AvatarUploadIn, *, limiter: RateLimiter
) -> AvatarUploadTicket:
    """Sign a URL the browser may PUT one picture to.

    Nothing is written to the database here, which is what makes this simpler
    than the video flow: an avatar has no processing to follow, so until the
    browser says the bytes landed there is no state worth keeping. A ticket
    nobody uses costs one unreferenced object at worst, and the account goes
    on wearing the picture it already had -- which is why the tickets are
    counted, before one is signed: a loop of them is a loop of those objects.
    """
    await enforce_avatar_ticket_limit(limiter, user.id)

    ttl = get_settings().upload_url_ttl_seconds
    key = avatar_key(user.id, data.filename)
    return AvatarUploadTicket(
        upload_url=storage.presigned_put_url(
            key, data.content_type, ttl, size_bytes=data.size_bytes
        ),
        storage_key=key,
        expires_in=ttl,
        content_type=data.content_type,
    )


def _own_avatar_key(user: User, storage: ObjectStorage) -> str | None:
    """The bucket key of the picture this account wears, when we host it.

    None for a Google picture: that URL belongs to Google, and handing it to
    our own bucket to delete would be meaningless. None too for anything that
    does not sit in this account's folder, which is the case worth being
    careful about -- deleting is not something to do on a guess.
    """
    if user.avatar_url is None:
        return None

    base = storage.public_url("")
    if not user.avatar_url.startswith(base):
        return None

    key = user.avatar_url[len(base) :]
    return key if key.startswith(f"{avatar_prefix(user.id)}/") else None


async def set_avatar(
    session: AsyncSession, user: User, storage: ObjectStorage, *, storage_key: str
) -> User:
    """Point the account at a picture the browser has just uploaded.

    The key travels back through the client, so it is checked against the
    caller's own folder before it is believed. Without that check the endpoint
    would happily hang any object in the bucket -- somebody else's picture, or
    a lecture video -- on this account.

    Whether the object really arrived is not checked, for the reason the video
    flow gives: a HEAD request here would only move a broken image from one
    place to another, and the browser has just watched its PUT succeed.
    """
    prefix = f"{avatar_prefix(user.id)}/"
    if not storage_key.startswith(prefix) or "/" in storage_key[len(prefix) :]:
        raise AvatarKeyNotOwnedError("Ảnh này không thuộc về tài khoản của bạn")

    stale_key = _own_avatar_key(user, storage)
    user.avatar_url = storage.public_url(storage_key)
    await session.commit()
    await session.refresh(user)

    if stale_key is not None and stale_key != storage_key:
        # After the commit, and best effort: the old picture is only garbage
        # once the new one is really saved, and a bucket that refuses must not
        # cost the caller the avatar they just uploaded.
        delete_quietly(storage, stale_key)

    return user
