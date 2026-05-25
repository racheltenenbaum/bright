import pytest
from unittest.mock import patch, MagicMock
import networkx as nx

from src.routing import (
    _haversine_m,
    build_graph,
    nearest_node,
    compute_edge_weights,
    find_optimized_path,
    nodes_to_coords,
    sample_waypoints,
    fetch_osm_road_network,
)

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
    def fake_shaded(lat, lng, buildings, sun_alt, sun_az, elev=0.0):
        return lat < 40.001
    with patch("src.routing.is_point_shaded", side_effect=fake_shaded):
        compute_edge_weights(g, [], 45.0, 180.0, "sun")
    # Shaded edge (1→2) should cost more than sunny edge (2→3)
    assert g.edges[1, 2]["weight"] > g.edges[2, 3]["weight"]


def test_compute_edge_weights_shade_prefers_shaded():
    g = build_graph(_simple_osm())
    def fake_shaded(lat, lng, buildings, sun_alt, sun_az, elev=0.0):
        return lat < 40.001
    with patch("src.routing.is_point_shaded", side_effect=fake_shaded):
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
    with patch("src.routing.is_point_shaded", return_value=True):
        compute_edge_weights(g, [], 45.0, 180.0, "sun")
    assert g.edges[1, 2]["weight"] == pytest.approx(dist_12 * 2.0)


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


# ── fetch_osm_road_network ────────────────────────────────────────────────────

def test_fetch_osm_road_network_returns_data():
    mock_data = {"elements": [{"type": "node", "id": 1, "lat": 40.0, "lon": -74.0}]}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data
    with patch("src.routing.requests.post", return_value=mock_resp) as mock_post:
        result = fetch_osm_road_network(40.0, -74.01, 40.01, -73.99)
    assert result == mock_data
    assert mock_post.called


def test_fetch_osm_road_network_http_error_returns_empty():
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    with patch("src.routing.requests.post", return_value=mock_resp):
        result = fetch_osm_road_network(40.0, -74.01, 40.01, -73.99)
    assert result == {"elements": []}


def test_fetch_osm_road_network_exception_returns_empty():
    with patch("src.routing.requests.post", side_effect=Exception("timeout")):
        result = fetch_osm_road_network(40.0, -74.01, 40.01, -73.99)
    assert result == {"elements": []}


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
        patch("src.routers.routing.fetch_osm_road_network", return_value=_OSM_DATA),
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


def test_optimized_route_endpoint_nighttime(client, auth_headers):
    with (
        patch("src.routers.routing.get_sun_position", return_value=(-5.0, 270.0)),
        patch("src.routers.routing.fetch_osm_road_network", return_value=_OSM_DATA),
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
    # Nighttime: returns direct start→end line
    assert body["waypoints"][0] == [40.000, -74.000]
    assert body["waypoints"][-1] == [40.002, -74.000]


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


def test_optimized_route_endpoint_no_road_network(client, auth_headers):
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routers.routing.fetch_osm_road_network", return_value={"elements": []}),
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
