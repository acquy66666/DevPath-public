"""add_lesson_progress

Revision ID: b6dea13f199c
Revises: 991bc02a257b
Create Date: 2026-08-23 16:22:41.203551

Hand-written for the same reason as `991bc02a257b`: no local database to
autogenerate against. `alembic check` in CI is what proves it matches the model.

`docs/database-design.md` also lists `ix_lesson_progress_enrollment`. It is not
created here: the unique constraint's index already leads with
`enrollment_id`, so a separate index on that column alone would be a second
copy of the same B-tree, paid for on every heartbeat write. The document has
been updated to say so.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b6dea13f199c'
down_revision: str | None = '991bc02a257b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'lesson_progress',
        sa.Column('enrollment_id', sa.UUID(), nullable=False),
        sa.Column('lesson_id', sa.UUID(), nullable=False),
        sa.Column('last_position_s', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('last_position_s >= 0', name='ck_lesson_progress_position_non_negative'),
        # Both CASCADE: progress belongs to an enrolment in a lesson, and means
        # nothing once either of them is gone.
        sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('enrollment_id', 'lesson_id', name='uq_lesson_progress_enrollment_lesson'),
    )


def downgrade() -> None:
    op.drop_table('lesson_progress')
