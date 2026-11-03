"""User account endpoints.

`GET /auth/me` stays where it is -- it answers "who is this token", which is an
auth question. Everything a signed-in person does *to their own account* lives
here.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.v1._transport import client_info, token_response
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import TokenOut, UserOut
from app.schemas.instructor_applications import (
    InstructorApplicationCreate,
    InstructorApplicationOut,
    MyInstructorApplicationOut,
)
from app.schemas.users import (
    AvatarConfirmIn,
    AvatarUploadIn,
    AvatarUploadTicket,
    PasswordChangeIn,
    ProfileUpdateIn,
)
from app.services import instructor_applications as applications_service
from app.services import users as users_service
from app.services.rate_limit import RateLimiter, get_rate_limiter
from app.services.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/users", tags=["users"])

Storage = Annotated[ObjectStorage, Depends(get_storage)]
RateLimit = Annotated[RateLimiter, Depends(get_rate_limiter)]


@router.get("/me/instructor-application", response_model=MyInstructorApplicationOut)
async def get_my_instructor_application(
    current_user: CurrentUser, session: DbSession
) -> MyInstructorApplicationOut:
    """Your latest application to teach -- pending, approved, or rejected with
    the reason -- or `application: null` if you never applied."""
    application = await applications_service.latest_for(session, current_user)
    return MyInstructorApplicationOut(
        application=InstructorApplicationOut.model_validate(application)
        if application
        else None
    )


@router.post(
    "/me/instructor-application",
    response_model=InstructorApplicationOut,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_teach(
    payload: InstructorApplicationCreate, current_user: CurrentUser, session: DbSession
) -> InstructorApplicationOut:
    """Ask an admin to make your account an instructor. Changes no role.

    No id in the path: it only ever files an application for the caller.
    409 `INSTRUCTOR_APPLICATION_PENDING` while one is waiting,
    `ALREADY_INSTRUCTOR` for an instructor, `ROLE_CHANGE_NOT_ALLOWED` for an admin.
    """
    application = await applications_service.apply(
        session, current_user, motivation=payload.motivation
    )
    return InstructorApplicationOut.model_validate(application)


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
    limiter: RateLimit,
) -> TokenOut:
    """Change your own password, signing every other device out.

    Answers with a new token pair and a new refresh cookie: the old refresh
    token was revoked along with the rest, so the caller needs the replacement
    to stay signed in. 429 AUTH_RATE_LIMITED after five attempts in fifteen
    minutes.
    """
    tokens = await users_service.change_password(
        session,
        current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        limiter=limiter,
        client=client_info(request),
    )
    return token_response(response, tokens)


@router.post(
    "/me/avatar",
    response_model=AvatarUploadTicket,
    status_code=status.HTTP_201_CREATED,
)
async def create_avatar_upload(
    payload: AvatarUploadIn, current_user: CurrentUser, storage: Storage, limiter: RateLimit
) -> AvatarUploadTicket:
    """Ask for somewhere to put a new profile picture. Carries no bytes.

    Like the video routes, this one answers 503 `STORAGE_NOT_CONFIGURED` when
    no bucket has been set up. That is deliberate: the rest of the profile page
    goes on working without object storage, and only this button does not.
    429 UPLOAD_RATE_LIMITED after twenty tickets in a day.
    """
    return await users_service.create_avatar_upload_ticket(
        current_user, storage, payload, limiter=limiter
    )


@router.post("/me/avatar/complete", response_model=UserOut)
async def complete_avatar_upload(
    payload: AvatarConfirmIn,
    current_user: CurrentUser,
    session: DbSession,
    storage: Storage,
) -> UserOut:
    """The browser finished its PUT: wear the new picture, drop the old one.

    No id in the path, and the key is checked against the caller's own folder
    in the service -- so this cannot be aimed at anybody else's account, in
    either direction.
    """
    user = await users_service.set_avatar(
        session, current_user, storage, storage_key=payload.storage_key
    )
    return UserOut.model_validate(user)
