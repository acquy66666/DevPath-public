"""User account endpoints.

`GET /auth/me` stays where it is -- it answers "who is this token", which is an
auth question. Everything a signed-in person does *to their own account* lives
here.
"""

from fastapi import APIRouter, Request, Response

from app.api.v1._transport import client_info, token_response
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import TokenOut, UserOut
from app.schemas.users import PasswordChangeIn, ProfileUpdateIn
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


@router.patch("/me", response_model=UserOut)
async def update_profile(
    payload: ProfileUpdateIn, current_user: CurrentUser, session: DbSession
) -> UserOut:
    """Edit your own profile. Requires sign-in, nothing else.

    The route takes no id, so it can only ever touch the caller; and the schema
    holds one field, so a `"role"` smuggled into the body goes nowhere.
    """
    user = await users_service.update_profile(
        session, current_user, full_name=payload.full_name
    )
    return UserOut.model_validate(user)


@router.post("/me/password", response_model=TokenOut)
async def change_password(
    payload: PasswordChangeIn,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    session: DbSession,
) -> TokenOut:
    """Change your own password, signing every other device out.

    Answers with a new token pair and a new refresh cookie: the old refresh
    token was revoked along with the rest, so the caller needs the replacement
    to stay signed in.
    """
    tokens = await users_service.change_password(
        session,
        current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        client=client_info(request),
    )
    return token_response(response, tokens)
