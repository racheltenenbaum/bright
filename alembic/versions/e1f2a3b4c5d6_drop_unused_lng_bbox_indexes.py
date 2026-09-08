"""drop the unused region_lng composite indexes

Revision ID: e1f2a3b4c5d6
Revises: c7d8e9f0a1b2
Create Date: 2026-09-08 00:00:00.000000

The previous migration added both a (region, min_lat, max_lat) and a
(region, min_lng, max_lng) composite index per table, expecting MySQL to
use index-merge intersection across both. In practice the optimizer never
picked either up on its own (even after ANALYZE TABLE), and forcing an
index-merge of both was measured slower than a plain full scan. Forcing
just the lat composite alone gives a real index range scan and was
measured ~20x faster (see src/routing.py::_fetch_roads_from_db and
src/routers/shadow_analyze.py::_fetch_buildings_from_db). The lng
composites are therefore dead weight — extra index-maintenance cost on
every write with no read benefit — and are dropped here.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX ix_osm_buildings_region_lng ON osm_buildings")
    op.execute("DROP INDEX ix_osm_roads_region_lng ON osm_roads")


def downgrade() -> None:
    op.execute("CREATE INDEX ix_osm_buildings_region_lng ON osm_buildings (region, min_lng, max_lng)")
    op.execute("CREATE INDEX ix_osm_roads_region_lng ON osm_roads (region, min_lng, max_lng)")
