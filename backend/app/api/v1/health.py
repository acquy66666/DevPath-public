from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    """Liveness probe. Public by design — no auth, no database access.

    Readiness (database + Redis reachable) gets its own endpoint once
    docker-compose brings those services up.
    """
    settings = get_settings()
    return HealthOut(status="ok", app=settings.app_name, env=settings.env)
