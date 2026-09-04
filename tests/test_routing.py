import pytest
from unittest.mock import patch, MagicMock
import networkx as nx

import src.routing as routing_module
from src.routing import (
    _haversine_m,
    _path_length_m,
    _road_bbox_key,
    _road_sqlite_get,
    _road_sqlite_set,
    build_graph,
    build_graph_from_edges,
    fetch_road_graph,
    nearest_node,
    compute_edge_shading,
    compute_edge_weights,
    apply_preference_weights,
    find_distance_path,
    find_optimized_path,
    nodes_to_coords,
    sample_waypoints,
    simplify_path,
    fetch_osm_road_network,
    OVERPASS_URLS,
)


def _clear_road_cache(*keys):
    for k in keys:
        routing_module._road_cache.pop(k, None)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _simple_osm(oneway: bool = False) -> dict:
    """Three nodes A(1) – B(2) – C(3) in a straight north-south line."""
    tags = {"highway": "residential"}
    if oneway:
        tags["oneway"] = "yes"
    return {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.000, "lon": -74.000},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.000},
            {"type": "node", "id": 3, "lat": 40.002, "lon": -74.000},
            {"type": "way",  "id": 100, "nodes": [1, 2, 3], "tags": tags},
        ]
    }


# ── _haversine_m ─────────────────────────────────────────────────────────────

def test_haversine_same_point():
    assert _haversine_m(40.0, -74.0, 40.0, -74.0) == 0.0


def test_haversine_known_latitude():
    # 1° latitude ≈ 111,195 m
    dist = _haversine_m(0.0, 0.0, 1.0, 0.0)
    assert abs(dist - 111_195) < 300


# ── build_graph ──────────────────────────────────────────────────────────────

def test_build_graph_nodes_created():
    g = build_graph(_simple_osm())
    assert set(g.nodes) == {1, 2, 3}


def test_build_graph_node_attributes():
    g = build_graph(_simple_osm())
    assert g.nodes[1]["lat"] == pytest.approx(40.000)
    assert g.nodes[1]["lng"] == pytest.approx(-74.000)


def test_build_graph_bidirectional():
    g = build_graph(_simple_osm(oneway=False))
    assert g.has_edge(1, 2) and g.has_edge(2, 1)
    assert g.has_edge(2, 3) and g.has_edge(3, 2)


def test_build_graph_oneway():
    g = build_graph(_simple_osm(oneway=True))
    assert g.has_edge(1, 2) and not g.has_edge(2, 1)
    assert g.has_edge(2, 3) and not g.has_edge(3, 2)


def test_build_graph_non_highway_excluded():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way",  "id": 100, "nodes": [1, 2], "tags": {"waterway": "river"}},
        ]
    }
    g = build_graph(data)
    assert g.number_of_edges() == 0


def test_build_graph_motorway_excluded():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way",  "id": 100, "nodes": [1, 2], "tags": {"highway": "motorway"}},
        ]
    }
    g = build_graph(data)
    assert g.number_of_edges() == 0


def test_build_graph_trunk_excluded():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way",  "id": 100, "nodes": [1, 2], "tags": {"highway": "trunk"}},
        ]
    }
    g = build_graph(data)
    assert g.number_of_edges() == 0


def test_build_graph_service_driveway_excluded():
    """highway=service with service=driveway/parking_aisle/drive-through is
    a car-only path through private lots, not a real pedestrian route — a
    plain residential/service way (no service sub-tag) is still included."""
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "service", "service": "driveway"}},
        ]
    }
    g = build_graph(data)
    assert g.number_of_edges() == 0


def test_build_graph_service_parking_aisle_excluded():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "service", "service": "parking_aisle"}},
        ]
    }
    g = build_graph(data)
    assert g.number_of_edges() == 0


def test_build_graph_service_drivethrough_excluded():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "service", "service": "drive-through"}},
        ]
    }
    g = build_graph(data)
    assert g.number_of_edges() == 0


def test_build_graph_plain_service_included():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "service"}},
        ]
    }
    g = build_graph(data)
    assert g.number_of_edges() == 2  # bidirectional by default


def test_build_graph_edge_has_distance():
    g = build_graph(_simple_osm())
    expected = _haversine_m(40.000, -74.0, 40.001, -74.0)
    assert abs(g.edges[1, 2]["distance_m"] - expected) < 1.0


def test_build_graph_edge_has_midpoint():
    g = build_graph(_simple_osm())
    assert g.edges[1, 2]["mid_lat"] == pytest.approx(40.0005)
    assert g.edges[1, 2]["mid_lng"] == pytest.approx(-74.000)


def test_build_graph_empty_data():
    g = build_graph({"elements": []})
    assert g.number_of_nodes() == 0
    assert g.number_of_edges() == 0


# ── build_graph_from_edges (bulk-imported roads) ────────────────────────────

def _simple_edges(oneway: bool = False) -> list[dict]:
    return [{
        "from_lat": 40.000, "from_lng": -74.000,
        "to_lat": 40.001, "to_lng": -74.000,
        "distance_m": 111.2, "oneway": oneway,
    }]


def test_build_graph_from_edges_creates_nodes_and_edge():
    g = build_graph_from_edges(_simple_edges())
    assert g.number_of_nodes() == 2
    assert g.has_edge((40.000, -74.000), (40.001, -74.000))


def test_build_graph_from_edges_bidirectional_by_default():
    g = build_graph_from_edges(_simple_edges(oneway=False))
    assert g.has_edge((40.000, -74.000), (40.001, -74.000))
    assert g.has_edge((40.001, -74.000), (40.000, -74.000))


def test_build_graph_from_edges_respects_oneway():
    g = build_graph_from_edges(_simple_edges(oneway=True))
    assert g.has_edge((40.000, -74.000), (40.001, -74.000))
    assert not g.has_edge((40.001, -74.000), (40.000, -74.000))


def test_build_graph_from_edges_sets_distance_and_midpoint():
    g = build_graph_from_edges(_simple_edges())
    edge = g.edges[(40.000, -74.000), (40.001, -74.000)]
    assert edge["distance_m"] == 111.2
    assert edge["weight"] == 111.2
    assert edge["mid_lat"] == pytest.approx(40.0005)
    assert edge["mid_lng"] == pytest.approx(-74.000)


def test_build_graph_from_edges_shares_nodes_across_edges():
    # A(1)-B(2)-C(3): B must be a single shared node, not duplicated.
    edges = [
        {"from_lat": 40.000, "from_lng": -74.000, "to_lat": 40.001, "to_lng": -74.000,
         "distance_m": 111.2, "oneway": False},
        {"from_lat": 40.001, "from_lng": -74.000, "to_lat": 40.002, "to_lng": -74.000,
         "distance_m": 111.2, "oneway": False},
    ]
    g = build_graph_from_edges(edges)
    assert g.number_of_nodes() == 3


def test_build_graph_from_edges_empty():
    g = build_graph_from_edges([])
    assert g.number_of_nodes() == 0


# ── fetch_road_graph (region-aware local lookup) ────────────────────────────

def test_fetch_roads_from_db_excludes_out_of_bbox_rows(db):
    from src.models import OsmRoad
    road = OsmRoad(
        region="la", min_lat=34.000, max_lat=34.001, min_lng=-118.300, max_lng=-118.299,
        from_lat=34.000, from_lng=-118.300, to_lat=34.001, to_lng=-118.299,
        distance_m=120.0, oneway=False,
    )
    db.add(road)
    db.commit()

    result = routing_module._fetch_roads_from_db("la", 33.900, -118.200, 33.901, -118.199)
    assert result == []


def test_fetch_roads_from_db_includes_matching_rows(db):
    from src.models import OsmRoad
    road = OsmRoad(
        region="la", min_lat=34.000, max_lat=34.001, min_lng=-118.300, max_lng=-118.299,
        from_lat=34.000, from_lng=-118.300, to_lat=34.001, to_lng=-118.299,
        distance_m=120.0, oneway=True,
    )
    db.add(road)
    db.commit()

    result = routing_module._fetch_roads_from_db("la", 33.999, -118.301, 34.002, -118.298)
    assert result == [{
        "from_lat": 34.000, "from_lng": -118.300,
        "to_lat": 34.001, "to_lng": -118.299,
        "distance_m": 120.0, "oneway": True,
    }]


def test_fetch_road_graph_imported_region_uses_local_db(db):
    from src.models import OsmRoad
    db.add(OsmRoad(
        region="la", min_lat=34.000, max_lat=34.001, min_lng=-118.300, max_lng=-118.299,
        from_lat=34.000, from_lng=-118.300, to_lat=34.001, to_lng=-118.299,
        distance_m=120.0, oneway=False,
    ))
    db.commit()

    with patch("requests.post") as mock_post:
        graph = routing_module.fetch_road_graph(33.999, -118.301, 34.002, -118.298)

    mock_post.assert_not_called()
    assert graph.has_edge((34.000, -118.300), (34.001, -118.299))


def test_fetch_road_graph_imported_region_empty_db_falls_back_to_overpass():
    """Same ambiguity as buildings: an imported region with zero local rows
    for this bbox might just be unimported yet, so this must not silently
    return an empty graph — it should fall back to live Overpass."""
    key = _road_bbox_key(34.100, -118.100, 34.101, -118.099)
    _clear_road_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": []}
    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            graph = routing_module.fetch_road_graph(34.100, -118.100, 34.101, -118.099)
    assert mock_post.called
    assert graph.number_of_nodes() == 0
    _clear_road_cache(key)


def test_fetch_road_graph_unimported_region_uses_overpass():
    key = _road_bbox_key(51.50, -0.10, 51.51, -0.09)
    _clear_road_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _simple_osm()
    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            graph = routing_module.fetch_road_graph(51.50, -0.10, 51.51, -0.09)
    assert mock_post.called
    assert graph.number_of_nodes() == 3
    _clear_road_cache(key)


# ── nearest_node ─────────────────────────────────────────────────────────────

def test_nearest_node_exact_match():
    g = build_graph(_simple_osm())
    assert nearest_node(g, 40.000, -74.000) == 1
    assert nearest_node(g, 40.002, -74.000) == 3


def test_nearest_node_between_two():
    g = build_graph(_simple_osm())
    # Closer to node 2
    assert nearest_node(g, 40.0009, -74.000) == 2


# ── compute_edge_weights ──────────────────────────────────────────────────────

def test_compute_edge_weights_sun_prefers_sunny():
    g = build_graph(_simple_osm())
    # First edge midpoint lat ~40.0005 (shaded), second ~40.0015 (sunny)
    def fake_shaded(lat, lng, polygons, index, sun_alt):
        return lat < 40.001
    with patch("src.routing.is_point_shaded_by_index", side_effect=fake_shaded):
        compute_edge_weights(g, [], 45.0, 180.0, "sun")
    # Shaded edge (1→2) should cost more than sunny edge (2→3)
    assert g.edges[1, 2]["weight"] > g.edges[2, 3]["weight"]


def test_compute_edge_weights_shade_prefers_shaded():
    g = build_graph(_simple_osm())
    def fake_shaded(lat, lng, polygons, index, sun_alt):
        return lat < 40.001
    with patch("src.routing.is_point_shaded_by_index", side_effect=fake_shaded):
        compute_edge_weights(g, [], 45.0, 180.0, "shade")
    # Sunny edge (2→3) should cost more than shaded edge (1→2)
    assert g.edges[2, 3]["weight"] > g.edges[1, 2]["weight"]


def test_compute_edge_weights_nighttime_no_penalty():
    g = build_graph(_simple_osm())
    dist = g.edges[1, 2]["distance_m"]
    compute_edge_weights(g, [], 0.0, 180.0, "sun")
    assert g.edges[1, 2]["weight"] == pytest.approx(dist)


def test_compute_edge_weights_penalty_factor():
    g = build_graph(_simple_osm())
    dist_12 = g.edges[1, 2]["distance_m"]
    # All edges shaded, sun preference → all penalized × SUN_PENALTY
    with patch("src.routing.is_point_shaded_by_index", return_value=True):
        compute_edge_weights(g, [], 45.0, 180.0, "sun")
    assert g.edges[1, 2]["weight"] == pytest.approx(dist_12 * 1.5)


# ── compute_edge_shading (dedup) ───────────────────────────────────────────────

def test_compute_edge_shading_dedupes_shared_midpoints():
    """4 directed edges share only 2 unique midpoints (bidirectional pairs) —
    the expensive shading check must run once per unique point, not per edge."""
    g = build_graph(_simple_osm())  # edges: 1-2, 2-1, 2-3, 3-2
    with patch("src.routing.is_point_shaded_by_index", return_value=False) as mock_shaded:
        compute_edge_shading(g, [], 45.0, 180.0)
    assert mock_shaded.call_count == 2


def test_compute_edge_shading_nighttime_all_shaded():
    g = build_graph(_simple_osm())
    compute_edge_shading(g, [], 0.0, 180.0)
    assert g.edges[1, 2]["shaded"] is True
    assert g.edges[2, 3]["shaded"] is True


# ── apply_preference_weights ───────────────────────────────────────────────────

def test_apply_preference_weights_sun_penalizes_shaded():
    g = build_graph(_simple_osm())
    for _, _, data in g.edges(data=True):
        data["shaded"] = False
    g.edges[1, 2]["shaded"] = True
    apply_preference_weights(g, "sun", 2.0)
    assert g.edges[1, 2]["weight"] == pytest.approx(g.edges[1, 2]["distance_m"] * 2.0)
    assert g.edges[2, 3]["weight"] == pytest.approx(g.edges[2, 3]["distance_m"])


def test_apply_preference_weights_shade_penalizes_sunny():
    g = build_graph(_simple_osm())
    for _, _, data in g.edges(data=True):
        data["shaded"] = False
    g.edges[1, 2]["shaded"] = True
    apply_preference_weights(g, "shade", 2.0)
    assert g.edges[1, 2]["weight"] == pytest.approx(g.edges[1, 2]["distance_m"])
    assert g.edges[2, 3]["weight"] == pytest.approx(g.edges[2, 3]["distance_m"] * 2.0)


# ── find_optimized_path ───────────────────────────────────────────────────────

def test_find_optimized_path_simple():
    g = build_graph(_simple_osm())
    path = find_optimized_path(g, 1, 3)
    assert path[0] == 1 and path[-1] == 3


def test_find_optimized_path_no_path():
    g = nx.DiGraph()
    g.add_node(1, lat=40.0, lng=-74.0)
    g.add_node(2, lat=40.001, lng=-74.0)
    assert find_optimized_path(g, 1, 2) == []


def test_find_optimized_path_picks_lower_weight():
    # Triangle: A→B direct (weight=400 — penalized shaded)
    #           A→C→B indirect (weight=300 — sunny detour)
    g = nx.DiGraph()
    g.add_node(1, lat=40.0, lng=-74.0)
    g.add_node(2, lat=40.002, lng=-74.0)
    g.add_node(3, lat=40.001, lng=-73.999)
    g.add_edge(1, 2, distance_m=200, mid_lat=40.001, mid_lng=-74.0, weight=400)
    g.add_edge(1, 3, distance_m=150, mid_lat=40.0005, mid_lng=-73.9995, weight=150)
    g.add_edge(3, 2, distance_m=150, mid_lat=40.0015, mid_lng=-73.9995, weight=150)
    path = find_optimized_path(g, 1, 2)
    assert path == [1, 3, 2]


# ── _path_length_m ───────────────────────────────────────────────────────────

def test_path_length_m_simple():
    g = build_graph(_simple_osm())
    expected = g.edges[1, 2]["distance_m"] + g.edges[2, 3]["distance_m"]
    assert _path_length_m(g, [1, 2, 3]) == pytest.approx(expected)


def test_path_length_m_single_node():
    g = build_graph(_simple_osm())
    assert _path_length_m(g, [1]) == 0.0


def test_path_length_m_empty():
    g = build_graph(_simple_osm())
    assert _path_length_m(g, []) == 0.0


# ── find_distance_path ────────────────────────────────────────────────────────

def test_find_distance_path_simple():
    g = build_graph(_simple_osm())
    path = find_distance_path(g, 1, 3)
    assert path[0] == 1 and path[-1] == 3


def test_find_distance_path_no_path():
    g = nx.DiGraph()
    g.add_node(1, lat=40.0, lng=-74.0)
    g.add_node(2, lat=40.001, lng=-74.0)
    assert find_distance_path(g, 1, 2) == []


def test_find_distance_path_picks_shorter_distance():
    # Triangle: direct A→B (distance_m=200, weight=300 penalized)
    #           detour A→C→B (distance_m=300, weight=300 sunny)
    # find_distance_path must pick direct (shorter distance_m), ignoring weights
    g = nx.DiGraph()
    g.add_node(1, lat=40.0, lng=-74.0)
    g.add_node(2, lat=40.002, lng=-74.0)
    g.add_node(3, lat=40.001, lng=-74.001)
    g.add_edge(1, 2, distance_m=200, mid_lat=40.001, mid_lng=-74.0, weight=300)
    g.add_edge(1, 3, distance_m=150, mid_lat=40.0005, mid_lng=-74.0005, weight=150)
    g.add_edge(3, 2, distance_m=150, mid_lat=40.0015, mid_lng=-74.0005, weight=150)
    path = find_distance_path(g, 1, 2)
    assert path == [1, 2]


# ── nodes_to_coords ───────────────────────────────────────────────────────────

def test_nodes_to_coords():
    g = build_graph(_simple_osm())
    coords = nodes_to_coords(g, [1, 2, 3])
    assert coords[0] == (40.000, -74.000)
    assert coords[2] == (40.002, -74.000)


# ── sample_waypoints ──────────────────────────────────────────────────────────

def test_sample_waypoints_fewer_than_n():
    coords = [(float(i), 0.0) for i in range(5)]
    assert sample_waypoints(coords, n=10) == coords


def test_sample_waypoints_exactly_n():
    coords = [(float(i), 0.0) for i in range(10)]
    assert sample_waypoints(coords, n=10) == coords


def test_sample_waypoints_more_than_n():
    coords = [(float(i), 0.0) for i in range(50)]
    result = sample_waypoints(coords, n=10)
    assert len(result) == 10
    assert result[0] == coords[0]
    assert result[-1] == coords[-1]


# ── simplify_path ────────────────────────────────────────────────────────────
# Geometry-preserving simplification (Douglas-Peucker) — unlike
# sample_waypoints' blind index-based thinning (which could skip a real turn
# and draw a straight line cutting across a street), this only ever drops a
# point that's within `tolerance_m` of the straight line between its
# neighbors, so every real turn beyond that tolerance survives.

def test_simplify_path_too_short_returned_as_is():
    coords = [(40.000, -74.000), (40.001, -74.000)]
    assert simplify_path(coords) == coords


def test_simplify_path_collinear_points_collapse_to_endpoints():
    # A straight north-south line with several redundant intermediate points.
    coords = [(40.0000 + i * 0.0001, -74.000) for i in range(10)]
    result = simplify_path(coords, tolerance_m=1.0)
    assert result == [coords[0], coords[-1]]


def test_simplify_path_keeps_real_turn_beyond_tolerance():
    # A clear 90-degree turn ~11m off the straight line — must survive a 3m tolerance.
    coords = [(40.0000, -74.0000), (40.0000, -73.9999), (40.0001, -73.9999)]
    result = simplify_path(coords, tolerance_m=3.0)
    assert coords[1] in result


def test_simplify_path_drops_jog_within_tolerance():
    # A tiny sub-meter wobble that shouldn't survive a several-meter tolerance.
    coords = [(40.00000, -74.00000), (40.000001, -74.000005), (40.00010, -74.00010)]
    result = simplify_path(coords, tolerance_m=5.0)
    assert result == [coords[0], coords[-1]]


def test_simplify_path_preserves_endpoints():
    coords = [(40.0 + i * 0.0002, -74.0 + (i % 3) * 0.0001) for i in range(15)]
    result = simplify_path(coords, tolerance_m=2.0)
    assert result[0] == coords[0]
    assert result[-1] == coords[-1]


def test_simplify_path_degenerate_loop_back_to_start():
    # start == end (a path that loops back on itself) — the perpendicular
    # distance falls back to a plain point-to-point distance rather than
    # dividing by a zero-length segment.
    coords = [(40.0000, -74.0000), (40.0010, -73.9990), (40.0000, -74.0000)]
    result = simplify_path(coords, tolerance_m=3.0)
    assert result[0] == coords[0]
    assert result[-1] == coords[-1]
    assert coords[1] in result


# ── _road_bbox_key / _road_sqlite_get / _road_sqlite_set ─────────────────────

def test_road_bbox_key_format():
    key = _road_bbox_key(40.0, -74.0, 40.5, -73.5)
    assert key == "road:40.0,-74.0,40.5,-73.5"


def test_road_sqlite_get_miss():
    assert _road_sqlite_get("road:nonexistent_key_xyz") is None


def test_road_sqlite_set_then_get():
    key = "road:test_set_get"
    data = {"elements": [{"type": "node", "id": 99}]}
    _road_sqlite_set(key, data)
    assert _road_sqlite_get(key) == data


def test_road_sqlite_get_exception():
    with patch("sqlite3.connect", side_effect=Exception("fail")):
        assert _road_sqlite_get("road:any") is None


def test_road_sqlite_set_exception():
    with patch("sqlite3.connect", side_effect=Exception("fail")):
        _road_sqlite_set("road:any", {"elements": []})  # must not raise


# ── fetch_osm_road_network ────────────────────────────────────────────────────

def test_fetch_osm_road_network_memory_cache_hit():
    key = _road_bbox_key(40.0, -74.01, 40.01, -73.99)
    cached = {"elements": [{"type": "node", "id": 42}]}
    routing_module._road_cache[key] = cached
    try:
        with patch("src.routing.requests.post") as mock_post:
            result = fetch_osm_road_network(40.0, -74.01, 40.01, -73.99)
        assert result == cached
        mock_post.assert_not_called()
    finally:
        _clear_road_cache(key)


def test_fetch_osm_road_network_sqlite_cache_hit():
    key = _road_bbox_key(41.0, -75.01, 41.01, -74.99)
    _clear_road_cache(key)
    cached = {"elements": [{"type": "node", "id": 7}]}
    with patch("src.routing._road_sqlite_get", return_value=cached):
        with patch("src.routing.requests.post") as mock_post:
            result = fetch_osm_road_network(41.0, -75.01, 41.01, -74.99)
    assert result == cached
    mock_post.assert_not_called()
    _clear_road_cache(key)


def test_fetch_osm_road_network_returns_data():
    key = _road_bbox_key(42.0, -76.01, 42.01, -75.99)
    _clear_road_cache(key)
    mock_data = {"elements": [{"type": "node", "id": 1, "lat": 40.0, "lon": -74.0}]}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data
    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("src.routing.requests.post", return_value=mock_resp) as mock_post:
            result = fetch_osm_road_network(42.0, -76.01, 42.01, -75.99)
    assert result == mock_data
    assert mock_post.called
    _clear_road_cache(key)


def test_fetch_osm_road_network_populates_memory_cache():
    key = _road_bbox_key(43.0, -77.01, 43.01, -76.99)
    _clear_road_cache(key)
    mock_data = {"elements": []}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data
    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("src.routing._road_sqlite_set"):
            with patch("src.routing.requests.post", return_value=mock_resp):
                fetch_osm_road_network(43.0, -77.01, 43.01, -76.99)
    assert routing_module._road_cache[key] == mock_data
    _clear_road_cache(key)


def test_fetch_osm_road_network_http_error_returns_empty():
    key = _road_bbox_key(44.0, -78.01, 44.01, -77.99)
    _clear_road_cache(key)
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("src.routing.requests.post", return_value=mock_resp):
            result = fetch_osm_road_network(44.0, -78.01, 44.01, -77.99)
    assert result == {"elements": []}


def test_fetch_osm_road_network_falls_back_to_working_mirror():
    """One mirror failing must not block a working mirror from succeeding —
    mirrors are tried concurrently, not one-at-a-time, so a single slow/dead
    mirror shouldn't multiply the total wait before giving up."""
    key = _road_bbox_key(46.0, -80.01, 46.01, -79.99)
    _clear_road_cache(key)
    mock_data = {"elements": []}
    good_resp = MagicMock()
    good_resp.status_code = 200
    good_resp.json.return_value = mock_data

    def fake_post(url, **kwargs):
        if url == OVERPASS_URLS[0]:
            raise Exception("mirror down")
        return good_resp

    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("src.routing.requests.post", side_effect=fake_post):
            result = fetch_osm_road_network(46.0, -80.01, 46.01, -79.99)
    assert result == mock_data
    _clear_road_cache(key)


def test_fetch_osm_road_network_tries_mirrors_concurrently_not_sequentially():
    """A slow mirror must not add its delay on top of the others' — mirrors
    are raced in parallel, so total wait should track the slowest single
    mirror, not the sum of all of them."""
    import time

    key = _road_bbox_key(48.0, -82.01, 48.01, -81.99)
    _clear_road_cache(key)
    good_resp = MagicMock()
    good_resp.status_code = 200
    good_resp.json.return_value = {"elements": []}

    def fake_post(url, **kwargs):
        time.sleep(0.15)
        if url == OVERPASS_URLS[0]:
            raise Exception("down")
        return good_resp

    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("src.routing.requests.post", side_effect=fake_post):
            start = time.monotonic()
            fetch_osm_road_network(48.0, -82.01, 48.01, -81.99)
            elapsed = time.monotonic() - start
    # Sequential retries mirror 2 only after mirror 1's 0.15s failure (>=0.3s
    # total); racing them concurrently should finish in ~0.15s.
    assert elapsed < 0.25
    _clear_road_cache(key)


def test_fetch_osm_road_network_tries_all_mirrors_when_all_fail():
    key = _road_bbox_key(47.0, -81.01, 47.01, -80.99)
    _clear_road_cache(key)
    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("src.routing.requests.post", side_effect=Exception("down")) as mock_post:
            result = fetch_osm_road_network(47.0, -81.01, 47.01, -80.99)
    assert result == {"elements": []}
    assert mock_post.call_count == len(OVERPASS_URLS)
    _clear_road_cache(key)


def test_fetch_osm_road_network_exception_returns_empty():
    key = _road_bbox_key(45.0, -79.01, 45.01, -78.99)
    _clear_road_cache(key)
    with patch("src.routing._road_sqlite_get", return_value=None):
        with patch("src.routing.requests.post", side_effect=Exception("timeout")):
            result = fetch_osm_road_network(45.0, -79.01, 45.01, -78.99)
    assert result == {"elements": []}


def test_fetch_osm_road_network_logs_failure_reason(caplog):
    """A silent empty result on total failure is undiagnosable in production —
    the actual reason (timeout, rate limit, DNS, etc.) must be logged."""
    key = _road_bbox_key(49.0, -83.01, 49.01, -82.99)
    _clear_road_cache(key)
    with caplog.at_level("WARNING"):
        with patch("src.routing._road_sqlite_get", return_value=None):
            with patch("src.routing.requests.post", side_effect=Exception("rate limited")):
                fetch_osm_road_network(49.0, -83.01, 49.01, -82.99)
    assert "rate limited" in caplog.text
    _clear_road_cache(key)


# ── endpoint tests ────────────────────────────────────────────────────────────

_OSM_DATA = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.000, "lon": -74.000},
        {"type": "node", "id": 2, "lat": 40.001, "lon": -74.000},
        {"type": "node", "id": 3, "lat": 40.002, "lon": -74.000},
        {"type": "way",  "id": 100, "nodes": [1, 2, 3], "tags": {"highway": "residential"}},
    ]
}


def test_optimized_route_endpoint_success(client, auth_headers):
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded", return_value=False),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000],
                "end": [40.002, -74.000],
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "waypoints" in body
    assert len(body["waypoints"]) >= 2
    assert body["sun_altitude"] == pytest.approx(45.0)


def test_optimized_route_endpoint_returns_full_path_not_downsampled(client, auth_headers):
    """A path with more real shape points than the old fixed sample count
    (25) must come back in full — downsampling to evenly-spaced indices was
    cutting straight lines across real turns whenever one fell between two
    sampled points, drawing the route diagonally across the street."""
    n_nodes = 40
    zigzag_osm = {
        "elements": (
            [
                {"type": "node", "id": i, "lat": 40.000 + i * 0.0001, "lon": -74.000 + (i % 2) * 0.0001}
                for i in range(1, n_nodes + 1)
            ]
            + [{"type": "way", "id": 100, "nodes": list(range(1, n_nodes + 1)), "tags": {"highway": "residential"}}]
        )
    }
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=zigzag_osm),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded", return_value=False),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.0001, -74.000],
                "end": [40.000 + n_nodes * 0.0001, -74.000],
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert len(resp.json()["waypoints"]) == n_nodes


def test_optimized_route_endpoint_nighttime(client, auth_headers):
    with (
        patch("src.routers.routing.get_sun_position", return_value=(-5.0, 270.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000],
                "end": [40.002, -74.000],
                "datetime": "2026-05-24T02:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    # Nighttime: still routes via OSM (distance-only weights), no straight line
    assert len(body["waypoints"]) >= 2
    assert body["waypoints"][0] == pytest.approx([40.000, -74.000], abs=0.01)
    assert body["waypoints"][-1] == pytest.approx([40.002, -74.000], abs=0.01)
    assert body["sun_altitude"] == pytest.approx(-5.0)


def test_optimized_route_endpoint_requires_auth(client):
    resp = client.post(
        "/sun/optimized-route",
        json={
            "start": [40.0, -74.0],
            "end": [40.002, -74.0],
            "datetime": "2026-05-24T14:00:00",
            "preference": "sun",
        },
    )
    assert resp.status_code == 401


def test_optimized_route_detour_cap_exceeded(client, auth_headers):
    """Sun path >30% longer than direct → fall back to distance path (fewer waypoints)."""
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routers.routing.find_optimized_path", return_value=[1, 3, 2]),
        patch("src.routers.routing.find_distance_path", return_value=[1, 2]),
        patch("src.routers.routing._path_length_m", side_effect=[400.0, 200.0]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000],
                "end": [40.002, -74.000],
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    # Distance path [1, 2] → 2 coords; sun path [1, 3, 2] → 3 coords
    assert len(resp.json()["waypoints"]) == 2


def test_optimized_route_detour_within_cap(client, auth_headers):
    """Sun path ≤30% longer than direct → keep sun path (more waypoints)."""
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routers.routing.find_optimized_path", return_value=[1, 3, 2]),
        patch("src.routers.routing.find_distance_path", return_value=[1, 2]),
        patch("src.routers.routing._path_length_m", side_effect=[230.0, 200.0]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000],
                "end": [40.002, -74.000],
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    # Sun path [1, 3, 2] → 3 coords kept (230 is not >200*1.3=260)
    assert len(resp.json()["waypoints"]) == 3


def test_optimized_route_uses_user_pref_max_detour(client, auth_headers):
    """Routing applies the user's stored pref_max_detour, not a hard-coded default."""
    # Set user preference to 10% via API
    assert client.patch("/users/me", json={"pref_max_detour": 10}, headers=auth_headers).status_code == 200

    # sun_len=300 > dist_len*1.10=220 → cap exceeded → distance path (2 waypoints)
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routers.routing.find_optimized_path", return_value=[1, 3, 2]),
        patch("src.routers.routing.find_distance_path", return_value=[1, 2]),
        patch("src.routers.routing._path_length_m", side_effect=[300.0, 200.0]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": [40.0, -74.0], "end": [40.002, -74.0],
                  "datetime": "2026-05-24T14:00:00", "preference": "sun"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert len(resp.json()["waypoints"]) == 2


def test_optimized_route_shade_gets_larger_detour_allowance(client, auth_headers):
    """Shade routes structurally need more detour than sun routes (most street
    edges are unshaded at once), so the same flat % cap used for sun would
    almost always reject shade routes and silently fall back to the plain
    distance path. Shade must get a larger effective detour allowance."""
    # sun_len=350 is >30% over dist_len=200 (a plain cap would reject this),
    # but must be kept for preference="shade" thanks to the larger allowance.
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routers.routing.find_optimized_path", return_value=[1, 3, 2]),
        patch("src.routers.routing.find_distance_path", return_value=[1, 2]),
        patch("src.routers.routing._path_length_m", side_effect=[350.0, 200.0]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000],
                "end": [40.002, -74.000],
                "datetime": "2026-05-24T14:00:00",
                "preference": "shade",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert len(resp.json()["waypoints"]) == 3


_SHADE_VS_SUN_OSM = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.0000, "lon": -74.000000},   # start
        {"type": "node", "id": 2, "lat": 40.0009, "lon": -74.000000},   # direct-path midpoint (unshaded)
        {"type": "node", "id": 3, "lat": 40.0018, "lon": -74.000000},   # end
        {"type": "node", "id": 4, "lat": 40.0009, "lon": -74.001147},   # detour-path midpoint (shaded)
        {"type": "way", "id": 100, "nodes": [1, 2, 3], "tags": {"highway": "residential"}},
        {"type": "way", "id": 101, "nodes": [1, 4, 3], "tags": {"highway": "residential"}},
    ]
}


def test_optimized_route_sun_and_shade_produce_different_routes(client, auth_headers):
    """Regression test: shade once silently collapsed to the exact same route
    as sun, because a flat detour cap disproportionately rejected shade's
    larger structural detour (see SHADE_DETOUR_MULTIPLIER). This must run the
    real endpoint end-to-end — graph build, Dijkstra, and the detour cap —
    rather than mocking path selection directly, since mocking path selection
    is exactly what let the original bug hide behind passing tests."""
    assert client.patch("/users/me", json={"pref_max_detour": 30}, headers=auth_headers).status_code == 200

    def fake_shaded(lat, lng, polygons, index, sun_alt):
        # Detour-path edges sit near lng=-74.001147; direct-path edges at lng=-74.000.
        return abs(lng - (-74.000)) > 0.0005

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_SHADE_VS_SUN_OSM),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded_by_index", side_effect=fake_shaded),
    ):
        sun_resp = client.post(
            "/sun/optimized-route",
            json={"start": [40.0000, -74.000000], "end": [40.0018, -74.000000],
                  "datetime": "2026-05-24T14:00:00", "preference": "sun"},
            headers=auth_headers,
        )
        shade_resp = client.post(
            "/sun/optimized-route",
            json={"start": [40.0000, -74.000000], "end": [40.0018, -74.000000],
                  "datetime": "2026-05-24T14:00:00", "preference": "shade"},
            headers=auth_headers,
        )

    assert sun_resp.status_code == 200
    assert shade_resp.status_code == 200

    sun_mid_lng = sun_resp.json()["waypoints"][1][1]
    shade_mid_lng = shade_resp.json()["waypoints"][1][1]

    # Sun takes the direct (unshaded) path through node 2 (lng ≈ -74.000)...
    assert sun_mid_lng == pytest.approx(-74.000, abs=1e-4)
    # ...shade must take the detour through node 4 (lng ≈ -74.001147) — not
    # silently fall back to the identical route sun took.
    assert shade_mid_lng == pytest.approx(-74.001147, abs=1e-4)
    assert sun_mid_lng != pytest.approx(shade_mid_lng, abs=1e-4)


_DISCONNECTED_OSM = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.000, "lon": -74.000},
        {"type": "node", "id": 2, "lat": 40.0005, "lon": -74.000},
        {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
        # Disconnected component — reachable by nearest_node but not by any path.
        {"type": "node", "id": 3, "lat": 41.000, "lon": -74.000},
        {"type": "node", "id": 4, "lat": 41.0005, "lon": -74.000},
        {"type": "way", "id": 101, "nodes": [3, 4], "tags": {"highway": "residential"}},
    ]
}


def test_optimized_route_endpoint_no_path_found(client, auth_headers):
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_DISCONNECTED_OSM),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000],
                "end": [41.0005, -74.000],
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 400
    assert "No path found" in resp.json()["detail"]


def test_optimized_route_endpoint_no_road_network(client, auth_headers):
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value={"elements": []}),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000],
                "end": [40.002, -74.000],
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 400
