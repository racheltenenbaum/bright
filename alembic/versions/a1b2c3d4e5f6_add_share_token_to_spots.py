"""add share_token to spots

Revision ID: a1b2c3d4e5f6
Revises: f2c9d4e1a705
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f2c9d4e1a705'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col['name'] for col in inspect(bind).get_columns('spots')}
    if 'share_token' not in cols:
        op.execute("ALTER TABLE spots ADD COLUMN share_token VARCHAR(36) NULL")
        op.execute("CREATE UNIQUE INDEX ix_spots_share_token ON spots (share_token)")


def downgrade() -> None:
    op.drop_index('ix_spots_share_token', table_name='spots')
    op.drop_column('spots', 'share_token')
