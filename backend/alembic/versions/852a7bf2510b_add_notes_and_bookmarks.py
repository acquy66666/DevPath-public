"""add_notes_and_bookmarks

Revision ID: 852a7bf2510b
Revises: b6dea13f199c
Create Date: 2026-08-23 17:05:12.664208

Hand-written, like the two before it: no local database to autogenerate
against, and `alembic check` in CI is what proves it matches the model.

Both tables point at the user rather than the enrolment, which is the
difference between them and `lesson_progress`: progress describes one run
through a course, while a note is something the person wrote and keeps.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '852a7bf2510b'
down_revision: str | None = 'b6dea13f199c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'notes',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('lesson_id', sa.UUID(), nullable=False),
        sa.Column('timestamp_s', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('timestamp_s >= 0', name='ck_notes_timestamp_non_negative'),
        sa.CheckConstraint('length(content) > 0', name='ck_notes_content_not_empty'),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Not unique: many notes down one lesson is the whole point.
    op.create_index('ix_notes_user_lesson', 'notes', ['user_id', 'lesson_id'], unique=False)

    op.create_table(
        'bookmarks',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('lesson_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'lesson_id', name='uq_bookmarks_user_lesson'),
    )


def downgrade() -> None:
    op.drop_table('bookmarks')
    op.drop_index('ix_notes_user_lesson', table_name='notes')
    op.drop_table('notes')
