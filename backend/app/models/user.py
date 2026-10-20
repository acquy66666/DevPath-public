import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ROLES = ("student", "instructor", "admin")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # Lowercased and trimmed in the service layer before it ever reaches here,
    # so the unique index compares what the user actually typed.
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Null for accounts that only ever sign in through Google.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Full R2 URL -- no business limit on length, so TEXT rather than VARCHAR.
    avatar_url: Mapped[str | None] = mapped_column(Text)

    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'student'")
    )

    oauth_provider: Mapped[str | None] = mapped_column(String(20))
    oauth_sub: Mapped[str | None] = mapped_column(String(255))

    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set by an admin; anything other than NULL blocks sign-in.
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: The instructor's tier, set only by an admin's decision
    #: (`instructor_tier_changes`). NULL is the first tier -- where every
    #: instructor starts -- so becoming one never has to set it.
    instructor_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instructor_tiers.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'instructor', 'admin')", name="ck_users_role"
        ),
        # An account nobody can sign in to is a support ticket waiting to happen.
        CheckConstraint(
            "password_hash IS NOT NULL OR oauth_sub IS NOT NULL",
            name="ck_users_credential",
        ),
        Index("uq_users_email", "email", unique=True),
        # Partial: password-only accounts all share a NULL oauth_sub, and NULLs
        # would not collide anyway -- the predicate makes that explicit.
        Index(
            "uq_users_oauth",
            "oauth_provider",
            "oauth_sub",
            unique=True,
            postgresql_where=text("oauth_sub IS NOT NULL"),
        ),
        Index("ix_users_role", "role"),
    )

    @property
    def has_password(self) -> bool:
        """Whether this account can be opened with a password at all.

        Derived, never stored: a Google-only account has no hash, and the
        profile page needs to know that to avoid offering a form that can only
        fail. Says nothing about the password itself.
        """
        return self.password_hash is not None

    def __repr__(self) -> str:
        return f"<User {self.email}>"
