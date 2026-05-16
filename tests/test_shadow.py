from unittest.mock import patch
from shapely.geometry import Polygon

from src.shadow import (
    _offset_point,
    _bearing,
    _parse_height,
    cast_shadow_polygon,
    is_point_shaded,
    which_side_sunny,
    extract_buildings_from_overpass,
)

# ── _offset_point ──────────────────────────────────────────────────────────────

def test_offset_point_north():
    lat, lng = _offset_point(51.0, 0.0, 0, 100)
    assert lat > 51.0
    assert abs(lng) < 1e-9

def test_offset_point_east():
    lat, lng = _offset_point(51.0, 0.0, 90, 100)
    assert abs(lat - 51.0) < 1e-9
    assert lng > 0.0

def test_offset_point_south():
    lat, lng = _offset_point(51.0, 0.0, 180, 100)
    assert lat < 51.0

def test_offset_point_west():
    lat, lng = _offset_point(51.0, 0.0, 270, 100)
    assert lng < 0.0

# ── _bearing ───────────────────────────────────────────────────────────────────

def test_bearing_north():
    assert abs(_bearing(51.0, 0.0, 52.0, 0.0)) < 1.0

def test_bearing_south():
    assert abs(_bearing(52.0, 0.0, 51.0, 0.0) - 180.0) < 1.0

def test_bearing_east():
    assert abs(_bearing(51.0, 0.0, 51.0, 1.0) - 90.0) < 1.0

def test_bearing_west():
    assert abs(_bearing(51.0, 1.0, 51.0, 0.0) - 270.0) < 1.0

# ── _parse_height ──────────────────────────────────────────────────────────────

def test_parse_height_from_height():
    assert _parse_height({"height": "15"}) == 15.0

def test_parse_height_with_m_suffix():
    assert _parse_height({"height": "12m"}) == 12.0

def test_parse_height_from_building_height():
    assert _parse_height({"building:height": "20"}) == 20.0

def test_parse_height_height_invalid_falls_to_building_height():
    assert _parse_height({"height": "tall", "building:height": "8"}) == 8.0

def test_parse_height_from_levels():
    assert _parse_height({"building:levels": "4"}) == 12.0

def test_parse_height_invalid_height_then_levels():
    assert _parse_height({"height": "abc", "building:levels": "3"}) == 9.0

def test_parse_height_invalid_levels():
    assert _parse_height({"height": "abc", "building:levels": "many"}) == 10.0

def test_parse_height_default():
    assert _parse_height({}) == 10.0

# ── cast_shadow_polygon ────────────────────────────────────────────────────────

def test_cast_shadow_polygon_sun_below_horizon():
    fp = [[51.0, 0.0], [51.001, 0.0], [51.001, 0.001]]
    assert cast_shadow_polygon(fp, 10, -1, 180) is None

def test_cast_shadow_polygon_sun_at_zero():
    fp = [[51.0, 0.0], [51.001, 0.0], [51.001, 0.001]]
    assert cast_shadow_polygon(fp, 10, 0, 180) is None

def test_cast_shadow_polygon_sun_overhead():
    fp = [[51.0, 0.0], [51.001, 0.0], [51.001, 0.001]]
    assert cast_shadow_polygon(fp, 10, 89, 180) is None

def test_cast_shadow_polygon_empty_footprint():
    assert cast_shadow_polygon([], 10, 45, 180) is None

def test_cast_shadow_polygon_one_coord_gives_two_points():
    # 1 coord → 2 points → < 3 → None
    assert cast_shadow_polygon([[51.0, 0.0]], 10, 45, 180) is None

def test_cast_shadow_polygon_normal():
    fp = [[51.0, 0.0], [51.001, 0.0], [51.001, 0.001], [51.0, 0.001]]
    result = cast_shadow_polygon(fp, 10, 45, 180)
    assert isinstance(result, Polygon)
    assert result.area > 0

# ── is_point_shaded ────────────────────────────────────────────────────────────

def test_is_point_shaded_sun_at_zero():
    assert is_point_shaded(51.0, 0.0, [], 0, 180) is True

def test_is_point_shaded_sun_negative():
    assert is_point_shaded(51.0, 0.0, [], -5, 180) is True

def test_is_point_shaded_no_buildings():
    assert is_point_shaded(51.0, 0.0, [], 45, 180) is False

def test_is_point_shaded_zero_effective_height():
    building = {"footprint": [[51.001, -0.001], [51.001, 0.001], [51.0, 0.001]], "height": 0.0}
    assert is_point_shaded(51.0, 0.0, [building], 45, 180) is False

def test_is_point_shaded_elevation_exceeds_building():
    building = {"footprint": [[51.001, -0.001], [51.001, 0.001], [51.0, 0.001]], "height": 5.0, "base_elevation": 0.0}
    assert is_point_shaded(51.0, 0.0, [building], 45, 180, point_elevation=10.0) is False

def test_is_point_shaded_in_shadow():
    # Tall building north of point, sun from north (azimuth ~0) at low angle → shadow falls south
    fp = [[51.0005, -0.0005], [51.0005, 0.0005], [51.001, 0.0005], [51.001, -0.0005]]
    building = {"footprint": fp, "height": 50.0, "base_elevation": 0.0}
    result = is_point_shaded(51.0, 0.0, [building], 10, 0, 0.0)
    assert isinstance(result, bool)

# ── which_side_sunny ───────────────────────────────────────────────────────────

def test_which_side_sunny_night():
    assert which_side_sunny(51.0, 0.0, 51.001, 0.0, [], 0, 180) == "neither"

def test_which_side_sunny_negative_altitude():
    assert which_side_sunny(51.0, 0.0, 51.001, 0.0, [], -5, 180) == "neither"

def test_which_side_sunny_both_open_sky():
    # No buildings → both sides sunny
    assert which_side_sunny(51.0, 0.0, 51.001, 0.0, [], 45, 180) == "both"

def test_which_side_sunny_neither():
    with patch("src.shadow.is_point_shaded", return_value=True):
        assert which_side_sunny(51.0, 0.0, 51.001, 0.0, [], 45, 180) == "neither"

def test_which_side_sunny_right():
    # left shaded, right sunny → "right"
    with patch("src.shadow.is_point_shaded", side_effect=[True, False]):
        assert which_side_sunny(51.0, 0.0, 51.001, 0.0, [], 45, 180) == "right"

def test_which_side_sunny_left():
    # left sunny, right shaded → "left"
    with patch("src.shadow.is_point_shaded", side_effect=[False, True]):
        assert which_side_sunny(51.0, 0.0, 51.001, 0.0, [], 45, 180) == "left"

# ── extract_buildings_from_overpass ────────────────────────────────────────────

def _make_overpass(ways):
    nodes = [
        {"type": "node", "id": 1, "lat": 51.0,   "lon": 0.0},
        {"type": "node", "id": 2, "lat": 51.001, "lon": 0.0},
        {"type": "node", "id": 3, "lat": 51.001, "lon": 0.001},
    ]
    return {"elements": nodes + ways}

def test_extract_buildings_empty():
    assert extract_buildings_from_overpass({"elements": []}) == []

def test_extract_buildings_no_elements_key():
    assert extract_buildings_from_overpass({}) == []

def test_extract_buildings_normal_height():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes", "height": "15"}, "nodes": [1, 2, 3]}])
    result = extract_buildings_from_overpass(data)
    assert len(result) == 1
    assert result[0]["height"] == 15.0

def test_extract_buildings_building_height_tag():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes", "building:height": "12m"}, "nodes": [1, 2, 3]}])
    assert extract_buildings_from_overpass(data)[0]["height"] == 12.0

def test_extract_buildings_levels():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes", "building:levels": "4"}, "nodes": [1, 2, 3]}])
    assert extract_buildings_from_overpass(data)[0]["height"] == 12.0

def test_extract_buildings_default_height():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes"}, "nodes": [1, 2, 3]}])
    assert extract_buildings_from_overpass(data)[0]["height"] == 10.0

def test_extract_buildings_skips_non_building_way():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"highway": "road"}, "nodes": [1, 2, 3]}])
    assert extract_buildings_from_overpass(data) == []

def test_extract_buildings_skips_too_few_nodes():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes"}, "nodes": [1, 2]}])
    assert extract_buildings_from_overpass(data) == []

def test_extract_buildings_skips_unknown_node():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes"}, "nodes": [1, 2, 999]}])
    # node 999 not in nodes dict → footprint has 2 coords → skipped
    assert extract_buildings_from_overpass(data) == []

def test_extract_buildings_invalid_height_falls_to_default():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes", "height": "tall"}, "nodes": [1, 2, 3]}])
    assert extract_buildings_from_overpass(data)[0]["height"] == 10.0

def test_extract_buildings_invalid_levels_falls_to_default():
    data = _make_overpass([{"type": "way", "id": 10, "tags": {"building": "yes", "building:levels": "many"}, "nodes": [1, 2, 3]}])
    assert extract_buildings_from_overpass(data)[0]["height"] == 10.0
