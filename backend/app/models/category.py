import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)

    # Two levels only -- a top-level category has parent_id IS NULL. Postgres
    # cannot enforce the depth cheaply, so the service layer does.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        CheckConstraint(
            "parent_id IS DISTINCT FROM id", name="ck_categories_not_self_parent"
        ),
        Index("uq_categories_slug", "slug", unique=True),
        Index("ix_categories_parent_id", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"
