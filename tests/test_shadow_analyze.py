import sqlite3
from unittest.mock import patch, MagicMock, call

import src.routers.shadow_analyze as sa_module
from src.routers.shadow_analyze import (
    _bbox_key,
    _route_bbox,
    _sample_coords,
    _nearest_shaded,
    _nearest_sunny_side,
    _sqlite_get,
    _sqlite_set,
    _fetch_buildings_for_bbox,
    _fetch_elevations,
    _is_terrain_flat,
    _terrain_ray_points,
    _check_terrain_shadows,
    RAY_DISTANCES_M,
    FLAT_TERRAIN_THRESHOLD_M,
    MAX_SUN_ALT_FOR_TERRAIN_DEG,
)

ROUTE = [[51.5, -0.1], [51.502, -0.1], [51.504, -0.1]]
DATETIME = "2025-06-01T12:00:00"
SUN_POS = (45.0, 180.0)
BUILDINGS = []


# ── helper: clear module-level memory cache ────────────────────────────────────

def _clear_cache(*keys):
    for k in keys:
        sa_module._overpass_cache.pop(k, None)


# ── _bbox_key ──────────────────────────────────────────────────────────────────

def test_bbox_key_rounds():
    assert _bbox_key(51.0, -0.1, 51.5, 0.1) == "51.0,-0.1,51.5,0.1"


# ── _route_bbox ────────────────────────────────────────────────────────────────

def test_route_bbox_covers_all_coords():
    s, w, n, e = _route_bbox([[51.5, -0.1], [51.6, 0.0]], padding_m=0)
    assert s <= 51.5
    assert n >= 51.6
    assert w <= -0.1
    assert e >= 0.0


def test_route_bbox_adds_padding():
    s1, w1, n1, e1 = _route_bbox([[51.5, 0.0]], padding_m=0)
    s2, w2, n2, e2 = _route_bbox([[51.5, 0.0]], padding_m=1000)
    assert s2 < s1 and n2 > n1


# ── _sample_coords ─────────────────────────────────────────────────────────────

def test_sample_coords_under_target():
    coords = [[51.5, 0.0], [51.51, 0.0]]
    samples = _sample_coords(coords, target=25)
    assert len(samples) == 2
    assert samples[0] == (0, 51.5, 0.0)


def test_sample_coords_over_target():
    coords = [[51.5 + i * 0.001, 0.0] for i in range(100)]
    samples = _sample_coords(coords, target=25)
    assert len(samples) == 25


# ── _nearest_shaded ────────────────────────────────────────────────────────────

def test_nearest_shaded_empty():
    assert _nearest_shaded({}, 5) is False


def test_nearest_shaded_picks_closest():
    assert _nearest_shaded({0: True, 10: False}, 2) is True
    assert _nearest_shaded({0: True, 10: False}, 8) is False


# ── _nearest_sunny_side ────────────────────────────────────────────────────────

def test_nearest_sunny_side_empty():
    assert _nearest_sunny_side({}, 5) is None


def test_nearest_sunny_side_picks_closest():
    assert _nearest_sunny_side({0: "left", 10: "right"}, 2) == "left"
    assert _nearest_sunny_side({0: "left", 10: "right"}, 9) == "right"


# ── _sqlite_get / _sqlite_set ──────────────────────────────────────────────────

def test_sqlite_get_miss():
    assert _sqlite_get("key_that_does_not_exist_xyz") is None


def test_sqlite_set_then_get():
    key = "test_set_get_key"
    buildings = [{"footprint": [[51.0, 0.0]], "height": 10.0}]
    _sqlite_set(key, buildings)
    assert _sqlite_get(key) == buildings


def test_sqlite_get_exception():
    with patch("sqlite3.connect", side_effect=Exception("fail")):
        assert _sqlite_get("any") is None


def test_sqlite_set_exception():
    with patch("sqlite3.connect", side_effect=Exception("fail")):
        _sqlite_set("any", [])  # must not raise


# ── _fetch_buildings_for_bbox ──────────────────────────────────────────────────

def test_fetch_buildings_memory_cache_hit():
    key = _bbox_key(10.0, 20.0, 10.5, 20.5)
    sa_module._overpass_cache[key] = [{"cached": True}]
    try:
        assert _fetch_buildings_for_bbox(10.0, 20.0, 10.5, 20.5) == [{"cached": True}]
    finally:
        _clear_cache(key)


def test_fetch_buildings_sqlite_cache_hit():
    key = _bbox_key(11.0, 21.0, 11.5, 21.5)
    _clear_cache(key)
    buildings = [{"footprint": [], "height": 5.0}]
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=buildings):
        result = _fetch_buildings_for_bbox(11.0, 21.0, 11.5, 21.5)
    assert result == buildings
    _clear_cache(key)


def test_fetch_buildings_api_call():
    key = _bbox_key(12.0, 22.0, 12.5, 22.5)
    _clear_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": []}
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp):
            result = _fetch_buildings_for_bbox(12.0, 22.0, 12.5, 22.5)
    assert result == []
    _clear_cache(key)


def test_fetch_buildings_api_exception():
    key = _bbox_key(13.0, 23.0, 13.5, 23.5)
    _clear_cache(key)
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", side_effect=Exception("network error")):
            result = _fetch_buildings_for_bbox(13.0, 23.0, 13.5, 23.5)
    assert result is None  # All API calls failed — return None, not []
    _clear_cache(key)


def test_fetch_buildings_api_success_no_buildings():
    """API succeeds but finds no buildings — returns [], not None."""
    key = _bbox_key(14.0, 24.0, 14.5, 24.5)
    _clear_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": []}
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp):
            result = _fetch_buildings_for_bbox(14.0, 24.0, 14.5, 24.5)
    assert result == []  # Successful fetch, just no buildings
    _clear_cache(key)


def test_shadow_analyze_no_buildings_shadow_still_available(client, auth_headers):
    """When API succeeds but finds no buildings, shadow_available should be True."""
    with patch("src.routers.shadow_analyze.get_sun_position", return_value=SUN_POS):
        with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=[]):
            with patch("src.routers.shadow_analyze._fetch_elevations", return_value=[0.0] * len(ROUTE)):
                response = client.post("/sun/shadow-analyze", json={
                    "coordinates": ROUTE, "datetime": DATETIME
                }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["shadow_available"] is True


def test_shadow_analyze_api_failure_shadow_not_available(client, auth_headers):
    """When Overpass API fails (returns None), shadow_available should be False."""
    with patch("src.routers.shadow_analyze.get_sun_position", return_value=SUN_POS):
        with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=None):
            with patch("src.routers.shadow_analyze._fetch_elevations", return_value=[0.0] * len(ROUTE)):
                response = client.post("/sun/shadow-analyze", json={
                    "coordinates": ROUTE, "datetime": DATETIME
                }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["shadow_available"] is False


# ── _fetch_elevations ──────────────────────────────────────────────────────────

def test_fetch_elevations_empty_coords():
    assert _fetch_elevations([]) == []


def test_fetch_elevations_no_api_key():
    with patch("src.routers.shadow_analyze.GOOGLE_MAPS_API_KEY", None):
        assert _fetch_elevations([(51.5, -0.1)]) == [0.0]


def test_fetch_elevations_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [{"elevation": 20.0}]}
    with patch("requests.get", return_value=mock_resp):
        assert _fetch_elevations([(51.5, -0.1)]) == [20.0]


def test_fetch_elevations_result_length_mismatch():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [{"elevation": 1.0}, {"elevation": 2.0}]}
    with patch("requests.get", return_value=mock_resp):
        assert _fetch_elevations([(51.5, -0.1)]) == [0.0]


def test_fetch_elevations_non_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    with patch("requests.get", return_value=mock_resp):
        assert _fetch_elevations([(51.5, -0.1)]) == [0.0]


def test_fetch_elevations_exception():
    with patch("requests.get", side_effect=Exception("network")):
        assert _fetch_elevations([(51.5, -0.1)]) == [0.0]


# ── _is_terrain_flat ──────────────────────────────────────────────────────────

def test_is_terrain_flat_single_point():
    assert _is_terrain_flat([100.0]) is True


def test_is_terrain_flat_empty():
    assert _is_terrain_flat([]) is True


def test_is_terrain_flat_true():
    assert _is_terrain_flat([50.0, 55.0, 52.0, 48.0]) is True  # range = 7 < 20


def test_is_terrain_flat_false():
    assert _is_terrain_flat([10.0, 35.0, 20.0]) is False  # range = 25 >= 20


def test_is_terrain_flat_custom_threshold():
    assert _is_terrain_flat([0.0, 15.0], threshold_m=10.0) is False
    assert _is_terrain_flat([0.0, 15.0], threshold_m=20.0) is True


# ── _terrain_ray_points ────────────────────────────────────────────────────────

def test_terrain_ray_points_count():
    pts = _terrain_ray_points(51.5, -0.1, 180.0, [100, 500, 1000])
    assert len(pts) == 3


def test_terrain_ray_points_are_tuples():
    pts = _terrain_ray_points(51.5, -0.1, 180.0, RAY_DISTANCES_M)
    for lat, lng in pts:
        assert isinstance(lat, float)
        assert isinstance(lng, float)


def test_terrain_ray_points_moves_away_from_sun():
    # Sun azimuth 180° (due south) → ray goes north (back_bearing = 0°)
    pts = _terrain_ray_points(51.5, -0.1, 180.0, [1000])
    lat, lng = pts[0]
    assert lat > 51.5  # moved north
    assert abs(lng - (-0.1)) < 0.001  # longitude barely changed


# ── _check_terrain_shadows ─────────────────────────────────────────────────────

def test_check_terrain_shadows_flat_skips_api():
    samples = [(0, 51.5, -0.1), (1, 51.51, -0.1)]
    elevations = [10.0, 12.0]  # range = 2 < 20 → flat
    with patch("src.routers.shadow_analyze._fetch_elevations") as mock_fetch:
        result = _check_terrain_shadows(samples, elevations, 10.0, 180.0)
    mock_fetch.assert_not_called()
    assert result == {0: False, 1: False}


def test_check_terrain_shadows_blocking_terrain():
    # Point at elevation 0, sun altitude 10° → at 900m, need terrain > 159m to block
    # We mock ray elevations: [0, 0, 200, 0, 0] → blocked at 900m
    import math
    samples = [(0, 51.5, -0.1)]
    elevations = [0.0]
    # Make terrain hilly so flatness check passes
    hilly_elevations = [0.0, 50.0]
    samples_hilly = [(0, 51.5, -0.1), (1, 51.52, -0.1)]

    n = len(RAY_DISTANCES_M)
    # Only first point's rays matter; second returns all zeros
    ray_returns = [0.0] * n + [0.0] * n
    # Set index 2 (900m for first point) high enough to block
    blocking_elev = 0.0 + RAY_DISTANCES_M[2] * math.tan(math.radians(10.0)) + 10.0
    ray_returns[2] = blocking_elev

    with patch("src.routers.shadow_analyze._fetch_elevations", return_value=ray_returns):
        result = _check_terrain_shadows(samples_hilly, hilly_elevations, 10.0, 180.0)
    assert result[0] is True
    assert result[1] is False


def test_check_terrain_shadows_non_blocking():
    import math
    samples = [(0, 51.5, -0.1), (1, 51.52, -0.1)]
    elevations = [0.0, 50.0]  # hilly enough
    n = len(RAY_DISTANCES_M)
    # All ray elevations below blocking threshold
    ray_returns = [5.0] * (2 * n)
    with patch("src.routers.shadow_analyze._fetch_elevations", return_value=ray_returns):
        result = _check_terrain_shadows(samples, elevations, 10.0, 180.0)
    assert result == {0: False, 1: False}


# ── _analyze_route terrain integration ────────────────────────────────────────

def test_analyze_route_high_sun_skips_terrain():
    """With sun altitude > MAX_SUN_ALT_FOR_TERRAIN_DEG, _check_terrain_shadows is not called."""
    from src.routers.shadow_analyze import _analyze_route
    with patch("src.routers.shadow_analyze._fetch_elevations", return_value=[0.0, 0.0, 0.0]):
        with patch("src.routers.shadow_analyze._check_terrain_shadows") as mock_terrain:
            _analyze_route(ROUTE, BUILDINGS, MAX_SUN_ALT_FOR_TERRAIN_DEG + 1, 180.0)
    mock_terrain.assert_not_called()


def test_analyze_route_low_sun_hilly_calls_terrain():
    """With sun altitude <= MAX_SUN_ALT_FOR_TERRAIN_DEG and hilly terrain, terrain check runs."""
    from src.routers.shadow_analyze import _analyze_route
    # 3 route points → 3 elevation samples; make range > threshold so it's hilly
    route_elevs = [0.0, 60.0, 30.0]
    n = len(RAY_DISTANCES_M)
    ray_elevs = [0.0] * (3 * n)
    # First call returns route elevations, second returns ray elevations
    with patch("src.routers.shadow_analyze._fetch_elevations", side_effect=[route_elevs, ray_elevs]):
        result = _analyze_route(ROUTE, BUILDINGS, 15.0, 180.0)
    assert len(result.segments) == len(ROUTE)


def test_analyze_route_terrain_shadow_marks_shaded():
    """Blocking terrain on a low-sun route marks the segment as shaded."""
    import math
    from src.routers.shadow_analyze import _analyze_route
    route_elevs = [0.0, 50.0, 25.0]
    n = len(RAY_DISTANCES_M)
    sun_altitude = 15.0
    # Make first point's ray blocked at distance index 2
    ray_returns = [0.0] * (3 * n)
    ray_returns[2] = 0.0 + RAY_DISTANCES_M[2] * math.tan(math.radians(sun_altitude)) + 50.0
    with patch("src.routers.shadow_analyze._fetch_elevations", side_effect=[route_elevs, ray_returns]):
        result = _analyze_route(ROUTE, BUILDINGS, sun_altitude, 180.0)
    # First segment should be terrain-shaded
    assert result.segments[0].shaded is True


# ── /sun/shadow-analyze endpoint ───────────────────────────────────────────────

def test_shadow_analyze_too_few_coords(client, auth_headers):
    response = client.post("/sun/shadow-analyze", json={
        "coordinates": [[51.5, -0.1]], "datetime": DATETIME
    }, headers=auth_headers)
    assert response.status_code == 400


def test_shadow_analyze_sun_below_horizon(client, auth_headers):
    with patch("src.routers.shadow_analyze.get_sun_position", return_value=(-5.0, 180.0)):
        with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=BUILDINGS):
            response = client.post("/sun/shadow-analyze", json={
                "coordinates": ROUTE, "datetime": DATETIME
            }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert all(s["shaded"] for s in data["segments"])
    assert data["sun_altitude"] == -5.0


def test_shadow_analyze_success(client, auth_headers):
    with patch("src.routers.shadow_analyze.get_sun_position", return_value=SUN_POS):
        with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=BUILDINGS):
            with patch("src.routers.shadow_analyze._fetch_elevations", return_value=[0.0] * len(ROUTE)):
                response = client.post("/sun/shadow-analyze", json={
                    "coordinates": ROUTE, "datetime": DATETIME
                }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sun_altitude"] == 45.0
    assert len(data["segments"]) == len(ROUTE)


def test_shadow_analyze_unauthenticated(client):
    response = client.post("/sun/shadow-analyze", json={
        "coordinates": ROUTE, "datetime": DATETIME
    })
    assert response.status_code == 401


# ── /sun/shadow-analyze-batch endpoint ────────────────────────────────────────

def test_shadow_analyze_batch_no_routes(client, auth_headers):
    response = client.post("/sun/shadow-analyze-batch", json={
        "routes": [], "datetime": DATETIME
    }, headers=auth_headers)
    assert response.status_code == 400


def test_shadow_analyze_batch_sun_below_horizon(client, auth_headers):
    with patch("src.routers.shadow_analyze.get_sun_position", return_value=(-5.0, 180.0)):
        with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=BUILDINGS):
            response = client.post("/sun/shadow-analyze-batch", json={
                "routes": [ROUTE], "datetime": DATETIME
            }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert all(s["shaded"] for s in data["routes"][0]["segments"])


def test_shadow_analyze_batch_success(client, auth_headers):
    with patch("src.routers.shadow_analyze.get_sun_position", return_value=SUN_POS):
        with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=BUILDINGS):
            with patch("src.routers.shadow_analyze._fetch_elevations", return_value=[0.0] * len(ROUTE)):
                response = client.post("/sun/shadow-analyze-batch", json={
                    "routes": [ROUTE, ROUTE], "datetime": DATETIME
                }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["routes"]) == 2
    assert data["sun_altitude"] == 45.0
    assert "sunny_side" in data["routes"][0]["segments"][0]


def test_shadow_analyze_batch_unauthenticated(client):
    response = client.post("/sun/shadow-analyze-batch", json={
        "routes": [ROUTE], "datetime": DATETIME
    })
    assert response.status_code == 401
