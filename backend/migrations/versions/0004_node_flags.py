"""node flags: watchdog disconnection debounce and operator tracking choice per vision node.

Moves two process-local dicts into the database so every process sees them and they survive a
restart. Additive only: one new table; nothing existing is touched.

Revision ID: 0004_node_flags
Revises: 0003_rate_limits
Create Date: 2026-11-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '0004_node_flags'
down_revision: Union[str, Sequence[str], None] = '0003_rate_limits'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('node_flags',
    sa.Column('node_id', sa.String(length=100), nullable=False),
    sa.Column('disconnect_notified', sa.Boolean(), nullable=False),
    sa.Column('tracking_enabled', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('node_id')
    )


def downgrade() -> None:
    op.drop_table('node_flags')
