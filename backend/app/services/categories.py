"""The category tree: reading it, and the admin curating it.

Two levels deep by design (see `models/category.py`), so the whole thing is one
query and a grouping pass -- there is no recursion to write and no depth to
guard against. Postgres cannot hold the depth cheaply, so every write here
does: a parent must itself be top-level, and a category that has children
cannot be moved under another.

**The slug never changes after creation.** It is made from the first name
(`lap-trinh-web`), with the courses' random suffix only when that is taken, and
renaming keeps it -- anything that already points at it keeps working.

**Deleting is refused while anything uses the category.** `courses.category_id`
is `ON DELETE RESTRICT`, soft-deleted courses included (they are still rows,
and still enrolled in), and a parent with children would orphan them. Both
answer 409 with what is in the way, rather than letting the foreign key fail
as a 500.
"""

import uuid
from dataclasses import dataclass

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models import Category, Course
from app.services.slug import slugify, unique_slug


class CategoryNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "CATEGORY_NOT_FOUND"


class CategoryTooDeepError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CATEGORY_TOO_DEEP"


class CategoryNameTakenError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CATEGORY_NAME_TAKEN"


class CategoryInUseError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CATEGORY_IN_USE"


class CategoryHasChildrenError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "CATEGORY_HAS_CHILDREN"


class InvalidCategoryOrderError(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_ORDER"


# --- Reading ---------------------------------------------------------------


async def list_tree(session: AsyncSession) -> list[tuple[Category, list[Category]]]:
    """Every category, parents first, each with its children in order.

    Ordered by `position` then `name`: position is what an admin arranges, and
    the name keeps rows that share a position from swapping places between two
    requests.
    """
    rows = list(
        await session.scalars(
            select(Category).order_by(Category.position, Category.name)
        )
    )

    children: dict = {}
    for row in rows:
        if row.parent_id is not None:
            children.setdefault(row.parent_id, []).append(row)

    return [(row, children.get(row.id, [])) for row in rows if row.parent_id is None]


async def course_counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    """Courses filed directly under each category, taken-down ones excluded."""
    rows = await session.execute(
        select(Course.category_id, func.count())
        .where(Course.deleted_at.is_(None))
        .group_by(Course.category_id)
    )
    return {category_id: count for category_id, count in rows}


# --- Writing (admin) -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Unset:
    """Marks "not sent" apart from an explicit null (move to the top level)."""


UNSET = Unset()


async def _get(session: AsyncSession, category_id: uuid.UUID) -> Category:
    category = await session.get(Category, category_id)
    if category is None:
        raise CategoryNotFoundError("Không tìm thấy danh mục")
    return category


async def _check_parent(
    session: AsyncSession, parent_id: uuid.UUID | None, moving: Category | None = None
) -> None:
    if parent_id is None:
        return
    if moving is not None and parent_id == moving.id:
        raise CategoryTooDeepError("Danh mục không thể nằm trong chính nó")
    parent = await session.get(Category, parent_id)
    if parent is None:
        raise CategoryNotFoundError("Không tìm thấy danh mục cha")
    if parent.parent_id is not None:
        raise CategoryTooDeepError("Danh mục chỉ có hai cấp: chọn một danh mục cấp trên cùng")
    if moving is not None:
        has_children = await session.scalar(
            select(func.count()).select_from(Category).where(Category.parent_id == moving.id)
        )
        if has_children:
            raise CategoryTooDeepError(
                "Danh mục này đang có danh mục con nên không chuyển vào danh mục khác được"
            )


async def _check_name(
    session: AsyncSession, name: str, parent_id: uuid.UUID | None, skip: uuid.UUID | None = None
) -> None:
    """Two siblings with the same name would be two identical rows in every menu."""
    same = select(Category.id).where(
        func.lower(Category.name) == name.lower(),
        Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id,
    )
    if skip is not None:
        same = same.where(Category.id != skip)
    if await session.scalar(same.limit(1)) is not None:
        raise CategoryNameTakenError(f"Đã có danh mục tên “{name}” ở cùng cấp")


def _siblings(parent_id: uuid.UUID | None):
    return Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id


async def _next_position(session: AsyncSession, parent_id: uuid.UUID | None) -> int:
    last = await session.scalar(select(func.max(Category.position)).where(_siblings(parent_id)))
    return 0 if last is None else last + 1


async def _free_slug(session: AsyncSession, name: str) -> str:
    plain = slugify(name)
    taken = await session.scalar(select(Category.id).where(Category.slug == plain))
    return plain if taken is None else unique_slug(name)


async def create(session: AsyncSession, *, name: str, parent_id: uuid.UUID | None) -> Category:
    await _check_parent(session, parent_id)
    await _check_name(session, name, parent_id)
    category = Category(
        name=name,
        slug=await _free_slug(session, name),
        parent_id=parent_id,
        position=await _next_position(session, parent_id),
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update(
    session: AsyncSession,
    category_id: uuid.UUID,
    *,
    name: str | None,
    parent_id: uuid.UUID | None | Unset,
) -> Category:
    """Rename, move, or both. Moving puts it last among its new siblings."""
    category = await _get(session, category_id)
    moving = not isinstance(parent_id, Unset) and parent_id != category.parent_id
    target_parent = category.parent_id if isinstance(parent_id, Unset) else parent_id

    if moving:
        await _check_parent(session, target_parent, moving=category)
    if name is not None or moving:
        await _check_name(session, name or category.name, target_parent, skip=category.id)

    if name is not None:
        category.name = name
    if moving:
        category.parent_id = target_parent
        category.position = await _next_position(session, target_parent)

    await session.commit()
    await session.refresh(category)
    return category


async def reorder(
    session: AsyncSession, parent_id: uuid.UUID | None, ordered_ids: list[uuid.UUID]
) -> None:
    """Set the order of one level: the whole list, exactly once each.

    Like the curriculum: the client knows the final order, so it sends it, and
    a list that leaves a sibling out would strand it at its old position.
    """
    siblings = list(await session.scalars(select(Category).where(_siblings(parent_id))))
    by_id = {category.id: category for category in siblings}
    if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(by_id):
        raise InvalidCategoryOrderError(
            "Danh sách sắp xếp phải có đủ và chỉ một lần mỗi danh mục cùng cấp"
        )
    for position, category_id in enumerate(ordered_ids):
        by_id[category_id].position = position
    await session.commit()


async def delete(session: AsyncSession, category_id: uuid.UUID) -> None:
    category = await _get(session, category_id)

    children = await session.scalar(
        select(func.count()).select_from(Category).where(Category.parent_id == category.id)
    )
    if children:
        raise CategoryHasChildrenError(
            f"Danh mục đang có {children} danh mục con — chuyển hoặc xóa chúng trước"
        )
    # Every course row, taken-down ones included: the foreign key counts them.
    courses = await session.scalar(
        select(func.count()).select_from(Course).where(Course.category_id == category.id)
    )
    if courses:
        raise CategoryInUseError(
            f"Còn {courses} khóa học thuộc danh mục này — chuyển chúng sang danh mục khác trước"
        )

    await session.delete(category)
    await session.commit()
