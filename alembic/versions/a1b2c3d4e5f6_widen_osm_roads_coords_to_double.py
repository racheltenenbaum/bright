"""widen osm_roads coordinate columns from FLOAT to DOUBLE

Revision ID: a1b2c3d4e5f6
Revises: b5c6d7e8f9a0
Create Date: 2026-09-08 00:00:00.000000

Single-precision FLOAT only holds ~7 significant digits, which quantizes a
latitude like 34.0922544 down to about 34.0923 — an ~11m grid. Since
build_graph_from_edges (src/routing.py) uses these exact coordinates as
routing-graph node identity, that quantization let genuinely distinct points
collapse onto the same node, producing snakey/staircase street shapes and
physically-impossible "shortcuts" (a computed path shorter than the
straight-line distance between its own endpoints).

This migration only widens the column type — it does not fix already-stored
rows, which already lost precision at write time. Road data for every region
must be re-imported afterward via scripts/import_osm_roads.py.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN min_lat DOUBLE NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN max_lat DOUBLE NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN min_lng DOUBLE NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN max_lng DOUBLE NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN from_lat DOUBLE NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN from_lng DOUBLE NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN to_lat DOUBLE NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN to_lng DOUBLE NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN min_lat FLOAT NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN max_lat FLOAT NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN min_lng FLOAT NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN max_lng FLOAT NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN from_lat FLOAT NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN from_lng FLOAT NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN to_lat FLOAT NOT NULL")
    op.execute("ALTER TABLE osm_roads MODIFY COLUMN to_lng FLOAT NOT NULL")
