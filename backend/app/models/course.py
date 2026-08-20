import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

STATUSES = ("draft", "pending_review", "published", "rejected")
LEVELS = ("beginner", "intermediate", "advanced")


class Course(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "courses"

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Generated from the title plus a short suffix, so two courses may share a
    # title without fighting over the URL.
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)

    # VND. Numeric, never float -- 0 means free.
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    level: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'beginner'")
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'vi'")
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'draft'")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Denormalised from reviews and enrollments so the listing page can sort on
    # an index. backend/scripts/rebuild_course_stats.py recomputes them.
    rating_avg: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0")
    )
    rating_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    students_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duration_total_s: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    # Filled by a Postgres trigger in Phase 2, when full-text search is built
    # and the Vietnamese text configuration gets decided.
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    # The one soft-deleted table: a course pulled from sale must stay watchable
    # for students who already bought it.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'pending_review', 'published', 'rejected')",
            name="ck_courses_status",
        ),
        CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_courses_level",
        ),
        CheckConstraint("price >= 0", name="ck_courses_price_non_negative"),
        CheckConstraint(
            "rating_avg BETWEEN 0 AND 5 AND rating_count >= 0",
            name="ck_courses_rating_range",
        ),
        CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_courses_published_at",
        ),
        CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL",
            name="ck_courses_rejection_reason",
        ),
        Index("uq_courses_slug", "slug", unique=True),
        # Listing queries always exclude soft-deleted rows, so the index does too.
        Index(
            "ix_courses_listing",
            "status",
            text("published_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_courses_rating",
            "status",
            text("rating_avg DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_courses_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_courses_category_id", "category_id"),
        Index("ix_courses_instructor_id", "instructor_id"),
    )

    def __repr__(self) -> str:
        return f"<Course {self.slug}>"
