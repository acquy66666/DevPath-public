"""The homepage banners. Public: the homepage is."""

from fastapi import APIRouter

from app.core.deps import DbSession
from app.schemas.banners import BannerOut
from app.services import banners as banners_service

router = APIRouter(prefix="/banners", tags=["banners"])


@router.get("", response_model=list[BannerOut])
async def list_live_banners(session: DbSession) -> list[BannerOut]:
    """Switched on and inside their window right now, in order, at most five.
    Unpaginated: it is the top of one page."""
    return [BannerOut.model_validate(b) for b in await banners_service.list_live(session)]
