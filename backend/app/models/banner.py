"""The banners across the top of the homepage, curated by an admin.

A banner shows when it is switched on **and** today falls inside its window:
`is_active` is the admin's hand on the switch, `starts_at`/`ends_at` let a
campaign banner go up and come down on its own. Either bound may be empty --
no start means "already", no end means "until switched off".

`image_url` is the public URL of a picture uploaded to the bucket under
`banners/`; the service only accepts keys there, so a banner cannot be pointed
at a lecture video or somebody's avatar. `link_url` is where clicking goes: a
path on this site or an absolute `http(s)` address, checked by the request
schema.

The partial index covers what the homepage asks on every visit -- switched-on
banners in order -- and nothing it never reads.
"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

BANNER_TITLE_MAX_LENGTH = 120


class Banner(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "banners"

    #: Shown over the picture and read out as its text alternative.
    title: Mapped[str] = mapped_column(String(BANNER_TITLE_MAX_LENGTH), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("length(title) > 0", name="ck_banners_title_not_empty"),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name="ck_banners_period",
        ),
        Index("ix_banners_active", "position", postgresql_where=text("is_active")),
    )

    def __repr__(self) -> str:
        return f"<Banner {self.title!r}>"
