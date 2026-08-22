"""The category list. Public, and small enough to send whole.

No pagination: the tree is a fixed taxonomy an admin curates, not user data
that grows. A page cursor over a dozen rows would be ceremony.
"""

from fastapi import APIRouter

from app.core.deps import DbSession
from app.schemas.categories import CategoryOut, CategoryTree
from app.services import categories as categories_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryTree])
async def list_categories(session: DbSession) -> list[CategoryTree]:
    tree = await categories_service.list_tree(session)
    return [
        CategoryTree(
            **CategoryOut.model_validate(parent).model_dump(),
            children=[CategoryOut.model_validate(child) for child in children],
        )
        for parent, children in tree
    ]
