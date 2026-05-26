"""add pref_max_detour to users

Revision ID: a1b2c3d4e5f6
Revises: f2c9d4e1a705
Create Date: 2026-05-26 12:00:00.000000

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
    cols = {col['name'] for col in inspect(bind).get_columns('users')}
    if 'pref_max_detour' not in cols:
        op.execute("ALTER TABLE users ADD COLUMN pref_max_detour INT NOT NULL DEFAULT 30")


def downgrade() -> None:
    op.drop_column('users', 'pref_max_detour')
