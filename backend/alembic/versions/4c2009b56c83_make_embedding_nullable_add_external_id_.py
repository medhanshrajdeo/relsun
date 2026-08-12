"""make embedding nullable, add external_id column

Revision ID: 4c2009b56c83
Revises: 99adbd8ff036
Create Date: 2026-08-11 17:51:18.884296

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '4c2009b56c83'
down_revision: Union[str, None] = '99adbd8ff036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate also proposed dropping+recreating ix_master_records_name_trgm
    # (a false positive — that GIN/gin_trgm_ops index was created via raw SQL in
    # 99adbd8ff036 and isn't visible to SQLAlchemy metadata comparison). Left untouched.
    op.add_column('master_records', sa.Column('external_id', sa.String(length=20), nullable=True))
    op.alter_column('master_records', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               nullable=True)
    op.create_index(op.f('ix_master_records_external_id'), 'master_records', ['external_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_master_records_external_id'), table_name='master_records')
    op.alter_column('master_records', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               nullable=False)
    op.drop_column('master_records', 'external_id')
