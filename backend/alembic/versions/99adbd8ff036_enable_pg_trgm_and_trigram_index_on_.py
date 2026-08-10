"""enable pg_trgm and trigram index on master_records name

Revision ID: 99adbd8ff036
Revises: 5b2c4935f815
Create Date: 2026-08-10 00:40:51.644081

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99adbd8ff036'
down_revision: Union[str, None] = '5b2c4935f815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_master_records_name_trgm ON master_records USING gin (name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_master_records_name_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
