"""widen osm_roads coordinate columns from FLOAT to DOUBLE

Revision ID: f8a1b2c3d4e5
Revises: b5c6d7e8f9a0
Create Date: 2026-09-08 00:00:00.000000

Single-precision FLOAT only holds ~7 significant digits, which quantizes a
latitude like 34.0922544 down to about 34.0923 — an ~11m grid. Since
build_graph_from_edges (src/routing.py) uses these exact coordinates as
routing-graph node identity, that quantization let genuinely distinct points
collapse onto the same node, producing snakey/staircase street shapes and
physically-impossible "shortcuts" (a computed path shorter than the
straight-line distance between its own endpoints).

Drops and recreates the table rather than ALTER TABLE ... MODIFY COLUMN:
a MODIFY on a table this size (5.7M rows across 4 regions) requires MySQL to
rebuild the whole table into a temporary copy, needing roughly the table's
own size again in free disk — this failed once in production with "table is
full" against a volume with only ~1GB headroom. Every region's road data
must be re-imported afterward via scripts/import_osm_roads.py regardless
(already-stored rows lost precision at write time), so there's nothing to
preserve here — dropping and recreating avoids ever needing that temporary
doubled copy, growing the table only incrementally as rows are re-inserted.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f8a1b2c3d4e5"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE osm_roads")
    op.execute("""
        CREATE TABLE osm_roads (
            id INT NOT NULL AUTO_INCREMENT,
            region VARCHAR(20) NOT NULL,
            min_lat DOUBLE NOT NULL,
            max_lat DOUBLE NOT NULL,
            min_lng DOUBLE NOT NULL,
            max_lng DOUBLE NOT NULL,
            from_lat DOUBLE NOT NULL,
            from_lng DOUBLE NOT NULL,
            to_lat DOUBLE NOT NULL,
            to_lng DOUBLE NOT NULL,
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
    op.execute("DROP TABLE osm_roads")
    op.execute("""
        CREATE TABLE osm_roads (
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
