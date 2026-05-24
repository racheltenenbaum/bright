"""add place_id to spots

Revision ID: e7a3b1c4d890
Revises: 304857bc1f56
Create Date: 2026-05-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7a3b1c4d890'
down_revision: Union[str, Sequence[str], None] = '304857bc1f56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('spots', sa.Column('place_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('spots', 'place_id')
