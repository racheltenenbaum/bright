"""add osm_roads table

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS osm_roads (
            id INT NOT NULL AUTO_INCREMENT,
            region VARCHAR(20) NOT NULL,
            min_lat FLOAT NOT NULL,
            max_lat FLOAT NOT NULL,
            min_lng FLOAT NOT NULL,
            max_lng FLOAT NOT NULL,
            from_lat FLOAT NOT NULL,
            from_lng FLOAT NOT NULL,
            to_lat FLOAT NOT NULL,
            to_lng FLOAT NOT NULL,
            distance_m FLOAT NOT NULL,
            oneway TINYINT(1) NOT NULL DEFAULT 0,
            PRIMARY KEY (id),
            INDEX ix_osm_roads_region (region),
            INDEX ix_osm_roads_min_lat (min_lat),
            INDEX ix_osm_roads_max_lat (max_lat),
            INDEX ix_osm_roads_min_lng (min_lng),
            INDEX ix_osm_roads_max_lng (max_lng)
        )
    """)


def downgrade() -> None:
    op.drop_table("osm_roads")
