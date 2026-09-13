"""add_submission_is_trial

Revision ID: 123eb876dda5
Revises: 86a5023fa0b8
Create Date: 2026-09-12 16:24:50.550063

A trial run ("chạy thử") is a submission against the sample cases only, kept
out of the student's history. It is the same row rather than a second table:
the queue, the worker, the sandbox, the progress channel and every rule about
who may read a run are identical, and duplicating all of that to avoid one
boolean would have been the expensive way round.

The index is rebuilt rather than left alone. Autogenerate does not compare an
index predicate, so this half is written by hand: without it the history query
-- which now filters `is_trial = false` -- would scan an index dominated by
trial rows, and a student who leans on "chạy thử" produces far more of those
than of real submissions.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '123eb876dda5'
down_revision: str | None = '86a5023fa0b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'submissions',
        sa.Column('is_trial', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )

    op.drop_index('ix_submissions_user_exercise', table_name='submissions')
    op.create_index(
        'ix_submissions_user_exercise',
        'submissions',
        ['user_id', 'exercise_id', sa.text('created_at DESC')],
        postgresql_where=sa.text('is_trial = false'),
    )


def downgrade() -> None:
    op.drop_index('ix_submissions_user_exercise', table_name='submissions')
    op.create_index(
        'ix_submissions_user_exercise',
        'submissions',
        ['user_id', 'exercise_id', sa.text('created_at DESC')],
    )
    op.drop_column('submissions', 'is_trial')
