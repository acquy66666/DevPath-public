from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class RefreshToken(Base, UUIDPrimaryKeyMixin):
    """One row per signed-in session.

    No TimestampMixin: docs/database-design.md gives this table `created_at`
    only. A row is written once and then at most revoked, and `revoked_at`
    records that more precisely than a generic `updated_at` would.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # SHA-256 hex of the token the client holds. The raw token is never stored,
    # so a leaked database dump yields nothing anyone can sign in with.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set on rotation, sign-out, or when a stolen token is detected.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The token this one was rotated into; NULL when it was revoked any other
    # way. Only a rotated token whose replacement is still live may come back
    # within the reuse leeway (services/auth.py::rotate_refresh_token).
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
    )

    # Both purely informational -- they drive the "devices signed in" screen.
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(INET)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("uq_refresh_tokens_token_hash", "token_hash", unique=True),
        # Revoking every session of one user is a single indexed delete.
        Index("ix_refresh_tokens_user_id", "user_id"),
        # Deleting a row (a user's cascade, an expiry sweep) has to find the
        # rows that point at it to null them; without this that is a scan per
        # deleted row.
        Index("ix_refresh_tokens_replaced_by_id", "replaced_by_id"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} expires={self.expires_at:%Y-%m-%d}>"
