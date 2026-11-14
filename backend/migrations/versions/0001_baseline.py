"""baseline schema: every table the application had before Alembic (incl. physical_action_log).

Existing deployments (tables created by the old ``create_all``) are stamped at this revision by
``app.main.init_db`` instead of running it.

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-11-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('event_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('module_name', sa.String(length=100), nullable=True),
    sa.Column('event_description', sa.Text(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('embedding', Vector(768), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_event_logs_id'), 'event_logs', ['id'], unique=False)
    op.create_index(op.f('ix_event_logs_timestamp'), 'event_logs', ['timestamp'], unique=False)

    op.create_table('eye_nodes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('node_id', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('ip', sa.String(length=50), nullable=True),
    sa.Column('stream_url', sa.String(length=255), nullable=True),
    sa.Column('yolo_threshold', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eye_nodes_id'), 'eye_nodes', ['id'], unique=False)
    op.create_index(op.f('ix_eye_nodes_node_id'), 'eye_nodes', ['node_id'], unique=True)

    op.create_table('physical_action_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_name', sa.String(length=100), nullable=False),
    sa.Column('channel', sa.String(length=30), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('result', sa.String(length=20), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_physical_action_log_id'), 'physical_action_log', ['id'], unique=False)
    op.create_index(op.f('ix_physical_action_log_timestamp'), 'physical_action_log', ['timestamp'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=True),
    sa.Column('clearance_level', sa.Integer(), nullable=True),
    sa.Column('can_create_chats', sa.Boolean(), nullable=True),
    sa.Column('can_delete_chats', sa.Boolean(), nullable=True),
    sa.Column('can_rename_chats', sa.Boolean(), nullable=True),
    sa.Column('can_control_hardware', sa.Boolean(), nullable=True),
    sa.Column('can_manage_users', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.create_table('chat_threads',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_threads_id'), 'chat_threads', ['id'], unique=False)

    op.create_table('chat_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('thread_id', sa.Integer(), nullable=True),
    sa.Column('role', sa.String(length=20), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('snapshot', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)



def downgrade() -> None:
    # Dropping the baseline would delete every chat, user and audit row; never automate it.
    raise NotImplementedError("The baseline migration cannot be downgraded")
