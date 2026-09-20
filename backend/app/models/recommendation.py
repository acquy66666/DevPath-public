"""What the recommender keeps between runs.

The collaborative half keeps nothing: it is refitted from `enrollments` every
night and lives in Redis until the next run. The content-based half cannot
work that way -- its input is a paid API call, not a SQL query -- so the
vectors are a table, and the table is what makes a rebuild cheap enough to run
nightly.

One row per course. `source_text` is the exact string that was embedded, kept
verbatim rather than hashed: the comparison that decides whether to pay for a
course again is `source_text == course_text(...)`, and a hash would answer the
same question while making "why was this re-embedded?" unanswerable. It is at
most a few thousand characters, which the course's own description already is.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.rag import EMBEDDING_DIMENSIONS


class CourseEmbedding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One course, as a point the catalogue can be measured against."""

    __tablename__ = "course_embeddings"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: Exactly the text handed to the model -- see the module docstring.
    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=False
    )
    #: Which model produced the vector. Two models can share a width and place
    #: the same sentence somewhere else entirely, so a table holding both would
    #: return nonsense instead of an error -- the similarity query compares
    #: only rows that agree with the target's model, and this is the column it
    #: agrees on. Same reasoning as `doc_chunks.embedding_model`.
    embedding_model: Mapped[str] = mapped_column(String(60), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "length(source_text) > 0", name="ck_course_embeddings_source_not_empty"
        ),
        # One vector per course, enforced rather than assumed: the rebuild
        # updates in place, and a second row would make "the" embedding of a
        # course a question about insertion order.
        Index("uq_course_embeddings_course_id", "course_id", unique=True),
        # Cosine, matching the `<=>` the similarity query uses -- an index
        # built with another operator class is ignored by the planner, which
        # falls back to a sequential scan and says nothing about it.
        #
        # On a catalogue of two dozen courses Postgres will sequential-scan
        # anyway, and should: the index earns its place at a few thousand
        # rows, which is the size this is built for rather than the size it
        # is tested at.
        Index(
            "ix_course_embeddings_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<CourseEmbedding {self.course_id}>"
