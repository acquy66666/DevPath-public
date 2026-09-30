"""Filing a report. What happens to it is the admin's (`api/v1/admin.py`)."""

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.reports import ReportCreate, ReportOut
from app.services import reports as reports_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: ReportCreate, current_user: CurrentUser, session: DbSession
) -> ReportOut:
    """Flag a course, a review, a Q&A question or a Q&A answer.

    Any signed-in account, for anything it can see and did not write. One
    pending report per person per target: a second one is 409 `ALREADY_REPORTED`.
    """
    report = await reports_service.create(
        session,
        current_user,
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason,
        details=body.details,
    )
    return ReportOut.model_validate(report)
