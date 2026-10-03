"""drop_submissions_peak_memory_mb

`submissions.peak_memory_mb` has been NULL on every row since it was created
(86a5023fa0b8): the worker had nothing to put in it. Measured on Docker Engine
29.7 with cgroup v2, the daemon cannot supply one -- the stats endpoint carries
the current usage and no maximum while the container runs, and nothing at all
once it has exited, which is the only moment a peak means anything. The
number exists only inside the container, as `/sys/fs/cgroup/memory.peak`, so
filling the column means changing what runs in the sandbox: a process that
outlives the submission to read it. Cheap in memory -- a shell in front of
the program adds about 0.2 MiB, measured -- but it reports through the same
stderr the submission writes to and can forge, and it stands between the
submission and the exit code that the TLE and MLE verdicts are read from, so
the verdict and attack suites would have to be proven again. All for a number
no page shows and the thesis outline does not ask for, so the column goes
instead of staying a promise.

Downgrade puts the column back empty, which is all it ever was.

Revision ID: 503c1217538c
Revises: 5b10213a072e
Create Date: 2026-10-03 18:11:57.112853

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '503c1217538c'
down_revision: str | None = '5b10213a072e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('submissions', 'peak_memory_mb')


def downgrade() -> None:
    op.add_column(
        'submissions',
        sa.Column('peak_memory_mb', sa.INTEGER(), autoincrement=False, nullable=True),
    )
