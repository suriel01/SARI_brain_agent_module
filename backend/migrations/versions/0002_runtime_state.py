"""runtime state: actuator_state (single row), node_status and operational_log.

Replaces the process-local ``HardwareState`` so live state survives restarts and is shared by every
API worker. Additive only: three new tables and the actuator row; nothing existing is touched.

Revision ID: 0002_runtime_state
Revises: 0001_baseline
Create Date: 2026-11-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '0002_runtime_state'
down_revision: Union[str, Sequence[str], None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    actuator_state = op.create_table('actuator_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('siren_active', sa.Boolean(), nullable=False),
    sa.Column('gates_locked', sa.Boolean(), nullable=False),
    sa.Column('alert_count', sa.Integer(), nullable=False),
    sa.Column('last_alert_time', sa.Float(), nullable=False),
    sa.Column('last_alert_thread_id', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.bulk_insert(actuator_state, [{
        'id': 1, 'siren_active': False, 'gates_locked': False, 'alert_count': 0, 'last_alert_time': 0.0,
        'last_alert_thread_id': None,
    }])

    op.create_table('node_status',
    sa.Column('node_id', sa.String(length=100), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('last_seen', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('node_id')
    )
    op.create_index(op.f('ix_node_status_last_seen'), 'node_status', ['last_seen'], unique=False)

    op.create_table('operational_log',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('level', sa.String(length=20), nullable=False),
    sa.Column('camera_module', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operational_log_expires_at'), 'operational_log', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_operational_log_expires_at'), table_name='operational_log')
    op.drop_table('operational_log')
    op.drop_index(op.f('ix_node_status_last_seen'), table_name='node_status')
    op.drop_table('node_status')
    op.drop_table('actuator_state')
