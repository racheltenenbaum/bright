"""Shading by the time the walker actually reaches each part of the route,
not the moment they set off — the sun keeps moving during a long walk."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.routing import (
    MAX_SUN_SLICES,
    ROUTE_LENGTH_SLACK,
    SUN_SLICE_TARGET_MIN,
    WALKING_SPEED_MPS,
    build_graph,
    compute_edge_weights,
    compute_edge_weights_timed,
    plan_sun_slices,
)
from src.utils.astronomy import resolve_departure

# Walk length (m) that takes exactly one target slice at the default pace.
TARGET_M = SUN_SLICE_TARGET_MIN * 60 * WALKING_SPEED_MPS


def _m(x: float, y: float) -> tuple[float, float]:
    """Local meters → lat/lng around (40, -74). x = east, y = north."""
    return 40.0 + y / 111_320, -74.0 + x / (111_320 * 0.766044)


def _sun_at_offset(offset):
    """Azimuth 90 for anything under 10 minutes in, 270 after."""
    return (45.0, 90.0) if offset < timedelta(minutes=10) else (45.0, 270.0)


# --- departure time ----------------------------------------------------------

def test_resolve_departure_uses_timezone_aware_time():
    dt = resolve_departure("2026-05-24T14:00:00+02:00")
    assert dt == datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


def test_resolve_departure_falls_back_to_now_for_naive_time():
    """Older app builds send local wall-clock time with no offset — treating
    that as UTC would shift the sun by hours, so it means "now" instead."""
    dt = resolve_departure("2020-01-01T09:00:00")
    assert abs((dt - datetime.now(timezone.utc)).total_seconds()) < 5


# --- slice planning ----------------------------------------------------------

def test_short_walk_is_one_slice_at_its_midpoint():
    plan = plan_sun_slices(TARGET_M * 0.5)
    assert plan.count == 1
    assert plan.offset(0) == timedelta(minutes=SUN_SLICE_TARGET_MIN * 0.25)
    assert plan.index(TARGET_M * 10) == 0


def test_longer_walk_splits_evenly():
    plan = plan_sun_slices(TARGET_M * 1.5)
    assert plan.count == 2
    half_m = TARGET_M * 0.75
    assert plan.index(0) == 0
    assert plan.index(half_m * 0.99) == 0
    assert plan.index(half_m * 1.01) == 1
    assert plan.index(half_m * 5) == 1
    assert plan.offset(1) == timedelta(minutes=SUN_SLICE_TARGET_MIN * 0.75 * 1.5)


def test_slice_count_is_capped():
    plan = plan_sun_slices(TARGET_M * 100)
    assert plan.count == MAX_SUN_SLICES


def test_slice_plan_respects_walking_speed():
    assert plan_sun_slices(TARGET_M * 1.5, speed_mps=WALKING_SPEED_MPS * 2).count == 1


def test_zero_length_walk():
    plan = plan_sun_slices(0)
    assert plan.count == 1
    assert plan.index(0) == 0


# --- time-aware edge weights -------------------------------------------------

def _line_osm(length_m: float, step_m: float = 250) -> dict:
    n = int(length_m // step_m) + 1
    nodes = [{"type": "node", "id": i + 1, "lat": _m(0, i * step_m)[0], "lon": _m(0, i * step_m)[1]}
             for i in range(n)]
    way = {"type": "way", "id": 100, "nodes": [i + 1 for i in range(n)], "tags": {"highway": "residential"}}
    return {"elements": nodes + [way]}


def _fake_polygons(buildings, alt, az):
    # Stand-in "polygons" that just record the sun angle they were built for.
    return (alt, az), None


def _last(g):
    return max(g.nodes)


def test_timed_weights_shade_far_edges_by_later_sun():
    # ~2000m line: ~30 min with slack → two slices, split ~1150m in.
    g = build_graph(_line_osm(2000))
    with (
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index",
              side_effect=lambda lat, lng, polys, idx, alt: polys[1] == 270.0),
    ):
        compute_edge_weights_timed(g, [], _sun_at_offset, "sun", 1, _last(g))
    last = _last(g)
    assert g.edges[1, 2]["shaded"] is False
    assert g.edges[last - 1, last]["shaded"] is True
    # Sun preference penalizes the shaded (far) edge only.
    assert g.edges[1, 2]["weight"] == pytest.approx(g.edges[1, 2]["distance_m"])
    assert g.edges[last - 1, last]["weight"] > g.edges[last - 1, last]["distance_m"]


def test_timed_weights_treat_slices_after_sunset_as_shaded():
    g = build_graph(_line_osm(2000))
    with (
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index", return_value=False),
    ):
        compute_edge_weights_timed(
            g, [], lambda off: (5.0, 260.0) if off < timedelta(minutes=10) else (-1.0, 265.0),
            "shade", 1, _last(g),
        )
    last = _last(g)
    assert g.edges[1, 2]["shaded"] is False
    assert g.edges[last - 1, last]["shaded"] is True


def test_timed_weights_all_below_horizon_is_plain_distance():
    g = build_graph(_line_osm(2000))
    compute_edge_weights_timed(g, [], lambda off: (-5.0, 280.0), "sun", 1, _last(g))
    for _, _, d in g.edges(data=True):
        assert d["weight"] == d["distance_m"]


def test_timed_weights_single_slice_matches_untimed():
    g1 = build_graph(_line_osm(1000))
    g2 = build_graph(_line_osm(1000))
    with patch("src.routing.is_point_shaded_by_index", side_effect=lambda lat, *a: lat > 40.004):
        compute_edge_weights(g1, [], 45.0, 180.0, "shade")
        compute_edge_weights_timed(g2, [], lambda off: (45.0, 180.0), "shade", 1, _last(g2))
    for u, v, d in g1.edges(data=True):
        assert g2.edges[u, v]["weight"] == d["weight"]


def test_timed_weights_unreachable_edges_use_first_slice():
    osm = _line_osm(2000)
    a, b = _m(500, 0), _m(500, 100)
    osm["elements"] += [
        {"type": "node", "id": 90, "lat": a[0], "lon": a[1]},
        {"type": "node", "id": 91, "lat": b[0], "lon": b[1]},
        {"type": "way", "id": 200, "nodes": [90, 91], "tags": {"highway": "residential"}},
    ]
    g = build_graph(osm)
    with (
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index",
              side_effect=lambda lat, lng, polys, idx, alt: polys[1] == 270.0),
    ):
        compute_edge_weights_timed(g, [], _sun_at_offset, "sun", 1, 9)
    assert g.edges[90, 91]["shaded"] is False
    assert g.edges[8, 9]["shaded"] is True


def test_timed_weights_unreachable_end_uses_one_slice():
    osm = _line_osm(2000)
    a = _m(500, 0)
    osm["elements"] += [{"type": "node", "id": 90, "lat": a[0], "lon": a[1]},
                        {"type": "node", "id": 91, "lat": a[0] + 0.001, "lon": a[1]},
                        {"type": "way", "id": 200, "nodes": [90, 91], "tags": {"highway": "residential"}}]
    g = build_graph(osm)
    with (
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index",
              side_effect=lambda lat, lng, polys, idx, alt: polys[1] == 270.0),
    ):
        compute_edge_weights_timed(g, [], _sun_at_offset, "sun", 1, 91)
    # One slice, departure-ish sun (azimuth 90) everywhere.
    assert not any(d["shaded"] for _, _, d in g.edges(data=True))


# --- end to end: the route picks its far branch by the shade at arrival -----

def _branch_osm() -> dict:
    """A long stem north (unshaded at any time), then two equal branches —
    west and east — well past the first slice. Morning-ish sun shades the
    west branch; the later sun the walker actually meets there shades the
    east one."""
    stem_end = 1500
    pts = {
        1: _m(0, 0),
        2: _m(0, stem_end / 2),
        3: _m(0, stem_end),
        4: _m(-100, stem_end + 250),   # west branch
        5: _m(100, stem_end + 250),    # east branch
        6: _m(0, stem_end + 500),
    }
    nodes = [{"type": "node", "id": i, "lat": lat, "lon": lng} for i, (lat, lng) in pts.items()]
    tags = {"highway": "residential"}
    ways = [
        {"type": "way", "id": 100, "nodes": [1, 2, 3], "tags": tags},
        {"type": "way", "id": 101, "nodes": [3, 4, 6], "tags": tags},
        {"type": "way", "id": 102, "nodes": [3, 5, 6], "tags": tags},
    ]
    return {"elements": nodes + ways}


_DEPARTURE = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


def _sun_by_time(lat, lng, dt=None):
    assert dt is not None, "routing must pass the departure time through"
    return _sun_at_offset(dt - _DEPARTURE)


def _shaded_by_sun_side(lat, lng, polys, idx, alt):
    _, az = polys
    if az == 90.0:
        return lng < -74.0001   # west branch shaded
    return lng > -73.9999       # east branch shaded


@pytest.mark.parametrize("preference,expect_east", [("shade", True), ("sun", False)])
def test_optimized_route_uses_sun_at_arrival_time(client, auth_headers, preference, expect_east):
    """Without time-awareness, shade would pick the west branch (shaded by
    the departure sun) — but by the time the walker gets there, the sun has
    moved and it's the east branch that's shaded. Runs the real endpoint
    for each preference."""
    start, end = _m(0, 0), _m(0, 2000)
    with (
        patch("src.routers.routing.get_sun_position", side_effect=_sun_by_time),
        patch("src.routing.fetch_osm_road_network", return_value=_branch_osm()),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index", side_effect=_shaded_by_sun_side),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": list(start), "end": list(end),
                  "datetime": "2026-05-24T14:00:00+02:00", "preference": preference},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    lngs = [p[1] for p in resp.json()["waypoints"]]
    went_east = max(lngs) > -73.9995
    went_west = min(lngs) < -74.0005
    assert went_east == expect_east
    assert went_west != expect_east


def test_optimized_route_reports_departure_sun(client, auth_headers):
    start, end = _m(0, 0), _m(0, 2000)
    with (
        patch("src.routers.routing.get_sun_position", side_effect=_sun_by_time) as sun,
        patch("src.routing.fetch_osm_road_network", return_value=_branch_osm()),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index", return_value=False),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": list(start), "end": list(end),
                  "datetime": "2026-05-24T14:00:00+02:00", "preference": "sun"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["sun_azimuth"] == 90.0
    assert sun.call_args_list[0].args[2] == _DEPARTURE


def test_optimized_route_naive_datetime_means_now(client, auth_headers):
    start, end = _m(0, 0), _m(0, 500)
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)) as sun,
        patch("src.routing.fetch_osm_road_network", return_value=_line_osm(500)),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": list(start), "end": list(end),
                  "datetime": "2020-01-01T09:00:00", "preference": "sun"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    departure = sun.call_args_list[0].args[2]
    assert abs((departure - datetime.now(timezone.utc)).total_seconds()) < 10


def test_optimized_route_works_when_sun_down_whole_walk(client, auth_headers):
    start, end = _m(0, 0), _m(0, 500)
    with (
        patch("src.routers.routing.get_sun_position", return_value=(-10.0, 300.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_line_osm(500)),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": list(start), "end": list(end),
                  "datetime": "2026-05-24T23:00:00+02:00", "preference": "sun"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    # The fetch runs in parallel and may start, but its result isn't awaited
    # or used; what matters is the route still comes back.
    assert resp.json()["sun_altitude"] == -10.0


@pytest.mark.parametrize("bad", [0.1, 5.0])
def test_optimized_route_rejects_implausible_walking_speed(client, auth_headers, bad):
    resp = client.post(
        "/sun/optimized-route",
        json={"start": [40.0, -74.0], "end": [40.001, -74.0],
              "datetime": "2026-05-24T14:00:00+02:00", "preference": "sun",
              "walking_speed_mps": bad},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_optimized_route_walking_speed_changes_slices(client, auth_headers):
    """Walking twice as fast reaches the branches inside the first slice, so
    the departure sun applies there and shade takes the west branch."""
    start, end = _m(0, 0), _m(0, 2000)
    with (
        patch("src.routers.routing.get_sun_position", side_effect=_sun_by_time),
        patch("src.routing.fetch_osm_road_network", return_value=_branch_osm()),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index", side_effect=_shaded_by_sun_side),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": list(start), "end": list(end),
                  "datetime": "2026-05-24T14:00:00+02:00", "preference": "shade",
                  "walking_speed_mps": WALKING_SPEED_MPS * 2},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert min(p[1] for p in resp.json()["waypoints"]) < -74.0005


# --- shadow-analyze colours segments by the sun at arrival ------------------

def _line_coords(length_m: float, step_m: float = 100) -> list[list[float]]:
    return [list(_m(0, y)) for y in range(0, int(length_m) + 1, int(step_m))]


def _analyze(client, auth_headers, coords, sun_fn, datetime_str="2026-05-24T14:00:00+02:00", **extra):
    with (
        patch("src.routers.shadow_analyze.get_sun_position", side_effect=sun_fn),
        patch("src.routers.shadow_analyze._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routers.shadow_analyze.precompute_shadow_polygons",
              side_effect=lambda b, alt, az: (alt, az)),
        patch("src.routers.shadow_analyze.build_shadow_polygon_index", return_value=None),
        patch("src.routers.shadow_analyze.is_point_shaded_by_index",
              side_effect=lambda lat, lng, polys, idx, alt: polys[1] == 270.0),
        patch("src.routers.shadow_analyze.which_side_sunny", return_value="left"),
    ):
        return client.post(
            "/sun/shadow-analyze",
            json={"coordinates": coords, "datetime": datetime_str, **extra},
            headers=auth_headers,
        )


def test_shadow_analyze_shades_far_segments_by_later_sun(client, auth_headers):
    coords = _line_coords(TARGET_M * 1.5)
    resp = _analyze(client, auth_headers, coords, _sun_by_time)
    assert resp.status_code == 200
    segs = resp.json()["segments"]
    assert segs[0]["shaded"] is False
    assert segs[-1]["shaded"] is True
    assert resp.json()["sun_azimuth"] == 90.0


def test_shadow_analyze_after_sunset_slice_is_shaded(client, auth_headers):
    coords = _line_coords(TARGET_M * 1.5)

    def sun(lat, lng, dt=None):
        return (5.0, 90.0) if dt - _DEPARTURE < timedelta(minutes=10) else (-1.0, 270.0)

    segs = _analyze(client, auth_headers, coords, sun).json()["segments"]
    assert segs[0]["shaded"] is False
    assert segs[-1]["shaded"] is True
    assert segs[-1]["sunny_side"] is None


def test_shadow_analyze_all_dark_skips_buildings(client, auth_headers):
    coords = _line_coords(TARGET_M * 1.5)
    with patch("src.routers.shadow_analyze._fetch_buildings_for_bbox"):
        resp = _analyze(client, auth_headers, coords, lambda lat, lng, dt=None: (-5.0, 300.0))
    assert resp.status_code == 200
    assert all(s["shaded"] for s in resp.json()["segments"])


def test_shadow_analyze_walking_speed_changes_slices(client, auth_headers):
    coords = _line_coords(TARGET_M * 1.5)
    segs = _analyze(client, auth_headers, coords, _sun_by_time,
                    walking_speed_mps=WALKING_SPEED_MPS * 2).json()["segments"]
    assert not any(s["shaded"] for s in segs)


def test_optimized_route_fetches_buildings_when_sun_rises_mid_walk(client, auth_headers):
    """Setting off just before sunrise: the sun is up for later parts of the
    walk, so shadows are still needed."""
    def sunrise(lat, lng, dt=None):
        return (-1.0, 80.0) if dt - _DEPARTURE < timedelta(minutes=10) else (3.0, 85.0)

    building = {"footprint": [], "height": 10}
    start, end = _m(0, 0), _m(0, 2000)
    with (
        patch("src.routers.routing.get_sun_position", side_effect=sunrise),
        patch("src.routing.fetch_osm_road_network", return_value=_branch_osm()),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[building]),
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons) as shadows,
        patch("src.routing.is_point_shaded_by_index", return_value=False),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": list(start), "end": list(end),
                  "datetime": "2026-05-24T14:00:00+02:00", "preference": "sun"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert shadows.call_args.args[0] == [building]


def test_optimized_route_accepts_very_slow_walking_speed(client, auth_headers):
    """Go mode sends the walker's measured pace; very slow walkers (300m in
    10 minutes is 0.5 m/s) must still be accepted, down to 0.3 m/s."""
    start, end = _m(0, 0), _m(0, 500)
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_line_osm(500)),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": list(start), "end": list(end),
                  "datetime": "2026-05-24T14:00:00+02:00", "preference": "sun",
                  "walking_speed_mps": 0.3},
            headers=auth_headers,
        )
    assert resp.status_code == 200


def test_shadow_analyze_accepts_very_slow_walking_speed(client, auth_headers):
    resp = _analyze(client, auth_headers, _line_coords(500), _sun_by_time, walking_speed_mps=0.3)
    assert resp.status_code == 200


def test_shadow_analyze_rejects_implausible_walking_speed(client, auth_headers):
    resp = _analyze(client, auth_headers, _line_coords(500), _sun_by_time, walking_speed_mps=0.2)
    assert resp.status_code == 422


def test_very_long_walk_gets_four_slices():
    """A slow walker's 3km is ~100 minutes; three slices would each span
    ~33 minutes of sun movement."""
    assert MAX_SUN_SLICES == 4
    assert plan_sun_slices(3000 * ROUTE_LENGTH_SLACK, speed_mps=0.5).count == 4
    # A normal-pace 3km walk is unaffected.
    assert plan_sun_slices(3000 * ROUTE_LENGTH_SLACK).count == 3


# --- the account's usual pace ----------------------------------------------

def _route_with_usual_pace(client, auth_headers, db, test_user, usual, sent=None):
    test_user.usual_walking_speed_mps = usual
    db.commit()
    body = {"start": list(_m(0, 0)), "end": list(_m(0, 2000)),
            "datetime": "2026-05-24T14:00:00+02:00", "preference": "shade"}
    if sent is not None:
        body["walking_speed_mps"] = sent
    with (
        patch("src.routers.routing.get_sun_position", side_effect=_sun_by_time),
        patch("src.routing.fetch_osm_road_network", return_value=_branch_osm()),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing._shadow_polygons_and_index", side_effect=_fake_polygons),
        patch("src.routing.is_point_shaded_by_index", side_effect=_shaded_by_sun_side),
    ):
        resp = client.post("/sun/optimized-route", json=body, headers=auth_headers)
    assert resp.status_code == 200
    return min(p[1] for p in resp.json()["waypoints"]) < -74.0005  # went west


def test_optimized_route_uses_accounts_usual_pace(client, auth_headers, db, test_user):
    """A fast usual walker reaches the branches inside the first slice, so
    the departure sun applies and shade goes west — without the app sending
    a pace at all."""
    assert _route_with_usual_pace(client, auth_headers, db, test_user, WALKING_SPEED_MPS * 2) is True


def test_optimized_route_sent_pace_overrides_usual_pace(client, auth_headers, db, test_user):
    assert _route_with_usual_pace(client, auth_headers, db, test_user, WALKING_SPEED_MPS * 2,
                                  sent=WALKING_SPEED_MPS) is False


def test_optimized_route_without_usual_pace_uses_default(client, auth_headers, db, test_user):
    assert _route_with_usual_pace(client, auth_headers, db, test_user, None) is False


def test_shadow_analyze_uses_accounts_usual_pace(client, auth_headers, db, test_user):
    test_user.usual_walking_speed_mps = WALKING_SPEED_MPS * 2
    db.commit()
    segs = _analyze(client, auth_headers, _line_coords(TARGET_M * 1.5), _sun_by_time).json()["segments"]
    assert not any(s["shaded"] for s in segs)
