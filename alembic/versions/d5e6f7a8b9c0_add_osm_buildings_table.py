"""add osm_buildings table

Revision ID: d5e6f7a8b9c0
Revises: c1d2e3f4a5b6
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS osm_buildings (
            id INT NOT NULL AUTO_INCREMENT,
            region VARCHAR(20) NOT NULL,
            source VARCHAR(20) NOT NULL,
            min_lat FLOAT NOT NULL,
            max_lat FLOAT NOT NULL,
            min_lng FLOAT NOT NULL,
            max_lng FLOAT NOT NULL,
            footprint TEXT NOT NULL,
            height FLOAT NOT NULL,
            PRIMARY KEY (id),
            INDEX ix_osm_buildings_region (region),
            INDEX ix_osm_buildings_min_lat (min_lat),
            INDEX ix_osm_buildings_max_lat (max_lat),
            INDEX ix_osm_buildings_min_lng (min_lng),
            INDEX ix_osm_buildings_max_lng (max_lng)
        )
    """)


def downgrade() -> None:
    op.drop_table("osm_buildings")
