"""add city to spots

Revision ID: f2c9d4e1a705
Revises: e7a3b1c4d890
Create Date: 2026-05-24 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f2c9d4e1a705'
down_revision: Union[str, Sequence[str], None] = 'e7a3b1c4d890'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE spots ADD COLUMN IF NOT EXISTS city VARCHAR(255) NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.drop_column('spots', 'city')
