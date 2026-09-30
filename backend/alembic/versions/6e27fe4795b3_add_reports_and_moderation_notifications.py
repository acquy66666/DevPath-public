"""add_reports_and_moderation_notifications

What the admin's moderation work needs from the database.

* **`reports`** as designed (`reporter_id`, `target_type`, `target_id`,
  `reason`, `status`, `ix_reports_status`, the `target_type` CHECK), plus what
  closing a report has to record: `details` (the reporter's own words --
  required when `reason = 'other'`), `resolved_by`, `resolved_at`,
  `resolution_note`, `content_removed`. `reason` is a closed list rather than
  free text so the queue can be read at a glance.
* **`ix_reports_status`** carries `created_at` after `status`: the queue is
  "pending, oldest first".
* **`ix_reports_target`**: a decision closes every pending report on the same
  target, and the queue shows how many there are.
* **`uq_reports_pending_per_reporter`**, partial on the pending statuses: one
  open complaint per person per target, but reporting again after a decision
  is allowed.
* **`ck_notifications_type`** gains three types an instructor is told about:
  `course_approved`, `course_rejected` (with the reason), and
  `course_taken_down` (an admin unpublished the course after a report).

The downgrade deletes rows of the three new notification types before
narrowing the CHECK back, because the old constraint cannot be restored over
rows it forbids.

Revision ID: 6e27fe4795b3
Revises: c7c21bbd1a9b
Create Date: 2026-09-30 09:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '6e27fe4795b3'
down_revision: str | None = 'c7c21bbd1a9b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TYPES = "type IN ('qa_reply', 'qa_question')"
NEW_TYPES = (
    "type IN ('qa_reply', 'qa_question', 'course_approved', 'course_rejected', "
    "'course_taken_down')"
)


def upgrade() -> None:
    op.create_table('reports',
    sa.Column('reporter_id', sa.UUID(), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=False),
    sa.Column('target_id', sa.UUID(), nullable=False),
    sa.Column('reason', sa.String(length=20), nullable=False),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'open'"), nullable=False),
    sa.Column('resolved_by', sa.UUID(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution_note', sa.Text(), nullable=True),
    sa.Column('content_removed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("target_type IN ('course', 'review', 'qa_thread', 'qa_reply')", name='ck_reports_target_type'),
    sa.CheckConstraint("reason IN ('spam', 'offensive', 'copyright', 'misleading', 'other')", name='ck_reports_reason'),
    sa.CheckConstraint("status IN ('open', 'reviewing', 'resolved', 'dismissed')", name='ck_reports_status'),
    sa.CheckConstraint("reason <> 'other' OR details IS NOT NULL", name='ck_reports_other_has_details'),
    sa.CheckConstraint("(status IN ('resolved', 'dismissed')) = (resolved_at IS NOT NULL)", name='ck_reports_closed_at'),
    sa.CheckConstraint("NOT content_removed OR status = 'resolved'", name='ck_reports_removed_only_when_resolved'),
    sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reports_status', 'reports', ['status', 'created_at'], unique=False)
    op.create_index('ix_reports_target', 'reports', ['target_type', 'target_id'], unique=False)
    op.create_index(
        'uq_reports_pending_per_reporter',
        'reports',
        ['reporter_id', 'target_type', 'target_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'reviewing')"),
    )

    op.drop_constraint('ck_notifications_type', 'notifications', type_='check')
    op.create_check_constraint('ck_notifications_type', 'notifications', NEW_TYPES)


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE type IN "
        "('course_approved', 'course_rejected', 'course_taken_down')"
    )
    op.drop_constraint('ck_notifications_type', 'notifications', type_='check')
    op.create_check_constraint('ck_notifications_type', 'notifications', OLD_TYPES)

    op.drop_index(
        'uq_reports_pending_per_reporter',
        table_name='reports',
        postgresql_where=sa.text("status IN ('open', 'reviewing')"),
    )
    op.drop_index('ix_reports_target', table_name='reports')
    op.drop_index('ix_reports_status', table_name='reports')
    op.drop_table('reports')
