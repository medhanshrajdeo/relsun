"""add relationship_edges table (replaces Neo4j :OWNS graph)

Revision ID: c7e4f1a09d3b
Revises: a1f3c9d2e7b4
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e4f1a09d3b'
down_revision: Union[str, None] = 'a1f3c9d2e7b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('relationship_edges',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=False),
    sa.Column('child_id', sa.Integer(), nullable=False),
    sa.Column('is_direct_parent', sa.Boolean(), nullable=False),
    sa.Column('is_ultimate_parent', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['master_records.id']),
    sa.ForeignKeyConstraint(['child_id'], ['master_records.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('parent_id', 'child_id', name='uq_relationship_edges_parent_child'),
    )
    op.create_index(op.f('ix_relationship_edges_parent_id'), 'relationship_edges', ['parent_id'], unique=False)
    op.create_index(op.f('ix_relationship_edges_child_id'), 'relationship_edges', ['child_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_relationship_edges_child_id'), table_name='relationship_edges')
    op.drop_index(op.f('ix_relationship_edges_parent_id'), table_name='relationship_edges')
    op.drop_table('relationship_edges')
