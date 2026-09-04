import json
import sqlite3
from unittest.mock import patch, MagicMock, call

import src.routers.shadow_analyze as sa_module
from src.models import OsmBuilding
from src.routers.shadow_analyze import (
    _bbox_key,
    _region_for_bbox,
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
    OVERPASS_URLS,
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


def test_fetch_buildings_api_non_200_status():
    key = _bbox_key(18.0, 28.0, 18.5, 28.5)
    _clear_cache(key)
    bad_resp = MagicMock()
    bad_resp.status_code = 429
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=bad_resp):
            result = _fetch_buildings_for_bbox(18.0, 28.0, 18.5, 28.5)
    assert result is None
    _clear_cache(key)


def test_fetch_buildings_api_exception():
    key = _bbox_key(13.0, 23.0, 13.5, 23.5)
    _clear_cache(key)
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", side_effect=Exception("network error")):
            result = _fetch_buildings_for_bbox(13.0, 23.0, 13.5, 23.5)
    assert result is None  # All API calls failed — return None, not []
    _clear_cache(key)


def test_fetch_buildings_logs_failure_reason(caplog):
    """A silent None on total failure is undiagnosable in production — the
    actual reason (timeout, rate limit, DNS, etc.) must be logged."""
    key = _bbox_key(19.0, 29.0, 19.5, 29.5)
    _clear_cache(key)
    with caplog.at_level("WARNING"):
        with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
            with patch("requests.post", side_effect=Exception("rate limited")):
                _fetch_buildings_for_bbox(19.0, 29.0, 19.5, 29.5)
    assert "rate limited" in caplog.text
    _clear_cache(key)


# ── _region_for_bbox ────────────────────────────────────────────────────────

def test_region_for_bbox_vienna():
    # A small bbox well inside Vienna's administrative extent.
    assert _region_for_bbox(48.20, 16.35, 48.21, 16.36) == "vienna"


def test_region_for_bbox_nyc():
    # A small bbox well inside NYC's five boroughs.
    assert _region_for_bbox(40.70, -74.00, 40.71, -73.99) == "nyc"


def test_region_for_bbox_telaviv():
    # A small bbox well inside Tel Aviv's municipal extent.
    assert _region_for_bbox(32.06, 34.77, 32.07, 34.78) == "telaviv"


def test_region_for_bbox_unimported_area():
    # London — not one of our pre-loaded regions.
    assert _region_for_bbox(51.50, -0.10, 51.51, -0.09) is None


def test_region_for_bbox_straddling_boundary_is_unimported():
    # A bbox that only partially overlaps Vienna's bounds must not be treated
    # as fully covered — we'd silently return incomplete local data otherwise.
    assert _region_for_bbox(48.05, 16.35, 48.21, 16.36) is None


# ── _fetch_buildings_for_bbox (local DB, imported regions) ────────────────────

def test_fetch_buildings_uses_local_db_for_imported_region(db):
    building = OsmBuilding(
        region="vienna", source="vienna_wfs",
        min_lat=48.200, max_lat=48.201, min_lng=16.350, max_lng=16.351,
        footprint=json.dumps([[48.200, 16.350], [48.200, 16.351], [48.201, 16.351]]),
        height=15.0,
    )
    db.add(building)
    db.commit()

    with patch("requests.post") as mock_post:
        result = _fetch_buildings_for_bbox(48.199, 16.349, 48.202, 16.352)

    mock_post.assert_not_called()
    assert result == [{"footprint": [[48.200, 16.350], [48.200, 16.351], [48.201, 16.351]], "height": 15.0}]


def test_fetch_buildings_local_db_excludes_out_of_bbox_rows(db):
    building = OsmBuilding(
        region="vienna", source="vienna_wfs",
        min_lat=48.250, max_lat=48.251, min_lng=16.400, max_lng=16.401,
        footprint=json.dumps([[48.250, 16.400], [48.250, 16.401], [48.251, 16.401]]),
        height=10.0,
    )
    db.add(building)
    db.commit()

    # Query bbox far from the seeded building, but still inside Vienna overall.
    # No local rows match, so this now falls back to live Overpass (see
    # test_fetch_buildings_imported_region_empty_db_falls_back_to_overpass).
    key = _bbox_key(48.100, 16.200, 48.101, 16.201)
    _clear_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": []}
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp):
            result = _fetch_buildings_for_bbox(48.100, 16.200, 48.101, 16.201)
    assert result == []
    _clear_cache(key)


def test_fetch_buildings_imported_region_empty_db_falls_back_to_overpass(db):
    """A bbox with no local rows is ambiguous: it might genuinely have no
    buildings, or the region might be registered but not actually imported
    yet (e.g. NYC's bounds exist before its import ran). Trusting an empty
    local result unconditionally risks silently returning no shading data
    for an unimported region, so this must fall back to live Overpass."""
    key = _bbox_key(48.300, 16.500, 48.301, 16.501)
    _clear_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": []}
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = _fetch_buildings_for_bbox(48.300, 16.500, 48.301, 16.501)
    assert mock_post.called
    assert result == []
    _clear_cache(key)


def test_remember_bbox_evicts_oldest_beyond_cap():
    sa_module._overpass_bbox_cache.clear()
    for i in range(sa_module._BBOX_CACHE_MAX_ENTRIES + 1):
        sa_module._remember_bbox(float(i), 0.0, float(i) + 1, 1.0, [])
    assert len(sa_module._overpass_bbox_cache) == sa_module._BBOX_CACHE_MAX_ENTRIES
    # The very first entry (s=0.0) must have been evicted.
    assert all(entry[0] != 0.0 for entry in sa_module._overpass_bbox_cache)
    sa_module._overpass_bbox_cache.clear()


def test_fetch_buildings_reuses_containing_cached_bbox():
    """A route's own bbox (e.g. shadow-analyze's route-shaped box) is often
    fully inside a bbox already fetched moments earlier for the same trip
    (e.g. optimized-route's start/end box). Re-fetching from Overpass for
    the smaller box wastes a live call the app already paid for — serving
    the superset's buildings instead is correct (they cover the same or
    more ground) and avoids a second unreliable network round trip."""
    outer_key = _bbox_key(10.00, 20.00, 10.10, 20.10)
    _clear_cache(outer_key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "elements": [
            {"type": "node", "id": 1, "lat": 10.05, "lon": 20.05},
            {"type": "node", "id": 2, "lat": 10.05, "lon": 20.06},
            {"type": "node", "id": 3, "lat": 10.06, "lon": 20.06},
            {"type": "way", "id": 100, "nodes": [1, 2, 3], "tags": {"building": "yes"}},
        ]
    }
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            outer_result = _fetch_buildings_for_bbox(10.00, 20.00, 10.10, 20.10)
            assert mock_post.called

            # A smaller, inner bbox fully contained within the one just fetched.
            with patch("requests.post") as inner_mock_post:
                inner_result = _fetch_buildings_for_bbox(10.02, 20.02, 10.04, 20.04)

    inner_mock_post.assert_not_called()
    assert inner_result == outer_result
    _clear_cache(outer_key)


def test_fetch_buildings_does_not_reuse_non_containing_bbox():
    """A bbox that merely overlaps (not fully contains) a cached one must
    still hit Overpass — serving a partial box's data as if it were
    complete would silently drop real buildings from the result."""
    key1 = _bbox_key(20.00, 30.00, 20.05, 30.05)
    key2 = _bbox_key(20.10, 30.10, 20.15, 30.15)
    _clear_cache(key1, key2)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": []}
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp):
            _fetch_buildings_for_bbox(20.00, 30.00, 20.05, 30.05)
        with patch("requests.post", return_value=mock_resp) as mock_post:
            _fetch_buildings_for_bbox(20.10, 30.10, 20.15, 30.15)
    assert mock_post.called
    _clear_cache(key1, key2)


def test_fetch_buildings_unimported_region_still_uses_overpass():
    """Regions we haven't imported must keep using the existing live-Overpass
    path unchanged — this is the safety net for anywhere outside coverage."""
    key = _bbox_key(51.50, -0.10, 51.51, -0.09)
    _clear_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": []}
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = _fetch_buildings_for_bbox(51.50, -0.10, 51.51, -0.09)
    assert result == []
    assert mock_post.called
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


def test_fetch_buildings_falls_back_to_working_mirror():
    """One mirror failing must not block a working mirror from succeeding —
    mirrors are tried concurrently, not one-at-a-time, so a single slow/dead
    mirror shouldn't multiply the total wait before giving up."""
    key = _bbox_key(15.0, 25.0, 15.5, 25.5)
    _clear_cache(key)
    good_resp = MagicMock()
    good_resp.status_code = 200
    good_resp.json.return_value = {"elements": []}

    def fake_post(url, **kwargs):
        if url == OVERPASS_URLS[0]:
            raise Exception("mirror down")
        return good_resp

    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", side_effect=fake_post):
            result = _fetch_buildings_for_bbox(15.0, 25.0, 15.5, 25.5)
    assert result == []
    _clear_cache(key)


def test_fetch_buildings_tries_mirrors_concurrently_not_sequentially():
    """A slow mirror must not add its delay on top of the others' — mirrors
    are raced in parallel, so total wait should track the slowest single
    mirror, not the sum of all of them."""
    import time

    key = _bbox_key(17.0, 27.0, 17.5, 27.5)
    _clear_cache(key)
    good_resp = MagicMock()
    good_resp.status_code = 200
    good_resp.json.return_value = {"elements": []}

    def fake_post(url, **kwargs):
        time.sleep(0.15)
        if url == OVERPASS_URLS[0]:
            raise Exception("down")
        return good_resp

    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", side_effect=fake_post):
            start = time.monotonic()
            _fetch_buildings_for_bbox(17.0, 27.0, 17.5, 27.5)
            elapsed = time.monotonic() - start
    # Sequential retries mirror 2 only after mirror 1's 0.15s failure (>=0.3s
    # total); racing them concurrently should finish in ~0.15s.
    assert elapsed < 0.25
    _clear_cache(key)


def test_fetch_buildings_tries_all_mirrors_when_all_fail():
    key = _bbox_key(16.0, 26.0, 16.5, 26.5)
    _clear_cache(key)
    with patch("src.routers.shadow_analyze._sqlite_get", return_value=None):
        with patch("requests.post", side_effect=Exception("down")) as mock_post:
            result = _fetch_buildings_for_bbox(16.0, 26.0, 16.5, 26.5)
    assert result is None
    assert mock_post.call_count == len(OVERPASS_URLS)
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
