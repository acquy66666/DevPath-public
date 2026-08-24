"""add_reviews

Revision ID: 7b60984bf439
Revises: 852a7bf2510b
Create Date: 2026-08-24 10:12:41.208317

Hand-written, like the ones before it: no local database to autogenerate
against, and `alembic check` in CI is what proves it matches the model.

The table this creates is the source of `courses.rating_avg` and
`courses.rating_count`, which already exist and stay at their defaults until
the first review lands. Nothing has to backfill them: no reviews means an
average of 0 over 0 ratings, which is exactly what those columns already say.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '7b60984bf439'
down_revision: str | None = '852a7bf2510b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'reviews',
        sa.Column('course_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_reviews_rating'),
        sa.CheckConstraint(
            'comment IS NULL OR length(btrim(comment)) > 0',
            name='ck_reviews_comment_not_blank',
        ),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('course_id', 'user_id', name='uq_reviews_course_user'),
    )
    # "This course's reviews, newest first" -- the only way the table is read.
    op.create_index(
        'ix_reviews_course_created',
        'reviews',
        ['course_id', sa.text('created_at DESC')],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_reviews_course_created', table_name='reviews')
    op.drop_table('reviews')
