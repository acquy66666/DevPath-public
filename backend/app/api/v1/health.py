from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.schemas.health import HealthOut, ReadinessOut
from app.services import readiness

router = APIRouter(tags=["health"])

Checks = Annotated[dict[str, readiness.Check], Depends(readiness.get_readiness_checks)]


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    """Liveness probe. Public by design — no auth, no database access.

    The container healthcheck reads this, so it must stay green while the
    process is fine, whatever Postgres or Redis are doing. Whether the API
    can actually serve is `/health/ready`.
    """
    settings = get_settings()
    return HealthOut(status="ok", app=settings.app_name, env=settings.env)


@router.get(
    "/health/ready",
    response_model=ReadinessOut,
    responses={503: {"description": "A dependency did not answer; `detail.checks` says which"}},
)
async def ready(checks: Checks) -> ReadinessOut:
    """Readiness probe: the database and Redis both answer, within a bound.

    Public by design, like liveness — the deploy script and an outside uptime
    check ask it without credentials. It costs a `SELECT 1` and a `PING`, and
    says which dependency failed but never why (see `services/readiness.py`).
    """
    return ReadinessOut(status="ready", checks=await readiness.require_ready(checks))
