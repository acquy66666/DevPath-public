from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, text
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

    def __repr__(self) -> str:
        return f"<User {self.email}>"
