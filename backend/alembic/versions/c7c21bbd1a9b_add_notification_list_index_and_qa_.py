"""add_notification_list_index_and_qa_question

What the notification bell and its page need from the table `8f1cea268f50`
created.

* **`ix_notifications_user_created`** (`user_id`, `created_at DESC`), not
  partial: the page lists read and unread notifications together, newest
  first, and the existing `ix_notifications_user_unread` only covers the
  unread ones. It is also what finds a user's rows when the user is deleted.
* **`ck_notifications_type`** gains `qa_question` -- a learner asked a question
  in a course you teach -- so the instructor hears about a question the way the
  learner hears about its answer. A closed list on purpose: each type has its
  own payload and its own wording on the page.

The downgrade deletes `qa_question` rows before narrowing the CHECK back,
because the old constraint cannot be restored over rows it forbids.

Revision ID: c7c21bbd1a9b
Revises: 8f1cea268f50
Create Date: 2026-09-29 15:32:47.422861

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c7c21bbd1a9b'
down_revision: str | None = '8f1cea268f50'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        'ix_notifications_user_created',
        'notifications',
        ['user_id', sa.literal_column('created_at DESC')],
        unique=False,
    )
    op.drop_constraint('ck_notifications_type', 'notifications', type_='check')
    op.create_check_constraint(
        'ck_notifications_type', 'notifications', "type IN ('qa_reply', 'qa_question')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE type = 'qa_question'")
    op.drop_constraint('ck_notifications_type', 'notifications', type_='check')
    op.create_check_constraint(
        'ck_notifications_type', 'notifications', "type IN ('qa_reply')"
    )
    op.drop_index('ix_notifications_user_created', table_name='notifications')
