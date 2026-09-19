"""add_quiz_question_review

Which questions a model drafted, and when the instructor signed each one off.
A quiz holding a drafted question that nobody reviewed cannot be published;
that rule lives in the service, and these two columns are what it reads.

Autogenerate found both columns and missed the check constraint (it does not
compare CHECKs), so `ck_quiz_questions_review_ai_only` is written by hand.
Every existing row was typed by an instructor -- the generator did not exist
before this revision -- so `false` / NULL is the true value for all of them,
not a placeholder.

Revision ID: ca9e1c7ffdbb
Revises: 42fff7804290
Create Date: 2026-09-19 20:27:34.791393

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'ca9e1c7ffdbb'
down_revision: str | None = '42fff7804290'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'quiz_questions',
        sa.Column('ai_generated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column('quiz_questions', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        'ck_quiz_questions_review_ai_only',
        'quiz_questions',
        'ai_generated OR reviewed_at IS NULL',
    )


def downgrade() -> None:
    op.drop_constraint('ck_quiz_questions_review_ai_only', 'quiz_questions', type_='check')
    op.drop_column('quiz_questions', 'reviewed_at')
    op.drop_column('quiz_questions', 'ai_generated')
