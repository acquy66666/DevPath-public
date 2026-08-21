"""Course request and response bodies."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.course import LEVELS

TITLE_MAX_LENGTH = 200
SUBTITLE_MAX_LENGTH = 300

# NUMERIC(12,2) in VND.
PRICE_MAX_DIGITS = 12
PRICE_DECIMAL_PLACES = 2

Level = Literal[LEVELS]  # type: ignore[valid-type]


def _quantise_price(value: Decimal) -> Decimal:
    """Money always carries its two decimals, so "0" comes back as "0.00"."""
    return value.quantize(Decimal("0.01"))


class CourseCreate(BaseModel):
    """What an instructor sends to start a course.

    No `instructor_id`, no `status`: the first comes from the token, the second
    is a transition with rules rather than a field.
    """

    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    category_id: uuid.UUID
    subtitle: str | None = Field(default=None, max_length=SUBTITLE_MAX_LENGTH)
    description: str | None = None
    thumbnail_url: str | None = None
    price: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        max_digits=PRICE_MAX_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
    )
    level: Level = "beginner"
    language: str = Field(default="vi", max_length=10)

    _quantise = field_validator("price")(_quantise_price)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Tiêu đề không được để trống")
        return stripped


class CourseUpdate(BaseModel):
    """Every field optional: a PATCH says what changed, not what exists.

    The slug is absent on purpose -- it is minted once from the first title, and
    a URL that has been shared has to keep working after a rename.
    """

    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    category_id: uuid.UUID | None = None
    subtitle: str | None = Field(default=None, max_length=SUBTITLE_MAX_LENGTH)
    description: str | None = None
    thumbnail_url: str | None = None
    price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=PRICE_MAX_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
    )
    level: Level | None = None
    language: str | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def refuse_clearing_what_cannot_be_empty(self) -> "CourseUpdate":
        """`null` means "clear this" in a PATCH, and these columns are NOT NULL.

        Without this the null would travel all the way to Postgres and come
        back as a 500 instead of a 422 pointing at the field.
        """
        for name in ("title", "category_id", "price", "level", "language"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"Trường '{name}' không thể để trống")
        return self

    @field_validator("price")
    @classmethod
    def quantise(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _quantise_price(value)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Tiêu đề không được để trống")
        return stripped


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instructor_id: uuid.UUID
    category_id: uuid.UUID
    title: str
    slug: str
    subtitle: str | None
    description: str | None
    thumbnail_url: str | None
    price: Decimal
    level: str
    language: str
    status: str
    published_at: datetime | None
    rating_avg: Decimal
    rating_count: int
    students_count: int
    duration_total_s: int
    created_at: datetime
    updated_at: datetime
