"""add users and user_sessions tables, submitted_by/decided_by on master_data_requests

Revision ID: a1f3c9d2e7b4
Revises: ea31ae1c8001
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f3c9d2e7b4'
down_revision: Union[str, None] = 'ea31ae1c8001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=True),
    sa.Column('password_hash', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.create_table('user_sessions',
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    sa.PrimaryKeyConstraint('token')
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)

    op.add_column('master_data_requests', sa.Column('submitted_by_id', sa.Integer(), nullable=True))
    op.add_column('master_data_requests', sa.Column('decided_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f('fk_master_data_requests_submitted_by_id_users'),
        'master_data_requests', 'users', ['submitted_by_id'], ['id']
    )
    op.create_foreign_key(
        op.f('fk_master_data_requests_decided_by_id_users'),
        'master_data_requests', 'users', ['decided_by_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint(op.f('fk_master_data_requests_decided_by_id_users'), 'master_data_requests', type_='foreignkey')
    op.drop_constraint(op.f('fk_master_data_requests_submitted_by_id_users'), 'master_data_requests', type_='foreignkey')
    op.drop_column('master_data_requests', 'decided_by_id')
    op.drop_column('master_data_requests', 'submitted_by_id')

    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_table('user_sessions')

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
