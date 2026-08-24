"""What a student thought of a course, once they were actually in it.

One row per person per course -- `uq_reviews_course_user`. Reviewing twice is
editing the first review, not writing a second one, and the constraint is what
makes "my review" a question with one answer.

Both foreign keys cascade, unlike `enrollments`, whose course key is RESTRICT.
The difference is deliberate: an enrolment is something a student keeps and a
course must not be deleted out from under it, while a review is *about* the
course and means nothing without it.

`courses.rating_avg` and `courses.rating_count` are the denormalised summary of
this table. They are rewritten in the same transaction as every write here --
see `app/services/reviews.py` -- and `scripts/rebuild_course_stats.py` can
recompute them from these rows at any time.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# A review is a paragraph, not an essay. Long enough to explain a low rating.
COMMENT_MAX_LENGTH = 2000

MIN_RATING = 1
MAX_RATING = 5


class Review(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reviews"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 1-5 stars. Integer like every other whole number in this schema; the
    # range is held by the constraint below rather than by the column type.
    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    # Optional: a rating on its own is a complete review. NULL means the person
    # rated without writing, which is not the same as writing nothing -- hence
    # the constraint against an empty string sneaking in as a third state.
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        CheckConstraint(
            "comment IS NULL OR length(btrim(comment)) > 0",
            name="ck_reviews_comment_not_blank",
        ),
        UniqueConstraint("course_id", "user_id", name="uq_reviews_course_user"),
        # The course page reads this table one way only: this course's reviews,
        # newest first. The unique constraint's index cannot serve that sort,
        # so the listing gets its own.
        Index("ix_reviews_course_created", "course_id", text("created_at DESC")),
    )

    def __repr__(self) -> str:
        return f"<Review {self.course_id} {self.rating}★>"
