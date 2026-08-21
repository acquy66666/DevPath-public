"""Course contents: sections, the lessons inside them, and video assets.

`position` is an explicit integer rather than an implicit ordering, because the
instructor drags rows around and the order has to survive a reload. The unique
constraints on `(parent, position)` are **deferrable**: reordering rewrites
several rows in one transaction and would otherwise collide with itself
halfway through, before the final arrangement is even reached.
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

LESSON_TYPES = ("video", "article", "quiz", "code_exercise")
VIDEO_ASSET_STATUSES = ("uploading", "processing", "ready", "failed")


class CourseSection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A chapter. Deleting the course takes its sections with it."""

    __tablename__ = "course_sections"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "position",
            name="uq_course_sections_position",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    def __repr__(self) -> str:
        return f"<CourseSection {self.position}: {self.title}>"


class VideoAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One uploaded video and whatever the transcode worker made of it.

    Created here so `lessons.video_asset_id` has a real foreign key from the
    start; the upload flow that fills it in is the next task.
    """

    __tablename__ = "video_assets"

    # Object key on R2, not a URL: the bucket and the CDN host can change.
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    hls_manifest_key: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'uploading'")
    )
    # Why a transcode failed, kept for the instructor to read.
    error_message: Mapped[str | None] = mapped_column(Text)
    # Subtitles/transcript on R2 -- the source the RAG pipeline chunks in Phase 4.
    transcript_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploading', 'processing', 'ready', 'failed')",
            name="ck_video_assets_status",
        ),
        UniqueConstraint("storage_key", name="uq_video_assets_storage_key"),
    )

    def __repr__(self) -> str:
        return f"<VideoAsset {self.storage_key} {self.status}>"


class Lesson(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One item of the curriculum, inside a section."""

    __tablename__ = "lessons"

    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Watchable without enrolling -- the sample that sells the course.
    is_preview: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # SET NULL rather than CASCADE: losing the video must not delete the lesson
    # and shift everything after it.
    video_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_assets.id", ondelete="SET NULL")
    )
    article_content: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "type IN ('video', 'article', 'quiz', 'code_exercise')",
            name="ck_lessons_type",
        ),
        # A video asset hanging off an article lesson would never be played and
        # never be found again.
        CheckConstraint(
            "video_asset_id IS NULL OR type = 'video'",
            name="ck_lessons_video_asset_type",
        ),
        UniqueConstraint(
            "section_id",
            "position",
            name="uq_lessons_position",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    def __repr__(self) -> str:
        return f"<Lesson {self.type} {self.position}: {self.title}>"
