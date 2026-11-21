"""Not part of the src/ coverage gate (scripts/ is bulk-import tooling), but
copy_region writes to production, so its resume and safety behaviour is
locked in here."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.copy_region import copy_table
from src.models import Base, OsmBuilding, OsmRoad


def _engine(tmp_path, name):
    engine = create_engine(f"sqlite:///{tmp_path / name}.db")
    Base.metadata.create_all(engine, tables=[OsmBuilding.__table__, OsmRoad.__table__])
    return engine


def _building(region, i):
    return {
        "region": region, "source": "osm", "min_lat": i, "max_lat": i + 0.5,
        "min_lng": 0.0, "max_lng": 1.0, "footprint": f"[[{i}, 0]]", "height": 10.0 + i,
    }


def _seed(engine, rows):
    with engine.begin() as conn:
        conn.execute(OsmBuilding.__table__.insert(), rows)


def _rows(engine, region):
    t = OsmBuilding.__table__
    with engine.connect() as conn:
        return [
            (r.region, r.footprint, r.height)
            for r in conn.execute(select(t).where(t.c.region == region).order_by(t.c.id))
        ]


def test_copies_only_the_requested_region_in_order(tmp_path):
    src, dst = _engine(tmp_path, "src"), _engine(tmp_path, "dst")
    _seed(src, [_building("vienna", i) for i in range(7)] + [_building("nyc", 99)])

    copied = copy_table(src, dst, OsmBuilding.__table__, "vienna", batch_size=3)

    assert copied == 7
    assert _rows(dst, "vienna") == _rows(src, "vienna")
    assert _rows(dst, "nyc") == []


def test_resumes_after_an_interrupted_copy_without_duplicates(tmp_path):
    src, dst = _engine(tmp_path, "src"), _engine(tmp_path, "dst")
    _seed(src, [_building("vienna", i) for i in range(10)])
    # Simulate a run that died after committing the first 4 rows.
    _seed(dst, [_building("vienna", i) for i in range(4)])

    copied = copy_table(src, dst, OsmBuilding.__table__, "vienna", batch_size=3)

    assert copied == 6
    assert _rows(dst, "vienna") == _rows(src, "vienna")


def test_does_nothing_when_already_complete(tmp_path):
    src, dst = _engine(tmp_path, "src"), _engine(tmp_path, "dst")
    rows = [_building("vienna", i) for i in range(5)]
    _seed(src, rows)
    _seed(dst, rows)

    assert copy_table(src, dst, OsmBuilding.__table__, "vienna", batch_size=3) == 0
    assert len(_rows(dst, "vienna")) == 5


def test_refuses_when_destination_has_more_rows_than_source(tmp_path):
    # The destination holds data this copy didn't produce (e.g. a separate
    # import), so "resume from row N" would be wrong — stop instead.
    src, dst = _engine(tmp_path, "src"), _engine(tmp_path, "dst")
    _seed(src, [_building("vienna", i) for i in range(2)])
    _seed(dst, [_building("vienna", i) for i in range(3)])

    with pytest.raises(SystemExit):
        copy_table(src, dst, OsmBuilding.__table__, "vienna", batch_size=3)


def test_refuses_when_destination_prefix_differs_from_source(tmp_path):
    src, dst = _engine(tmp_path, "src"), _engine(tmp_path, "dst")
    _seed(src, [_building("vienna", i) for i in range(5)])
    _seed(dst, [_building("vienna", i + 100) for i in range(2)])

    with pytest.raises(SystemExit):
        copy_table(src, dst, OsmBuilding.__table__, "vienna", batch_size=3)


def test_copies_roads_with_full_precision(tmp_path):
    src, dst = _engine(tmp_path, "src"), _engine(tmp_path, "dst")
    road = {
        "region": "la", "min_lat": 34.0922544, "max_lat": 34.0922999,
        "min_lng": -118.2, "max_lng": -118.1, "from_lat": 34.0922544, "from_lng": -118.2,
        "to_lat": 34.0922999, "to_lng": -118.1, "distance_m": 12.5, "oneway": True, "kind": "sidewalk",
    }
    with src.begin() as conn:
        conn.execute(OsmRoad.__table__.insert(), [road])

    assert copy_table(src, dst, OsmRoad.__table__, "la", batch_size=10) == 1
    with dst.connect() as conn:
        got = conn.execute(select(OsmRoad.__table__)).one()
        assert conn.execute(select(func.count()).select_from(OsmRoad.__table__)).scalar() == 1
    assert (got.from_lat, got.oneway, got.kind) == (34.0922544, True, "sidewalk")
