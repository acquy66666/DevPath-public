"""add_instructor_applications

A learner no longer makes themself an instructor; they apply and an admin
decides.

* **`instructor_applications`**: `user_id`, the learner's optional
  `motivation`, `status` (`pending`/`approved`/`rejected`), `decided_by`,
  `decided_at`, `rejection_reason`. `decided_at` is set exactly when the
  status leaves `pending`, and only a rejection carries (and must carry) a
  reason.
* **`uq_instructor_applications_pending`**, partial: one pending application
  per person; applying again after a decision is allowed.
* **`ix_instructor_applications_status`** (status, created_at) for the admin
  queue, **`ix_instructor_applications_user`** for "my latest application".
* **`ck_notifications_type`** gains `instructor_application_approved` and
  `instructor_application_rejected` (with the reason).

Instructors who promoted themselves before this revision stay instructors:
nothing here touches `users.role`.

The downgrade refuses while notifications of the two new types exist -- the
old constraint cannot be restored over rows it forbids.

Revision ID: 7c885a800a6a
Revises: ad80b1df78a1
Create Date: 2026-11-02 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '7c885a800a6a'
down_revision: str | None = 'ad80b1df78a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TYPES = (
    "type IN ('qa_reply', 'qa_question', 'course_approved', 'course_rejected', "
    "'course_taken_down', 'instructor_tier_changed')"
)
NEW_TYPES = (
    "type IN ('qa_reply', 'qa_question', 'course_approved', 'course_rejected', "
    "'course_taken_down', 'instructor_tier_changed', "
    "'instructor_application_approved', 'instructor_application_rejected')"
)


def upgrade() -> None:
    op.create_table(
        'instructor_applications',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('motivation', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('decided_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name='ck_instructor_applications_status',
        ),
        sa.CheckConstraint(
            "(status = 'pending') = (decided_at IS NULL)",
            name='ck_instructor_applications_decided_at',
        ),
        sa.CheckConstraint(
            "(status = 'rejected') = (rejection_reason IS NOT NULL)",
            name='ck_instructor_applications_rejection_reason',
        ),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_instructor_applications_status',
        'instructor_applications',
        ['status', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_instructor_applications_user',
        'instructor_applications',
        ['user_id', sa.text('created_at DESC')],
        unique=False,
    )
    op.create_index(
        'uq_instructor_applications_pending',
        'instructor_applications',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.drop_constraint('ck_notifications_type', 'notifications', type_='check')
    op.create_check_constraint('ck_notifications_type', 'notifications', NEW_TYPES)


def downgrade() -> None:
    told = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM notifications WHERE type IN "
            "('instructor_application_approved', 'instructor_application_rejected')"
        )
    )
    if told:
        raise RuntimeError(
            f"{told} notification(s) about instructor applications exist; the previous "
            "constraint cannot hold them."
        )
    op.drop_constraint('ck_notifications_type', 'notifications', type_='check')
    op.create_check_constraint('ck_notifications_type', 'notifications', OLD_TYPES)

    op.drop_index(
        'uq_instructor_applications_pending',
        table_name='instructor_applications',
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index('ix_instructor_applications_user', table_name='instructor_applications')
    op.drop_index('ix_instructor_applications_status', table_name='instructor_applications')
    op.drop_table('instructor_applications')
