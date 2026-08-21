"""One envelope for every list endpoint.

`{items, total, page, page_size}` rather than a bare array: a client that gets
an array has no way to render "trang 2 / 7" without a second request, and
adding the fields later breaks everyone at once.
"""

from pydantic import BaseModel

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
