"""User account endpoints.

`GET /auth/me` stays where it is -- it answers "who is this token", which is an
auth question. Everything a signed-in person does *to their own account* lives
here.
"""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import UserOut
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/me/instructor", response_model=UserOut)
async def become_instructor(current_user: CurrentUser, session: DbSession) -> UserOut:
    """Upgrade your own account to `instructor`. Requires sign-in, nothing else.

    Only the caller's account is ever touched -- the route has no id to take,
    so there is no way to point it at anyone else.

    The access token the caller is holding still says `student`; endpoints read
    the role from the database so that does not matter for permissions, but the
    frontend should refresh to render itself as an instructor.
    """
    user = await users_service.promote_to_instructor(session, current_user)
    return UserOut.model_validate(user)
