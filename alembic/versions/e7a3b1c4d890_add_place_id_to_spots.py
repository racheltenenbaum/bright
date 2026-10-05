"""add place_id to spots

Revision ID: e7a3b1c4d890
Revises: 304857bc1f56
Create Date: 2026-05-24 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = 'e7a3b1c4d890'
down_revision: Union[str, Sequence[str], None] = '304857bc1f56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # spots was first created outside migrations (production already had it
    # when this ran), so a fresh database reaches here without it. Build the
    # original table here so `upgrade head` works from empty — e.g. staging.
    if not inspect(bind).has_table('spots'):
        op.create_table(
            'spots',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('address', sa.String(length=512), nullable=False),
            sa.Column('lat', sa.Float(), nullable=False),
            sa.Column('lng', sa.Float(), nullable=False),
            sa.Column('icon', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_spots_id'), 'spots', ['id'], unique=False)
    cols = {col['name'] for col in inspect(bind).get_columns('spots')}
    if 'place_id' not in cols:
        op.execute("ALTER TABLE spots ADD COLUMN place_id VARCHAR(255)")


def downgrade() -> None:
    op.drop_column('spots', 'place_id')
