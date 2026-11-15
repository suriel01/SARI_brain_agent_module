"""rate limits: login/PIN failure counters shared by every API worker.

Additive only: one new table; nothing existing is touched.

Revision ID: 0003_rate_limits
Revises: 0002_runtime_state
Create Date: 2026-11-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '0003_rate_limits'
down_revision: Union[str, Sequence[str], None] = '0002_runtime_state'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('rate_limit',
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('failures', sa.JSON(), nullable=False),
    sa.Column('locked_until', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('rate_limit')
