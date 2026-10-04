"""add usual_walking_speed_mps to users

Revision ID: b7e2c9d4f1a3
Revises: a3d5f7b9c1e2
Create Date: 2026-10-04 00:00:00.000000

Purely additive nullable column, learned from Go-mode walks.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7e2c9d4f1a3"
down_revision: Union[str, None] = "a3d5f7b9c1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("usual_walking_speed_mps", sa.Float(), nullable=True))


def downgrade() -> None:
    # Destructive: per CLAUDE.md, never run against production without
    # Rachel's explicit confirmation, three separate times.
    op.drop_column("users", "usual_walking_speed_mps")
