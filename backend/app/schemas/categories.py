"""The category tree, as the course form needs it."""

import uuid

from pydantic import BaseModel, ConfigDict


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
