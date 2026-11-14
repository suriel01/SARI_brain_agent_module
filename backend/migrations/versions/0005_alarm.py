"""alarm: state machine status, timeline and active supervision faults.

Additive only: three new tables; nothing existing is touched. The status row is created on first
use as `armed_away`, which keeps the pre-Phase-B behavior until an operator disarms.

Revision ID: 0005_alarm
Revises: 0004_node_flags
Create Date: 2026-11-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '0005_alarm'
down_revision: Union[str, Sequence[str], None] = '0004_node_flags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('alarm_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=True),
    sa.Column('since', sa.Float(), nullable=False),
    sa.Column('deadline', sa.Float(), nullable=True),
    sa.Column('cause', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('alarm_event',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('at', sa.Float(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('from_state', sa.String(length=20), nullable=True),
    sa.Column('to_state', sa.String(length=20), nullable=True),
    sa.Column('cause', sa.String(length=200), nullable=False),
    sa.Column('actor', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alarm_event_at'), 'alarm_event', ['at'], unique=False)
    op.create_table('alarm_fault',
    sa.Column('device_id', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('since', sa.Float(), nullable=False),
    sa.Column('reason', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('device_id')
    )


def downgrade() -> None:
    op.drop_table('alarm_fault')
    op.drop_index(op.f('ix_alarm_event_at'), table_name='alarm_event')
    op.drop_table('alarm_event')
    op.drop_table('alarm_state')
