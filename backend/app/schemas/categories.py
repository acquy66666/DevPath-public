"""The category tree, as the course form needs it."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    position: int


class CategoryTree(CategoryOut):
    """A top-level category with the ones nested under it.

    Always a list, empty when there are none: a client rendering a `<select>`
    should not have to tell "no children" from "children unknown".
    """

    children: list[CategoryOut] = []


# --- The admin's side -------------------------------------------------------

NAME_MAX_LENGTH = 100


def _name(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise ValueError("Tên danh mục không được để trống")
    return text


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    #: Null for a top-level category; otherwise a top-level one to nest under.
    parent_id: uuid.UUID | None = None

    _strip = field_validator("name")(_name)


class CategoryUpdate(BaseModel):
    """Only what is sent changes. `parent_id: null` sent means "move to the top"."""

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    parent_id: uuid.UUID | None = None

    _strip = field_validator("name")(_name)


class CategoryOrderIn(BaseModel):
    #: The level being ordered: null for the top level.
    parent_id: uuid.UUID | None = None
    ids: list[uuid.UUID] = Field(min_length=1)


class AdminCategoryOut(CategoryOut):
    parent_id: uuid.UUID | None
    #: Courses filed directly here, taken-down ones excluded.
    courses_count: int


class AdminCategoryTree(AdminCategoryOut):
    children: list[AdminCategoryOut] = []
