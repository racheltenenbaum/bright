"""add place_id to spots

Revision ID: e7a3b1c4d890
Revises: 304857bc1f56
Create Date: 2026-05-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = 'e7a3b1c4d890'
down_revision: Union[str, Sequence[str], None] = '304857bc1f56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col['name'] for col in inspect(bind).get_columns('spots')}
    if 'place_id' not in cols:
        op.execute("ALTER TABLE spots ADD COLUMN place_id VARCHAR(255)")


def downgrade() -> None:
    op.drop_column('spots', 'place_id')
