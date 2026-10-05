"""add_refresh_tokens_replaced_by_id

Which token a refresh token was rotated into. Lets `rotate_refresh_token` tell
a token that was *replaced* moments ago -- sent again by a second tab sharing
the cookie -- from one that was signed out or revoked with every other session,
and allow only the first back within the reuse leeway. Rows rotated before this
migration keep NULL and so get no leeway, which is the old behaviour.

The constraint is named the way Postgres names the inline foreign keys of the
other tables (`<table>_<column>_fkey`), so a later drop can name it.

Revision ID: abb01d258134
Revises: 551da64fc983
Create Date: 2026-10-05 01:02:28.272397

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'abb01d258134'
down_revision: str | None = '551da64fc983'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('refresh_tokens', sa.Column('replaced_by_id', sa.UUID(), nullable=True))
    op.create_index(
        'ix_refresh_tokens_replaced_by_id', 'refresh_tokens', ['replaced_by_id'], unique=False
    )
    op.create_foreign_key(
        'refresh_tokens_replaced_by_id_fkey',
        'refresh_tokens',
        'refresh_tokens',
        ['replaced_by_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('refresh_tokens_replaced_by_id_fkey', 'refresh_tokens', type_='foreignkey')
    op.drop_index('ix_refresh_tokens_replaced_by_id', table_name='refresh_tokens')
    op.drop_column('refresh_tokens', 'replaced_by_id')
