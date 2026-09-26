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
    nearest_node_candidates,
    describe_no_path_found,
    compute_edge_shading,
    compute_edge_weights,
    apply_preference_weights,
    find_distance_path,
    find_optimized_path,
    nodes_to_coords,
    route_bbox_padding_m,
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


def test_build_graph_service_alley_excluded():
    """highway=service with service=alley produced the zigzag "staircase"
    routes reported in East Hollywood, LA — the optimizer ducked through
    back alleys between blocks instead of following the direct street,
    since alleys weren't in EXCLUDED_SERVICE_SUBTYPES."""
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.0, "lon": -74.0},
            {"type": "node", "id": 2, "lat": 40.001, "lon": -74.0},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "service", "service": "alley"}},
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


def test_fetch_roads_from_db_caches_exact_bbox(db):
    """A second call with the identical bbox must not re-hit MySQL — verified
    by deleting the underlying row between calls and confirming the second
    call still returns it (proof it came from cache, not a fresh query)."""
    from src.models import OsmRoad
    routing_module._db_roads_cache.clear()
    road = OsmRoad(
        region="la", min_lat=34.000, max_lat=34.001, min_lng=-118.300, max_lng=-118.299,
        from_lat=34.000, from_lng=-118.300, to_lat=34.001, to_lng=-118.299,
        distance_m=120.0, oneway=True,
    )
    db.add(road)
    db.commit()

    first = routing_module._fetch_roads_from_db("la", 33.999, -118.301, 34.002, -118.298)
    assert len(first) == 1

    db.query(OsmRoad).delete()
    db.commit()

    second = routing_module._fetch_roads_from_db("la", 33.999, -118.301, 34.002, -118.298)
    assert second == first
    routing_module._db_roads_cache.clear()


def test_fetch_roads_from_db_does_not_reuse_containing_bbox(db):
    """Unlike the buildings cache, this is deliberately exact-match only —
    a smaller bbox fully inside an already-cached larger one must still hit
    the DB fresh, not silently inherit the larger bbox's (potentially much
    bigger, unrelated) road set."""
    from src.models import OsmRoad
    routing_module._db_roads_cache.clear()
    road = OsmRoad(
        region="la", min_lat=34.000, max_lat=34.001, min_lng=-118.300, max_lng=-118.299,
        from_lat=34.000, from_lng=-118.300, to_lat=34.001, to_lng=-118.299,
        distance_m=120.0, oneway=True,
    )
    db.add(road)
    db.commit()

    outer = routing_module._fetch_roads_from_db("la", 33.90, -118.40, 34.10, -118.20)
    assert len(outer) == 1

    db.query(OsmRoad).delete()
    db.commit()

    inner = routing_module._fetch_roads_from_db("la", 33.999, -118.301, 34.002, -118.298)
    assert inner == []
    routing_module._db_roads_cache.clear()


def test_fetch_roads_from_db_cache_is_region_scoped(db):
    from src.models import OsmRoad
    routing_module._db_roads_cache.clear()
    routing_module._db_roads_cache[("la", routing_module._road_bbox_key(33.90, -118.40, 34.10, -118.20))] = [
        {"from_lat": 0.0, "from_lng": 0.0, "to_lat": 0.0, "to_lng": 0.0, "distance_m": 1.0, "oneway": False}
    ]
    road = OsmRoad(
        region="nyc", min_lat=34.000, max_lat=34.001, min_lng=-118.300, max_lng=-118.299,
        from_lat=34.000, from_lng=-118.300, to_lat=34.001, to_lng=-118.299,
        distance_m=120.0, oneway=True,
    )
    db.add(road)
    db.commit()

    result = routing_module._fetch_roads_from_db("nyc", 33.90, -118.40, 34.10, -118.20)
    assert len(result) == 1
    assert result[0]["distance_m"] == 120.0
    routing_module._db_roads_cache.clear()


def test_fetch_roads_from_db_cache_evicts_oldest_beyond_cap(db):
    routing_module._db_roads_cache.clear()
    for i in range(routing_module._DB_ROADS_CACHE_MAX_ENTRIES + 1):
        routing_module._fetch_roads_from_db("la", float(i), 0.0, float(i) + 1, 1.0)
    assert len(routing_module._db_roads_cache) == routing_module._DB_ROADS_CACHE_MAX_ENTRIES
    # The very first entry (s=0.0) must have been evicted.
    first_key = ("la", routing_module._road_bbox_key(0.0, 0.0, 1.0, 1.0))
    assert first_key not in routing_module._db_roads_cache
    routing_module._db_roads_cache.clear()


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


# ── route_bbox_padding_m ─────────────────────────────────────────────────────
# A fixed 100m pad was too narrow for longer routes: a real walking path
# often has to jog sideways (a bridge crossing, a one-way detour) by more
# than that, and a too-narrow bbox then has no road connecting start to end
# at all — reproduced in production for a ~3.4km Vienna route that needed to
# reach a specific canal crossing outside the fixed 100m-wide box.
#
# max_detour_fraction (added later) fixes a second, separate bug: raising a
# user's max-detour setting to 100% changed nothing for a real reported
# case, because the setting only decided whether to *accept* an
# already-found path — the search box itself stayed the same fixed size
# regardless, so if no shaded street existed inside it, none could ever be
# found no matter how much extra walking the user said they'd accept.

def test_route_bbox_padding_m_short_route_uses_minimum():
    assert route_bbox_padding_m(50.0) == 100.0


def test_route_bbox_padding_m_scales_with_distance():
    assert route_bbox_padding_m(2000.0) == pytest.approx(400.0)


def test_route_bbox_padding_m_caps_at_maximum():
    assert route_bbox_padding_m(50_000.0) == 2000.0


def test_route_bbox_padding_m_default_detour_fraction_is_zero():
    assert route_bbox_padding_m(2000.0) == route_bbox_padding_m(2000.0, 0.0)


def test_route_bbox_padding_m_detour_fraction_adds_padding():
    base = route_bbox_padding_m(2000.0, 0.0)
    with_detour = route_bbox_padding_m(2000.0, 0.75)
    assert with_detour > base
    assert with_detour == pytest.approx(base + 2000.0 * 0.75 * 0.5)


def test_route_bbox_padding_m_detour_fraction_still_caps_at_maximum():
    assert route_bbox_padding_m(50_000.0, 2.5) == 2000.0


# ── nearest_node ─────────────────────────────────────────────────────────────

def test_nearest_node_exact_match():
    g = build_graph(_simple_osm())
    assert nearest_node(g, 40.000, -74.000) == 1
    assert nearest_node(g, 40.002, -74.000) == 3


def test_nearest_node_between_two():
    g = build_graph(_simple_osm())
    # Closer to node 2
    assert nearest_node(g, 40.0009, -74.000) == 2


def test_nearest_node_skips_tiny_disconnected_stub():
    """A real reported bad route (NYC, "556 Fashion Avenue"): its literal
    nearest OSM node was a 2-node dead-end stub with no connection to the
    real street network a few meters away, so routing failed with "No path
    found" from the wrong starting point. nearest_node should prefer a
    node in a real (reasonably-sized) component over a geometrically closer
    one stranded in a tiny island."""
    data = {
        "elements": [
            # Tiny 2-node stub, closest to the query point.
            {"type": "node", "id": 1, "lat": 40.00001, "lon": -74.00001},
            {"type": "node", "id": 2, "lat": 40.00002, "lon": -74.00002},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
            # Real network nearby: 6 connected nodes, slightly further away.
            {"type": "node", "id": 10, "lat": 40.0010, "lon": -74.0010},
            {"type": "node", "id": 11, "lat": 40.0011, "lon": -74.0011},
            {"type": "node", "id": 12, "lat": 40.0012, "lon": -74.0012},
            {"type": "node", "id": 13, "lat": 40.0013, "lon": -74.0013},
            {"type": "node", "id": 14, "lat": 40.0014, "lon": -74.0014},
            {"type": "node", "id": 15, "lat": 40.0015, "lon": -74.0015},
            {"type": "way", "id": 101, "nodes": [10, 11, 12, 13, 14, 15], "tags": {"highway": "residential"}},
        ]
    }
    g = build_graph(data)
    assert nearest_node(g, 40.0, -74.0) == 10


def test_nearest_node_accepts_precomputed_candidates():
    """A request needs nearest_node for both start and end, and recomputing
    connected-components from scratch inside nearest_node each time is
    expensive on a large graph (confirmed in production: ~3.4s combined for
    two calls on a ~100k-node graph). Passing the same precomputed candidate
    set into both calls must give the identical result as the no-arg form."""
    g = build_graph(_simple_osm())
    candidates = nearest_node_candidates(g)
    assert nearest_node(g, 40.0009, -74.000, candidates=candidates) == nearest_node(g, 40.0009, -74.000)


def test_nearest_node_candidates_skips_tiny_disconnected_stub():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.00001, "lon": -74.00001},
            {"type": "node", "id": 2, "lat": 40.00002, "lon": -74.00002},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
            {"type": "node", "id": 10, "lat": 40.0010, "lon": -74.0010},
            {"type": "node", "id": 11, "lat": 40.0011, "lon": -74.0011},
            {"type": "node", "id": 12, "lat": 40.0012, "lon": -74.0012},
            {"type": "node", "id": 13, "lat": 40.0013, "lon": -74.0013},
            {"type": "node", "id": 14, "lat": 40.0014, "lon": -74.0014},
            {"type": "node", "id": 15, "lat": 40.0015, "lon": -74.0015},
            {"type": "way", "id": 101, "nodes": [10, 11, 12, 13, 14, 15], "tags": {"highway": "residential"}},
        ]
    }
    g = build_graph(data)
    candidates = nearest_node_candidates(g)
    assert nearest_node(g, 40.0, -74.0, candidates=candidates) == 10


def test_nearest_node_reuses_candidates_without_recomputing_components():
    """The whole point of passing candidates in is to skip the expensive
    per-call connected-components recomputation — verify it's actually
    skipped, not just that the result happens to match."""
    g = build_graph(_simple_osm())
    candidates = nearest_node_candidates(g)
    with patch("src.routing.nx.connected_components") as mock_cc:
        nearest_node(g, 40.0009, -74.000, candidates=candidates)
    mock_cc.assert_not_called()


# ── describe_no_path_found ──────────────────────────────────────────────────────

def test_describe_no_path_found_reports_separate_components():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.000, "lon": -74.000},
            {"type": "node", "id": 2, "lat": 40.0005, "lon": -74.000},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
            {"type": "node", "id": 3, "lat": 41.000, "lon": -74.000},
            {"type": "node", "id": 4, "lat": 41.0005, "lon": -74.000},
            {"type": "way", "id": 101, "nodes": [3, 4], "tags": {"highway": "residential"}},
        ]
    }
    g = build_graph(data)
    result = describe_no_path_found(g, 1, 4)
    assert result["num_components"] == 2
    assert sorted(result["component_sizes"]) == [2, 2]
    assert result["same_component"] is False
    assert result["start_component"] != result["end_component"]


def test_describe_no_path_found_same_component():
    g = build_graph(_simple_osm())
    result = describe_no_path_found(g, 1, 3)
    assert result["num_components"] == 1
    assert result["same_component"] is True
    assert result["start_component"] == result["end_component"]


# ── connected_components_by_size / nearest_node_in_set ──────────────────────────

def test_connected_components_by_size_orders_largest_first():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 40.000, "lon": -74.000},
            {"type": "node", "id": 2, "lat": 40.0005, "lon": -74.000},
            {"type": "node", "id": 3, "lat": 40.0010, "lon": -74.000},
            {"type": "way", "id": 100, "nodes": [1, 2, 3], "tags": {"highway": "residential"}},
            {"type": "node", "id": 4, "lat": 41.000, "lon": -74.000},
            {"type": "node", "id": 5, "lat": 41.0005, "lon": -74.000},
            {"type": "way", "id": 101, "nodes": [4, 5], "tags": {"highway": "residential"}},
        ]
    }
    g = build_graph(data)
    components = routing_module.connected_components_by_size(g)
    assert [len(c) for c in components] == [3, 2]


def test_nearest_node_in_set_restricted_to_given_nodes():
    g = build_graph(_simple_osm())  # nodes 1,2,3 at lat 40.000/40.001/40.002
    # Closest overall is node 3, but restricting the candidate set to {1, 2}
    # must pick node 2 (closer of the two allowed) instead.
    assert routing_module.nearest_node_in_set(g, 40.002, -74.000, {1, 2}) == 2


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
    assert g.edges[1, 2]["weight"] == pytest.approx(dist_12 * routing_module.SUN_PENALTY)


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


def test_compute_edge_shading_far_building_never_affects_result():
    """Same setup as above, but asserting on the actual output: a shading
    result that includes a too-far-to-matter building must be identical to
    one computed without it at all."""
    g1 = build_graph(_simple_osm())
    g2 = build_graph(_simple_osm())
    nearby_building = {
        "footprint": [[40.0005, -74.0001], [40.0005, -74.0000], [40.0006, -74.0000]],
        "height": 20.0,
    }
    far_away_building = {
        "footprint": [[41.0, -74.0001], [41.0, -74.0000], [41.0006, -74.0000]],
        "height": 20.0,
    }

    compute_edge_shading(g1, [nearby_building], 45.0, 180.0)
    compute_edge_shading(g2, [nearby_building, far_away_building], 45.0, 180.0)

    assert g1.edges[1, 2]["shaded"] == g2.edges[1, 2]["shaded"]
    assert g1.edges[2, 3]["shaded"] == g2.edges[2, 3]["shaded"]


# ── shadow polygon cache ────────────────────────────────────────────────────────

def test_shadow_polygons_and_index_caches_by_buildings_identity_and_sun_bucket():
    """A second call with the same buildings list object and a near-identical
    sun position must reuse the cached polygons/index rather than rebuilding —
    verified by mocking precompute_shadow_polygons and confirming it's only
    invoked once across two calls."""
    routing_module._shadow_polygon_cache.clear()
    buildings = [{"footprint": [[40.0005, -74.0001], [40.0005, -74.0000], [40.0006, -74.0000]], "height": 20.0}]

    with patch(
        "src.routing.precompute_shadow_polygons", wraps=routing_module.precompute_shadow_polygons
    ) as mock_precompute:
        polygons1, index1 = routing_module._shadow_polygons_and_index(buildings, 45.0, 180.0)
        # Sun angle drifted slightly (same minute, a few seconds later) — must
        # still hit the cache since both round to the same 1° bucket.
        polygons2, index2 = routing_module._shadow_polygons_and_index(buildings, 45.3, 180.2)

    mock_precompute.assert_called_once()
    assert polygons1 is polygons2
    assert index1 is index2
    routing_module._shadow_polygon_cache.clear()


def test_shadow_polygons_and_index_different_buildings_object_misses_cache():
    """Two distinct buildings list objects — even with identical content —
    must not share a cache entry, since they aren't guaranteed to stay in
    sync (e.g. one could be evicted and rebuilt from the DB independently)."""
    routing_module._shadow_polygon_cache.clear()
    buildings_a = [{"footprint": [[40.0005, -74.0001], [40.0005, -74.0000], [40.0006, -74.0000]], "height": 20.0}]
    buildings_b = [{"footprint": [[40.0005, -74.0001], [40.0005, -74.0000], [40.0006, -74.0000]], "height": 20.0}]

    with patch(
        "src.routing.precompute_shadow_polygons", wraps=routing_module.precompute_shadow_polygons
    ) as mock_precompute:
        routing_module._shadow_polygons_and_index(buildings_a, 45.0, 180.0)
        routing_module._shadow_polygons_and_index(buildings_b, 45.0, 180.0)

    assert mock_precompute.call_count == 2
    routing_module._shadow_polygon_cache.clear()


def test_shadow_polygons_and_index_different_sun_bucket_misses_cache():
    routing_module._shadow_polygon_cache.clear()
    buildings = [{"footprint": [[40.0005, -74.0001], [40.0005, -74.0000], [40.0006, -74.0000]], "height": 20.0}]

    with patch(
        "src.routing.precompute_shadow_polygons", wraps=routing_module.precompute_shadow_polygons
    ) as mock_precompute:
        routing_module._shadow_polygons_and_index(buildings, 45.0, 180.0)
        routing_module._shadow_polygons_and_index(buildings, 60.0, 180.0)

    assert mock_precompute.call_count == 2
    routing_module._shadow_polygon_cache.clear()


def test_shadow_polygon_cache_evicts_oldest_beyond_cap():
    routing_module._shadow_polygon_cache.clear()
    for i in range(routing_module._SHADOW_POLYGON_CACHE_MAX_ENTRIES + 1):
        routing_module._shadow_polygons_and_index([], float(i % 89) + 1, 180.0)
    assert len(routing_module._shadow_polygon_cache) == routing_module._SHADOW_POLYGON_CACHE_MAX_ENTRIES
    routing_module._shadow_polygon_cache.clear()


def test_compute_edge_shading_reuses_cached_shadow_polygons():
    """End-to-end: calling compute_edge_shading twice with the same buildings
    list object must only build shadow polygons once."""
    routing_module._shadow_polygon_cache.clear()
    g1 = build_graph(_simple_osm())
    g2 = build_graph(_simple_osm())
    buildings = [{"footprint": [[40.0005, -74.0001], [40.0005, -74.0000], [40.0006, -74.0000]], "height": 20.0}]

    with patch(
        "src.routing.precompute_shadow_polygons", wraps=routing_module.precompute_shadow_polygons
    ) as mock_precompute:
        compute_edge_shading(g1, buildings, 45.0, 180.0)
        compute_edge_shading(g2, buildings, 45.0, 180.0)

    mock_precompute.assert_called_once()
    assert g1.edges[1, 2]["shaded"] == g2.edges[1, 2]["shaded"]
    routing_module._shadow_polygon_cache.clear()


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
    """A path with more real turns than the old fixed sample count (25) must
    still show every one of them — downsampling to evenly-spaced indices was
    cutting straight lines across real turns whenever one fell between two
    sampled points, drawing the route diagonally across the street. Each
    zigzag point here is offset ~25m (well beyond simplify_path's 8m
    tolerance), so every one is a genuine turn that must survive."""
    n_nodes = 40
    zigzag_osm = {
        "elements": (
            [
                {"type": "node", "id": i, "lat": 40.000 + i * 0.0001, "lon": -74.000 + (i % 2) * 0.0003}
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
    # Not the old fixed cap of 25 — every genuine zigzag turn survives
    # simplification (allow the endpoint itself to merge into its neighbor).
    assert len(resp.json()["waypoints"]) >= n_nodes - 1


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


def test_optimized_route_endpoint_works_without_auth(client):
    """Core computation endpoints work anonymously — only saving (routes,
    spots, account settings) requires an account. An anonymous request gets
    the same default detour tolerance a new account starts with."""
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded", return_value=False),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.0, -74.0],
                "end": [40.002, -74.0],
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
        )
    assert resp.status_code == 200


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


def test_optimized_route_anonymous_uses_default_max_detour(client):
    """An anonymous request (no Authorization header) must not error, and
    must use the same default detour tolerance a brand-new account starts
    with (DEFAULT_MAX_DETOUR), not 0% or some other unintended fallback."""
    from src.routers.routing import DEFAULT_MAX_DETOUR

    captured_max_detour = {}

    def fake_padding(straight_line_m, max_detour_fraction=0.0):
        captured_max_detour["value"] = max_detour_fraction
        return 100.0

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded", return_value=False),
        patch("src.routers.routing.route_bbox_padding_m", side_effect=fake_padding),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": [40.0, -74.0], "end": [40.002, -74.0],
                  "datetime": "2026-05-24T14:00:00", "preference": "sun"},
        )

    assert resp.status_code == 200
    assert captured_max_detour["value"] == pytest.approx(DEFAULT_MAX_DETOUR / 100)


def test_optimized_route_anonymous_with_explicit_max_detour(client):
    """An anonymous user can adjust detour tolerance for the current request
    (e.g. via the Plan Route screen's Sun/Shade Priority control) without an
    account — this only works locally/per-request, never persisted, but the
    endpoint must actually honor it rather than silently falling back to
    DEFAULT_MAX_DETOUR for every logged-out request."""
    captured_max_detour = {}

    def fake_padding(straight_line_m, max_detour_fraction=0.0):
        captured_max_detour["value"] = max_detour_fraction
        return 100.0

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded", return_value=False),
        patch("src.routers.routing.route_bbox_padding_m", side_effect=fake_padding),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": [40.0, -74.0], "end": [40.002, -74.0],
                  "datetime": "2026-05-24T14:00:00", "preference": "sun",
                  "max_detour": 70},
        )

    assert resp.status_code == 200
    assert captured_max_detour["value"] == pytest.approx(70 / 100)


def test_optimized_route_explicit_max_detour_overrides_account_pref(client, auth_headers):
    """A logged-in user's explicit request-level max_detour (e.g. adjusted
    ad hoc on the Plan Route screen) takes priority over their saved account
    pref_max_detour, so trying a different value doesn't require saving it
    to the account first."""
    assert client.patch("/users/me", json={"pref_max_detour": 10}, headers=auth_headers).status_code == 200

    captured_max_detour = {}

    def fake_padding(straight_line_m, max_detour_fraction=0.0):
        captured_max_detour["value"] = max_detour_fraction
        return 100.0

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_OSM_DATA),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded", return_value=False),
        patch("src.routers.routing.route_bbox_padding_m", side_effect=fake_padding),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={"start": [40.0, -74.0], "end": [40.002, -74.0],
                  "datetime": "2026-05-24T14:00:00", "preference": "sun",
                  "max_detour": 70},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert captured_max_detour["value"] == pytest.approx(70 / 100)


def test_optimized_route_rejects_out_of_range_max_detour(client):
    resp = client.post(
        "/sun/optimized-route",
        json={"start": [40.0, -74.0], "end": [40.002, -74.0],
              "datetime": "2026-05-24T14:00:00", "preference": "sun",
              "max_detour": 0},
    )
    assert resp.status_code == 422

    resp = client.post(
        "/sun/optimized-route",
        json={"start": [40.0, -74.0], "end": [40.002, -74.0],
              "datetime": "2026-05-24T14:00:00", "preference": "sun",
              "max_detour": 101},
    )
    assert resp.status_code == 422


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


_MODERATE_SHADE_DETOUR_OSM = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.000, "lon": -74.000},
        {"type": "node", "id": 2, "lat": 40.009, "lon": -74.000},
        {"type": "node", "id": 3, "lat": 40.0045, "lon": -73.992674},  # shaded detour, ~60% longer
        {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
        {"type": "way", "id": 101, "nodes": [1, 3], "tags": {"highway": "residential"}},
        {"type": "way", "id": 102, "nodes": [3, 2], "tags": {"highway": "residential"}},
    ]
}


def test_optimized_route_shade_takes_moderate_detour_for_real_shade(client, auth_headers):
    """Regression test for SUN_PENALTY being too weak in practice: on a real
    ~830m LA route with a genuinely more-shaded alternative (43% longer),
    the optimizer never even tried it at the old penalty (1.5) — it picked
    the exact same path as plain distance. This graph reproduces that shape
    at a smaller scale: a fully-shaded detour ~60% longer than the direct
    unshaded route. At the old penalty (1.5x on the unwanted/unshaded edge)
    the detour's real cost (1.60x direct) exceeds that penalized weight, so
    Dijkstra picks the direct route regardless of preference; the current
    penalty must be strong enough to actually choose the detour instead,
    while still comfortably inside the default user's accept/reject cap
    (30% max_detour * SHADE_DETOUR_MULTIPLIER 2.5x = 75% allowance) so the
    endpoint doesn't reject it afterward. Runs the real endpoint end-to-end
    (real graph, real Dijkstra) rather than mocking path selection, which
    is exactly what let the original weak-penalty behavior hide."""

    def fake_shaded(lat, lng, polygons, index, sun_alt):
        # Direct edge midpoint sits at lng=-74.000 (unshaded); both detour
        # edges' midpoints sit around lng=-73.9963 (shaded).
        return lng > -73.998

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_MODERATE_SHADE_DETOUR_OSM),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded_by_index", side_effect=fake_shaded),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": [40.000, -74.000], "end": [40.009, -74.000],
                "datetime": "2026-05-24T14:00:00", "preference": "shade",
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200
    lngs = [pt[1] for pt in resp.json()["waypoints"]]
    # Took the detour through node 3 (lng ≈ -73.992674), not the direct
    # unshaded edge straight up lng = -74.000.
    assert max(lngs) == pytest.approx(-73.992674, abs=1e-4)


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


_RETRY_DISCONNECTED_OSM = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.0000, "lon": -74.000},
        {"type": "node", "id": 2, "lat": 40.0003, "lon": -74.000},
        {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
        {"type": "node", "id": 3, "lat": 40.0024, "lon": -74.000},
        {"type": "node", "id": 4, "lat": 40.0027, "lon": -74.000},
        {"type": "way", "id": 101, "nodes": [3, 4], "tags": {"highway": "residential"}},
    ]
}

_CONNECTED_OSM = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.0000, "lon": -74.000},
        {"type": "node", "id": 2, "lat": 40.0010, "lon": -74.000},
        {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
        {"type": "node", "id": 3, "lat": 40.0017, "lon": -74.000},
        {"type": "node", "id": 4, "lat": 40.0027, "lon": -74.000},
        {"type": "way", "id": 101, "nodes": [3, 4], "tags": {"highway": "residential"}},
        # The connector — only present once a wide-enough bbox reaches it.
        {"type": "node", "id": 5, "lat": 40.0013, "lon": -74.000},
        {"type": "way", "id": 102, "nodes": [2, 5, 3], "tags": {"highway": "residential"}},
    ]
}


# start/end kept close together (~300m) so the default padding is well
# under ROUTE_BBOX_MAX_PADDING_M and a retry actually has room to trigger —
# unlike the huge separation used above, which already forces max padding
# on the very first attempt.
_RETRY_START = [40.0000, -74.000]
_RETRY_END = [40.0027, -74.000]


def test_optimized_route_retries_with_wider_bbox_when_disconnected(client, auth_headers, caplog):
    """A real reported case: Heldenplatz (a real, well-connected central
    Vienna square) came back as an isolated ~20-node island, disconnected
    from the main street network within the default search bbox — the app
    must never give up with a hard error for something this clearly
    reachable. If the narrow (default-padding) bbox comes back disconnected,
    a second attempt with the widest bbox this app ever uses must be tried
    before failing."""
    def fetch_road_graph_side_effect(s, w, n, e):
        # Only the wide retry bbox (padded to ROUTE_BBOX_MAX_PADDING_M,
        # ~2000m) reaches far enough to include the connector node.
        if (n - s) > 0.01:
            return build_graph(_CONNECTED_OSM)
        return build_graph(_RETRY_DISCONNECTED_OSM)

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routers.routing.fetch_road_graph", side_effect=fetch_road_graph_side_effect),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        with caplog.at_level("WARNING"):
            resp = client.post(
                "/sun/optimized-route",
                json={
                    "start": _RETRY_START, "end": _RETRY_END,
                    "datetime": "2026-05-24T14:00:00", "preference": "sun",
                },
                headers=auth_headers,
            )
    assert resp.status_code == 200
    assert len(resp.json()["waypoints"]) > 0
    assert any("retrying with max bbox padding" in r.message for r in caplog.records)


def test_optimized_route_no_retry_when_wide_bbox_also_disconnected(client, auth_headers, caplog):
    """If even the widened bbox can't connect them, this must still fail —
    not retry forever — but the failure log must show retried=True so it's
    clear the wider search was actually attempted."""
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routers.routing.fetch_road_graph", return_value=build_graph(_RETRY_DISCONNECTED_OSM)),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        with caplog.at_level("WARNING"):
            resp = client.post(
                "/sun/optimized-route",
                json={
                    "start": _RETRY_START, "end": _RETRY_END,
                    "datetime": "2026-05-24T14:00:00", "preference": "sun",
                },
                headers=auth_headers,
            )
    assert resp.status_code == 400
    assert any("retried=True" in r.message for r in caplog.records)


_FALLBACK_OSM = {
    "elements": [
        # Main, well-connected component (6 nodes — above
        # MIN_COMPONENT_SIZE_FOR_NEAREST_NODE, so it's real "big" nearest_node
        # territory, not the small-graph fallback-to-all-nodes exception).
        {"type": "node", "id": 1, "lat": 40.0000, "lon": -74.000},
        {"type": "node", "id": 2, "lat": 40.0002, "lon": -74.000},
        {"type": "node", "id": 3, "lat": 40.0004, "lon": -74.000},
        {"type": "node", "id": 4, "lat": 40.0006, "lon": -74.000},
        {"type": "node", "id": 5, "lat": 40.0008, "lon": -74.000},
        {"type": "node", "id": 6, "lat": 40.0010, "lon": -74.000},
        {"type": "way", "id": 100, "nodes": [1, 2, 3, 4, 5, 6], "tags": {"highway": "residential"}},
        # A smaller but still "big enough" (5-node) isolated component, far
        # from the main one — a real Heldenplatz-shaped case: OSM genuinely
        # has no path data connecting it, not a bbox-too-narrow problem.
        {"type": "node", "id": 10, "lat": 41.0000, "lon": -74.000},
        {"type": "node", "id": 11, "lat": 41.0002, "lon": -74.000},
        {"type": "node", "id": 12, "lat": 41.0004, "lon": -74.000},
        {"type": "node", "id": 13, "lat": 41.0006, "lon": -74.000},
        {"type": "node", "id": 14, "lat": 41.0008, "lon": -74.000},
        {"type": "way", "id": 101, "nodes": [10, 11, 12, 13, 14], "tags": {"highway": "residential"}},
    ]
}


def test_optimized_route_falls_back_to_nearest_reachable_point(client, auth_headers, caplog):
    """A real reported case: Heldenplatz's open plaza surface genuinely has
    no OSM path data crossing it — not fixable by widening the search bbox
    or handling OSM relations better, since there's nothing there to find.
    Rachel's explicit requirement: this must never surface as a hard error
    for something this clearly reachable in reality. When the destination
    lands in a small isolated component even after the widened retry, the
    route must fall back to the nearest point in the graph's main connected
    component and still return 200, not 400."""
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routers.routing.fetch_road_graph", return_value=build_graph(_FALLBACK_OSM)),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        with caplog.at_level("WARNING"):
            resp = client.post(
                "/sun/optimized-route",
                json={
                    "start": [40.0000, -74.000], "end": [41.0004, -74.000],
                    "datetime": "2026-05-24T14:00:00", "preference": "sun",
                },
                headers=auth_headers,
            )
    assert resp.status_code == 200
    waypoints = resp.json()["waypoints"]
    assert len(waypoints) > 0
    # The route must land in the main component (near lat 40.00x), not the
    # isolated one (lat 41.00x) — confirms the fallback actually rerouted
    # to a reachable point instead of just silently returning garbage.
    assert all(lat < 41.0 for lat, lng in waypoints)
    assert any("falling back to nearest reachable point" in r.message for r in caplog.records)


def test_optimized_route_fallback_declines_for_too_small_main_component(client, auth_headers):
    """The fallback must not engage when even the "main" component is too
    small to be meaningful (e.g. tiny test-scale graphs) — must still fail
    cleanly with a 400, not silently reroute to an arbitrary tiny island."""
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routers.routing.fetch_road_graph", return_value=build_graph(_RETRY_DISCONNECTED_OSM)),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": _RETRY_START, "end": _RETRY_END,
                "datetime": "2026-05-24T14:00:00", "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 400


def test_optimized_route_retry_still_finds_no_road_network(client, auth_headers):
    """The widened retry bbox can itself come back with zero roads (e.g. a
    genuinely remote area) — must still surface the "no road network" error,
    not crash or hang, even on the retry path specifically."""
    def fetch_road_graph_side_effect(s, w, n, e):
        if (n - s) > 0.01:
            return build_graph({"elements": []})
        return build_graph(_RETRY_DISCONNECTED_OSM)

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routers.routing.fetch_road_graph", side_effect=fetch_road_graph_side_effect),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": _RETRY_START, "end": _RETRY_END,
                "datetime": "2026-05-24T14:00:00", "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 400
    assert "No road network found" in resp.json()["detail"]


def test_optimized_route_endpoint_no_path_found(client, auth_headers, caplog):
    """A production "No path found" (e.g. a route needing to cross a river/
    canal the search bbox didn't reach) used to be a bare 400 with no way to
    tell "genuinely disconnected" apart from any other cause — this must now
    log enough to diagnose it without waiting to catch it live again."""
    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", return_value=_DISCONNECTED_OSM),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        with caplog.at_level("WARNING"):
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
    assert any("no path found" in r.message.lower() for r in caplog.records)
    assert any("same_component=False" in r.message for r in caplog.records)


def test_optimized_route_endpoint_needs_wide_bbox_for_sideways_detour(client, auth_headers):
    """Reproduces a real production failure: a ~1.1km north-south route whose
    only connecting path jogs ~150m sideways (e.g. to reach a bridge/crossing).
    A fixed 100m pad excludes the connecting node entirely, splitting the
    route into two disconnected one-edge stubs and returning "No path found"
    even though a real walking path exists. route_bbox_padding_m scales the
    pad with distance so the real end-to-end request (not a mocked graph)
    actually finds it — a mocked fetch_osm_road_network that ignores its bbox
    args, like the other endpoint tests here use, would never catch this."""
    start = (40.000, -74.000)
    end = (40.010, -74.000)
    detour = (40.005, -73.998241)  # ~150m east of the direct line

    full_osm = {
        "elements": [
            {"type": "node", "id": 1, "lat": start[0], "lon": start[1]},
            {"type": "node", "id": 2, "lat": detour[0], "lon": detour[1]},
            {"type": "node", "id": 3, "lat": end[0], "lon": end[1]},
            {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
            {"type": "way", "id": 101, "nodes": [2, 3], "tags": {"highway": "residential"}},
        ]
    }

    def fake_fetch(s, w, n, e):
        elements = [
            el for el in full_osm["elements"]
            if el["type"] != "node" or (s <= el["lat"] <= n and w <= el["lon"] <= e)
        ]
        kept_ids = {el["id"] for el in elements if el["type"] == "node"}
        for el in full_osm["elements"]:
            if el["type"] == "way" and all(nid in kept_ids for nid in el["nodes"]):
                elements.append(el)
        return {"elements": elements}

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", side_effect=fake_fetch),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
    ):
        resp = client.post(
            "/sun/optimized-route",
            json={
                "start": list(start),
                "end": list(end),
                "datetime": "2026-05-24T14:00:00",
                "preference": "sun",
            },
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert len(resp.json()["waypoints"]) >= 2


_DETOUR_SHADE_OSM = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.000, "lon": -74.000},
        {"type": "node", "id": 2, "lat": 40.010, "lon": -74.000},
        {"type": "node", "id": 3, "lat": 40.005, "lon": -73.9965},  # shaded detour node
        {"type": "way", "id": 100, "nodes": [1, 2], "tags": {"highway": "residential"}},
        {"type": "way", "id": 101, "nodes": [1, 3], "tags": {"highway": "residential"}},
        {"type": "way", "id": 102, "nodes": [3, 2], "tags": {"highway": "residential"}},
    ]
}


def test_optimized_route_higher_max_detour_widens_search_for_shade(client, auth_headers):
    """Regression test: a user reported that raising their max-detour
    setting to 100% for a shade route changed nothing. Root cause:
    pref_max_detour only ever decided whether to *accept* a path already
    found over the plain-distance one — route_bbox_padding_m (the search
    box itself) didn't factor it in at all, so a shaded street just outside
    that fixed-size box could never be found no matter how much extra
    walking the user said they'd accept. Must run the real endpoint
    end-to-end (real graph build via a bbox-filtering fetch, real Dijkstra)
    — a mocked fetch_osm_road_network that ignores its bbox args, like most
    other endpoint tests here use, would never catch this."""

    def fake_fetch(s, w, n, e):
        elements = [
            el for el in _DETOUR_SHADE_OSM["elements"]
            if el["type"] != "node" or (s <= el["lat"] <= n and w <= el["lon"] <= e)
        ]
        kept_ids = {el["id"] for el in elements if el["type"] == "node"}
        for el in _DETOUR_SHADE_OSM["elements"]:
            if el["type"] == "way" and all(nid in kept_ids for nid in el["nodes"]):
                elements.append(el)
        return {"elements": elements}

    def fake_shaded(lat, lng, polygons, index, sun_alt):
        # Direct-path edge midpoint sits at lng=-74.000 (unshaded); detour
        # edges' midpoints sit at lng=-73.99825 (shaded).
        return lng > -73.999

    body = {
        "start": [40.000, -74.000],
        "end": [40.010, -74.000],
        "datetime": "2026-05-24T14:00:00",
        "preference": "shade",
    }

    with (
        patch("src.routers.routing.get_sun_position", return_value=(45.0, 180.0)),
        patch("src.routing.fetch_osm_road_network", side_effect=fake_fetch),
        patch("src.routers.routing._fetch_buildings_for_bbox", return_value=[]),
        patch("src.routing.is_point_shaded_by_index", side_effect=fake_shaded),
    ):
        assert client.patch("/users/me", json={"pref_max_detour": 10}, headers=auth_headers).status_code == 200
        low_resp = client.post("/sun/optimized-route", json=body, headers=auth_headers)

        assert client.patch("/users/me", json={"pref_max_detour": 100}, headers=auth_headers).status_code == 200
        high_resp = client.post("/sun/optimized-route", json=body, headers=auth_headers)

    assert low_resp.status_code == 200
    assert high_resp.status_code == 200

    low_lngs = [pt[1] for pt in low_resp.json()["waypoints"]]
    high_lngs = [pt[1] for pt in high_resp.json()["waypoints"]]

    # At 10% detour, the shaded detour node sits entirely outside the
    # search bbox, so the only path ever found is the direct (unshaded) one.
    assert max(low_lngs) == pytest.approx(-74.000, abs=1e-4)
    # At 100% detour, the wider search bbox includes the shaded detour
    # node, and shade preference actually routes through it.
    assert max(high_lngs) == pytest.approx(-73.9965, abs=1e-4)


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
