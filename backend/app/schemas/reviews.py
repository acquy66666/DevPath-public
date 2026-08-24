"""Course reviews on the wire."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.review import COMMENT_MAX_LENGTH, MAX_RATING, MIN_RATING
from app.schemas.pagination import Page


class ReviewUpsert(BaseModel):
    """A rating, and optionally what lies behind it.

    There is no separate create and update body: writing a review twice is
    editing the first one, so both directions send the same fields.
    """

    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    comment: str | None = Field(default=None, max_length=COMMENT_MAX_LENGTH)

    @field_validator("comment")
    @classmethod
    def _blank_is_absent(cls, value: str | None) -> str | None:
        """A textarea the reader left alone arrives as "" or "   ".

        That is the same thing as not writing a comment, and storing it as an
        empty string would make three states out of two.
        """
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReviewAuthorOut(BaseModel):
    """The reviewer as the page shows them -- no email, like the instructor."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    avatar_url: str | None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    rating: int
    comment: str | None
    author: ReviewAuthorOut
    created_at: datetime
    updated_at: datetime


class CourseReviewsOut(Page[ReviewOut]):
    """One page of reviews, plus the summary the heading above them shows.

    The standard `{items, total, page, page_size}` envelope with two fields
    added, rather than a second request: writing a review moves the average, so
    the list and the average have to be refetched together anyway, and sending
    them apart is how a page ends up showing four stars over five reviews that
    average 4.2.
    """

    rating_avg: Decimal
    rating_count: int
