"""add kind to osm_roads

Revision ID: a3d5f7b9c1e2
Revises: c1d9e2f4a6b8
Create Date: 2026-10-03 00:00:00.000000

Purely additive nullable column. On MySQL this uses ALGORITHM=INSTANT, a
metadata-only change: a table-rebuilding ALTER on osm_roads (millions of
rows) once failed in production with "table is full" for lack of disk
headroom (see f8a1b2c3d4e5). INSTANT fails loudly instead of silently
falling back to a rebuild if MySQL can't honor it.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3d5f7b9c1e2"
down_revision: Union[str, None] = "c1d9e2f4a6b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "mysql":
        op.execute("ALTER TABLE osm_roads ADD COLUMN kind VARCHAR(16) NULL, ALGORITHM=INSTANT")
    else:
        op.add_column("osm_roads", sa.Column("kind", sa.String(16), nullable=True))


def downgrade() -> None:
    # Destructive: per CLAUDE.md, never run against production without
    # Rachel's explicit confirmation, three separate times.
    op.drop_column("osm_roads", "kind")
