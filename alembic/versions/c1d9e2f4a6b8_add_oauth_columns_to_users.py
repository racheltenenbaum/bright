"""add oauth columns to users

Revision ID: c1d9e2f4a6b8
Revises: e1f2a3b4c5d6
Create Date: 2026-09-20 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = 'c1d9e2f4a6b8'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col['name'] for col in inspect(bind).get_columns('users')}
    if 'google_sub' not in cols:
        op.execute("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255) NULL UNIQUE")
    if 'apple_sub' not in cols:
        op.execute("ALTER TABLE users ADD COLUMN apple_sub VARCHAR(255) NULL UNIQUE")
    op.execute("ALTER TABLE users MODIFY COLUMN hashed_password VARCHAR(255) NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users MODIFY COLUMN hashed_password VARCHAR(255) NOT NULL")
    op.drop_column('users', 'apple_sub')
    op.drop_column('users', 'google_sub')
