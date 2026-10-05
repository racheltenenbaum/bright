"""backfill columns no earlier migration creates

Revision ID: c8f1a2b3d4e5
Revises: b7e2c9d4f1a3
Create Date: 2026-10-05 00:00:00.000000

routes.preference/share_token/route_path and spots.description were added
to production outside migrations, so a fresh database (e.g. staging) built by
`upgrade head` lacked them. Each is added only if missing: a no-op on
production, purely additive everywhere else.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "c8f1a2b3d4e5"
down_revision: Union[str, None] = "b7e2c9d4f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = [
    ("routes", sa.Column("preference", sa.String(length=10), nullable=True)),
    ("routes", sa.Column("share_token", sa.String(length=36), nullable=True)),
    ("routes", sa.Column("route_path", sa.Text(), nullable=True)),
    ("spots", sa.Column("description", sa.Text(), nullable=True)),
]


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    for table, column in COLUMNS:
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column.name not in existing:
            op.add_column(table, column)

    # Matched by column, not name, in case production's index is named
    # differently — a second unique index would be redundant.
    indexed = {tuple(ix["column_names"]) for ix in inspect(op.get_bind()).get_indexes("routes")}
    if ("share_token",) not in indexed:
        op.create_index("ix_routes_share_token", "routes", ["share_token"], unique=True)


def downgrade() -> None:
    # Intentionally a no-op: on production these columns predate this
    # migration and hold real data, so dropping them here would be
    # destructive (see CLAUDE.md's production database rule).
    pass
