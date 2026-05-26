"""add pref_map_type to users

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-26 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col['name'] for col in inspect(bind).get_columns('users')}
    if 'pref_map_type' not in cols:
        op.execute("ALTER TABLE users ADD COLUMN pref_map_type VARCHAR(20) NOT NULL DEFAULT 'roadmap'")


def downgrade() -> None:
    op.drop_column('users', 'pref_map_type')
