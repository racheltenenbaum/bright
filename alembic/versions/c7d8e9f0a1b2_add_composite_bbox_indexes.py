"""add composite (region, lat/lng) indexes to osm_buildings and osm_roads

Revision ID: c7d8e9f0a1b2
Revises: f8a1b2c3d4e5
Create Date: 2026-09-08 00:00:00.000000

The bbox lookup on both tables filters min_lat/max_lat/min_lng/max_lng as an
AND of ranges, on top of a region equality filter. A bare single-column
index per column can't be combined for that — EXPLAIN confirmed MySQL was
using only the region index and then scanning/filtering every remaining row
in that region (up to ~3.9M rows for LA), which is what actually made a
route computation take 15+ seconds, not the earlier FLOAT->DOUBLE precision
fix. A composite index per axis lets the optimizer use index-merge
intersection to narrow both axes before touching table rows.

Purely additive (CREATE INDEX only) — no data is modified or at risk.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "f8a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_osm_buildings_region_lat ON osm_buildings (region, min_lat, max_lat)")
    op.execute("CREATE INDEX ix_osm_buildings_region_lng ON osm_buildings (region, min_lng, max_lng)")
    op.execute("CREATE INDEX ix_osm_roads_region_lat ON osm_roads (region, min_lat, max_lat)")
    op.execute("CREATE INDEX ix_osm_roads_region_lng ON osm_roads (region, min_lng, max_lng)")


def downgrade() -> None:
    op.execute("DROP INDEX ix_osm_buildings_region_lat ON osm_buildings")
    op.execute("DROP INDEX ix_osm_buildings_region_lng ON osm_buildings")
    op.execute("DROP INDEX ix_osm_roads_region_lat ON osm_roads")
    op.execute("DROP INDEX ix_osm_roads_region_lng ON osm_roads")
