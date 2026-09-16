"""What the RAG chatbot is allowed to read: the course's own words, cut up.

A chunk is one passage of one lesson, plus the embedding of that passage. The
assistant answers by embedding the student's question, finding the nearest
chunks *inside one course*, and quoting them back with a link to the lesson
they came from. That last part is why `lesson_id` is not nullable: a chunk
nobody can cite would be an answer the student has to take on faith, and
"trả lời kèm trích nguồn" is a gate condition of this phase, not a nicety.

`course_id` is the one denormalised column here. It is reachable the long way
round -- lesson → section → course -- but every retrieval filters by it, and
paying for two joins around a vector scan on every question asked is the kind
of cost that only ever grows. The ingest job writes both columns together and
re-ingest deletes by `lesson_id`, so the two cannot drift apart unless someone
edits rows by hand.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# The width of one embedding, fixed in the column type and therefore in the
# schema: 768 is the native size of Gemini `text-embedding-004` and also a
# valid Matryoshka truncation of `gemini-embedding-001`, so the choice of model
# can still change without a rewrite of every row. It is also under pgvector's
# 2000-dimension ceiling for an HNSW index on `vector`; the full 3072 of
# `gemini-embedding-001` is not, and would have to be stored as `halfvec`.
EMBEDDING_DIMENSIONS = 768


class DocChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One retrievable passage of course material."""

    __tablename__ = "doc_chunks"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Where the passage sits in the lesson. It makes re-ingest idempotent
    # (same lesson, same slot, one row) and lets a later retrieval widen a hit
    # into its neighbours, which is how a citation gets enough context to read
    # as a quotation rather than a fragment.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Counted at ingest by whatever did the chunking. Stored because the
    # retrieval step has a prompt budget to fill and must know the size of what
    # it is about to put in it -- counting tokens again at query time would
    # mean re-tokenising every candidate chunk.
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=False
    )
    # Which model produced the vector above. Two embedding models can share a
    # width and still place the same sentence somewhere else entirely, so a
    # table holding both silently returns nonsense instead of an error. The
    # plan already names "Gemini API đổi/giới hạn quota" as a live risk; this
    # column is what makes the day it happens a query instead of a mystery.
    embedding_model: Mapped[str] = mapped_column(String(60), nullable=False)

    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_doc_chunks_chunk_index"),
        CheckConstraint("length(content) > 0", name="ck_doc_chunks_content_not_empty"),
        CheckConstraint("token_count > 0", name="ck_doc_chunks_token_count"),
        # Re-ingesting a lesson must not double it. The ingest job deletes the
        # lesson's chunks and writes them again; if a crash ever leaves it
        # half-done, this is what refuses the second copy.
        UniqueConstraint(
            "lesson_id", "chunk_index", name="uq_doc_chunks_lesson_chunk"
        ),
        # The filter that runs before every vector search: one course's chunks
        # and nothing else. pgvector filters after the index scan, so this
        # index is what keeps a course-scoped question from reading the whole
        # table once the corpus outgrows one course.
        Index("ix_doc_chunks_course_id", "course_id"),
        # Approximate nearest neighbour, cosine distance -- the operator class
        # has to match the operator the query uses (`<=>`), or the planner
        # ignores the index and silently falls back to a sequential scan. Build
        # parameters (m=16, ef_construction=64) are left at pgvector's
        # defaults; there is nothing to tune them against until the corpus is
        # real, and the numbers to tune them with will be in this phase's
        # evidence.
        Index(
            "ix_doc_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<DocChunk {self.lesson_id} #{self.chunk_index}>"
