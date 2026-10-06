"""Not part of the src/ coverage gate (scripts/ is one-off bulk-import
tooling) — but the tree WFS returns UTM33 points with sometimes-missing
crown/height values, and paging or chunk-edge mistakes would silently drop
or double-import trees.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_berlin_trees import LAYERS, feature_to_canopy, fetch_page, iter_canopies
from src.shadow import TREE_CANOPY_HEIGHT_M, TREE_CANOPY_SIDES

# 391000E 5820000N (UTM33) -> ~52.51920N 13.39354E
BBOX = (52.51, 13.38, 52.53, 13.40)


def _feature(x=391000.0, y=5820000.0, crown=6.0, height=14.0):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [x, y]},
        "properties": {"gisid": "g", "kronedurch": crown, "baumhoehe": height},
    }


def test_feature_to_canopy_projects_and_sizes_the_tree():
    row = feature_to_canopy(_feature(), BBOX)
    assert row["height"] == 14.0
    assert len(row["footprint"]) == TREE_CANOPY_SIDES
    centre_lat = (row["min_lat"] + row["max_lat"]) / 2
    centre_lng = (row["min_lng"] + row["max_lng"]) / 2
    assert abs(centre_lat - 52.51920) < 1e-4
    assert abs(centre_lng - 13.39354) < 1e-4


def test_feature_to_canopy_defaults_missing_values():
    row = feature_to_canopy(_feature(crown=None, height=None), BBOX)
    assert row["height"] == TREE_CANOPY_HEIGHT_M


def test_feature_to_canopy_skips_trees_outside_the_chunk():
    assert feature_to_canopy(_feature(), (52.40, 13.30, 52.45, 13.35)) is None


def test_feature_to_canopy_chunk_edges_are_half_open():
    # The WFS BBOX filter is inclusive on every edge, so a tree exactly on a
    # shared chunk edge comes back for both chunks; only one may keep it.
    from scripts.import_berlin_trees import TO_WGS84
    lng, lat = TO_WGS84.transform(391000.0, 5820000.0)
    assert feature_to_canopy(_feature(), (lat, 13.38, 52.53, 13.40)) is not None
    assert feature_to_canopy(_feature(), (52.51, 13.38, lat, 13.40)) is None


def test_feature_to_canopy_skips_missing_geometry():
    feature = _feature()
    feature["geometry"] = None
    assert feature_to_canopy(feature, BBOX) is None


def test_fetch_page_filters_by_bbox_and_pages_stably():
    resp = MagicMock()
    resp.json.return_value = {"features": []}
    with patch("scripts.import_berlin_trees.requests.get", return_value=resp) as get:
        fetch_page("street", BBOX, start=5000, count=5000)
    params = get.call_args.kwargs["params"]
    assert params["typeNames"] == LAYERS["street"]
    assert params["CQL_FILTER"] == "BBOX(geom,13.38,52.51,13.4,52.53,'EPSG:4326')"
    assert params["sortBy"] == "gisid"
    assert params["startIndex"] == 5000
    assert params["count"] == 5000


def test_iter_canopies_pages_until_a_short_page():
    pages = [
        {"features": [_feature(), _feature()]},
        {"features": [_feature()]},
    ]
    with patch("scripts.import_berlin_trees.fetch_page", side_effect=pages) as fetch:
        rows = list(iter_canopies("street", BBOX, page_size=2))
    assert len(rows) == 3
    assert [c.kwargs["start"] for c in fetch.call_args_list] == [0, 2]


def test_iter_canopies_rejects_unknown_layer():
    with pytest.raises(KeyError):
        list(iter_canopies("forest", BBOX))
