"""add pref_map_controls to users

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-26 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col['name'] for col in inspect(bind).get_columns('users')}
    if 'pref_map_controls' not in cols:
        op.execute("ALTER TABLE users ADD COLUMN pref_map_controls BOOLEAN NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.drop_column('users', 'pref_map_controls')
