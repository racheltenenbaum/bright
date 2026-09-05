import json
import logging
import math
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import networkx as nx
import requests

from src.database import SessionLocal
from src.models import OsmRoad
from src.regions import region_for_bbox
from src.shadow import (
    is_point_shaded,
    is_point_shaded_by_polygons,
    is_point_shaded_by_index,
    build_shadow_polygon_index,
    precompute_shadow_polygons,
)

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]
SUN_PENALTY = 1.5
# Shade routes structurally need a bigger detour than sun routes: at any given
# moment most street edges are unshaded, so avoiding them (shade) requires
# deviating much further than avoiding the shaded minority (sun). Without this,
# shade paths routinely blow the same flat detour cap sun paths comfortably
# clear, and silently collapse to the plain distance path.
SHADE_DETOUR_MULTIPLIER = 2.5
EXCLUDED_HIGHWAY_TYPES = {"motorway", "trunk", "motorway_link", "trunk_link"}
# highway=service covers real minor streets (needed for pedestrian routing
# where no separate sidewalk data exists) but also driveways, parking-lot
# access lanes, and drive-throughs — car maneuvering areas through private
# lots, not real through-routes. Including them let the router find
# unrealistic loopy "shortcuts" criss-crossing parking lots, especially in
# commercial corridors (confirmed: 73% of service ways near a real reported
# bad route in East Hollywood, LA were exactly these sub-types).
EXCLUDED_SERVICE_SUBTYPES = {"driveway", "parking_aisle", "drive-through"}

EARTH_RADIUS_M = 6_371_000.0

# L1: in-memory cache
_road_cache: dict[str, dict] = {}

# L2: SQLite cache (shared DB with building cache)
_CACHE_DB = os.path.join(os.path.dirname(__file__), "../overpass_cache.db")
_SQLITE_LOCK = threading.Lock()


def _init_road_db():
    with _SQLITE_LOCK:
        conn = sqlite3.connect(_CACHE_DB)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS road_cache "
            "(bbox_key TEXT PRIMARY KEY, roads_json TEXT)"
        )
        conn.commit()
        conn.close()


_init_road_db()


def _road_bbox_key(s: float, w: float, n: float, e: float) -> str:
    return f"road:{round(s,3)},{round(w,3)},{round(n,3)},{round(e,3)}"


def _road_sqlite_get(key: str) -> dict | None:
    try:
        conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
        row = conn.execute(
            "SELECT roads_json FROM road_cache WHERE bbox_key=?", (key,)
        ).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def _road_sqlite_set(key: str, data: dict) -> None:
    try:
        with _SQLITE_LOCK:
            conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
            conn.execute(
                "INSERT OR REPLACE INTO road_cache VALUES (?, ?)",
                (key, json.dumps(data)),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


ROUTE_BBOX_MIN_PADDING_M = 100.0
ROUTE_BBOX_MAX_PADDING_M = 800.0
ROUTE_BBOX_PADDING_FRACTION = 0.2


def route_bbox_padding_m(straight_line_m: float) -> float:
    """How far to pad a route's start/end bounding box when fetching roads
    and buildings. A fixed 100m pad works for short routes, but a real
    walking path often has to jog sideways to reach a bridge or avoid a
    one-way street — for a multi-km route that detour can be hundreds of
    meters wide, and a too-narrow box then has no road connecting start to
    end at all (start and end resolve to nodes in disconnected components).
    Padding scales with the route's straight-line distance instead of
    staying fixed, clamped so short routes still get a sane minimum and
    very long routes don't balloon the fetched area unboundedly.
    """
    return min(
        ROUTE_BBOX_MAX_PADDING_M,
        max(ROUTE_BBOX_MIN_PADDING_M, straight_line_m * ROUTE_BBOX_PADDING_FRACTION),
    )


def _query_overpass_roads(url: str, query: str, timeout: int | tuple[int, int]) -> dict | None:
    try:
        resp = requests.post(url, data=query, headers={"User-Agent": "bright-app/1.0"}, timeout=timeout)
    except Exception as exc:
        logger.warning("Overpass road request to %s failed: %r", url, exc)
        return None
    if resp.status_code == 200 and resp.json().get("elements") is not None:
        return resp.json()
    logger.warning(
        "Overpass road request to %s returned status %s: %s",
        url, resp.status_code, resp.text[:300],
    )
    return None


def fetch_osm_road_network(s: float, w: float, n: float, e: float) -> dict:
    key = _road_bbox_key(s, w, n, e)

    if key in _road_cache:
        return _road_cache[key]

    cached = _road_sqlite_get(key)
    if cached is not None:
        _road_cache[key] = cached
        return cached

    query = (
        f'[out:json][timeout:45][maxsize:8388608];'
        f'(way["highway"~"^(footway|path|pedestrian|living_street|residential|'
        f'service|unclassified|tertiary|secondary|primary|cycleway|steps|track)$"]'
        f'({s},{w},{n},{e}););out body;>;out skel qt;'
    )

    # Mirrors are raced concurrently, not tried one at a time — a dense urban
    # area can make a single mirror take the full timeout, and retrying the
    # rest sequentially after that would multiply the total wait.
    # timeout=(connect, read): a dead/unreachable mirror should fail fast
    # rather than burning the whole budget just trying to open a connection;
    # a mirror that connects but is genuinely slow for a dense area still
    # gets a fair amount of time to actually respond.
    executor = ThreadPoolExecutor(max_workers=len(OVERPASS_URLS))
    try:
        futures = [executor.submit(_query_overpass_roads, url, query, (5, 45)) for url in OVERPASS_URLS]
        for future in as_completed(futures):
            data = future.result()
            if data is not None:
                _road_cache[key] = data
                _road_sqlite_set(key, data)
                return data
        return {"elements": []}
    finally:
        executor.shutdown(wait=False)


def _fetch_roads_from_db(region: str, s: float, w: float, n: float, e: float) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(OsmRoad).filter(
            OsmRoad.region == region,
            OsmRoad.min_lat <= n,
            OsmRoad.max_lat >= s,
            OsmRoad.min_lng <= e,
            OsmRoad.max_lng >= w,
        ).all()
        return [
            {
                "from_lat": row.from_lat, "from_lng": row.from_lng,
                "to_lat": row.to_lat, "to_lng": row.to_lng,
                "distance_m": row.distance_m, "oneway": row.oneway,
            }
            for row in rows
        ]
    finally:
        db.close()


def fetch_road_graph(s: float, w: float, n: float, e: float) -> nx.DiGraph:
    """Region-aware entry point: bulk-imported regions build the graph
    directly from local edges (no live Overpass call); everywhere else keeps
    the existing live-Overpass path unchanged.

    An empty local result is treated the same as "not imported yet" (see
    src.routers.shadow_analyze._fetch_buildings_for_bbox for the identical
    reasoning) and falls back to Overpass rather than silently returning an
    empty graph.
    """
    region = region_for_bbox(s, w, n, e)
    if region:
        edges = _fetch_roads_from_db(region, s, w, n, e)
        if edges:
            return build_graph_from_edges(edges)

    return build_graph(fetch_osm_road_network(s, w, n, e))


def build_graph_from_edges(edges: list[dict]) -> nx.DiGraph:
    """Build a routing graph directly from bulk-imported road edges, which
    are already split/deduplicated the same way build_graph() splits raw OSM
    ways — so no OSM node IDs exist to key nodes on. Coordinates themselves
    are used as node identity instead, which is safe here because imported
    edges share exact endpoint coordinates by construction.
    """
    g = nx.DiGraph()
    for edge in edges:
        u = (edge["from_lat"], edge["from_lng"])
        v = (edge["to_lat"], edge["to_lng"])
        mid_lat = (u[0] + v[0]) / 2
        mid_lng = (u[1] + v[1]) / 2
        edge_data = {
            "distance_m": edge["distance_m"],
            "mid_lat": mid_lat,
            "mid_lng": mid_lng,
            "weight": edge["distance_m"],
        }
        g.add_node(u, lat=u[0], lng=u[1])
        g.add_node(v, lat=v[0], lng=v[1])
        g.add_edge(u, v, **edge_data)
        if not edge["oneway"]:
            g.add_edge(v, u, **edge_data)
    return g


def build_graph(osm_data: dict) -> nx.DiGraph:
    elements = osm_data.get("elements", [])

    node_coords: dict[int, tuple[float, float]] = {}
    for el in elements:
        if el["type"] == "node":
            node_coords[el["id"]] = (el["lat"], el["lon"])

    g = nx.DiGraph()
    for node_id, (lat, lng) in node_coords.items():
        g.add_node(node_id, lat=lat, lng=lng)

    for el in elements:
        if el["type"] != "way":
            continue
        tags = el.get("tags", {})
        highway = tags.get("highway")
        if not highway or highway in EXCLUDED_HIGHWAY_TYPES:
            continue
        if highway == "service" and tags.get("service") in EXCLUDED_SERVICE_SUBTYPES:
            continue

        node_ids = [nid for nid in el.get("nodes", []) if nid in node_coords]
        is_oneway = tags.get("oneway") == "yes"

        for i in range(len(node_ids) - 1):
            u, v = node_ids[i], node_ids[i + 1]
            lat1, lng1 = node_coords[u]
            lat2, lng2 = node_coords[v]
            dist = _haversine_m(lat1, lng1, lat2, lng2)
            mid_lat = (lat1 + lat2) / 2
            mid_lng = (lng1 + lng2) / 2
            edge_data = {
                "distance_m": dist,
                "mid_lat": mid_lat,
                "mid_lng": mid_lng,
                "weight": dist,
            }
            g.add_edge(u, v, **edge_data)
            if not is_oneway:
                g.add_edge(v, u, **edge_data)

    return g


def nearest_node(graph: nx.DiGraph, lat: float, lng: float) -> int:
    return min(
        graph.nodes,
        key=lambda n: _haversine_m(lat, lng, graph.nodes[n]["lat"], graph.nodes[n]["lng"]),
    )


def compute_edge_shading(
    graph: nx.DiGraph,
    buildings: list,
    sun_altitude: float,
    sun_azimuth: float,
) -> None:
    """Tag each edge with data["shaded"]. Each building's shadow polygon is
    built once (not per edge — it doesn't depend on the point being tested),
    and bidirectional edge pairs share a midpoint so are checked only once.
    """
    if sun_altitude <= 0:
        for _, _, data in graph.edges(data=True):
            data["shaded"] = True
        return

    shadow_polygons = precompute_shadow_polygons(buildings, sun_altitude, sun_azimuth)
    shadow_index = build_shadow_polygon_index(shadow_polygons)
    shaded_cache: dict[tuple[float, float], bool] = {}
    for _, _, data in graph.edges(data=True):
        key = (data["mid_lat"], data["mid_lng"])
        if key not in shaded_cache:
            shaded_cache[key] = is_point_shaded_by_index(
                key[0], key[1], shadow_polygons, shadow_index, sun_altitude
            )
        data["shaded"] = shaded_cache[key]


def apply_preference_weights(graph: nx.DiGraph, preference: str, penalty: float) -> None:
    for _, _, data in graph.edges(data=True):
        wants_sunny = preference == "sun"
        unwanted = data["shaded"] if wants_sunny else not data["shaded"]
        data["weight"] = data["distance_m"] * (penalty if unwanted else 1.0)


def compute_edge_weights(
    graph: nx.DiGraph,
    buildings: list,
    sun_altitude: float,
    sun_azimuth: float,
    preference: str,
) -> None:
    if sun_altitude <= 0:
        for _, _, data in graph.edges(data=True):
            data["weight"] = data["distance_m"]
        return
    compute_edge_shading(graph, buildings, sun_altitude, sun_azimuth)
    apply_preference_weights(graph, preference, SUN_PENALTY)


def _path_length_m(graph: nx.DiGraph, path: list[int]) -> float:
    if len(path) < 2:
        return 0.0
    return sum(graph.edges[path[i], path[i + 1]]["distance_m"] for i in range(len(path) - 1))


def find_distance_path(graph: nx.DiGraph, start_node: int, end_node: int) -> list[int]:
    try:
        return nx.shortest_path(graph, start_node, end_node, weight="distance_m")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def find_optimized_path(graph: nx.DiGraph, start_node: int, end_node: int) -> list[int]:
    try:
        return nx.shortest_path(graph, start_node, end_node, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def nodes_to_coords(graph: nx.DiGraph, node_ids: list[int]) -> list[tuple[float, float]]:
    return [(graph.nodes[n]["lat"], graph.nodes[n]["lng"]) for n in node_ids]


def sample_waypoints(coords: list, n: int = 10) -> list:
    if len(coords) <= n:
        return coords
    step = (len(coords) - 1) / (n - 1)
    return [coords[round(i * step)] for i in range(n)]


def _latlng_to_xy_m(lat: float, lng: float, ref_lat: float) -> tuple[float, float]:
    """Local equirectangular projection to meters — accurate enough over the
    short spans a single route covers, and only used for the perpendicular-
    distance check below, not for real distance/routing math."""
    x = lng * math.cos(math.radians(ref_lat)) * 111_320
    y = lat * 111_320
    return x, y


def _perp_distance_m(pt: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    (x, y), (x1, y1), (x2, y2) = pt, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return math.hypot(x - proj_x, y - proj_y)


def simplify_path(coords: list[tuple[float, float]], tolerance_m: float = 8.0) -> list[tuple[float, float]]:
    """Douglas-Peucker simplification — drops a point only if it's within
    tolerance_m of the straight line between its neighbors, so any real turn
    beyond that tolerance survives. This is what actually fixes routes
    visually cutting across streets/looking artificially jagged: unlike
    sample_waypoints' blind index-based thinning (which could skip a real
    turn entirely and draw a straight line across a street), or showing
    every raw graph node (which renders every OSM shape point, including
    ones a few meters apart with no real turn between them), this keeps
    exactly the points that matter geometrically.

    8m (not a stricter 3m) because a real Vienna route was found to have
    near-continuous few-meter-scale wobble along nearly its entire length —
    typical OSM node-position noise / minor way-endpoint misalignment at
    intersections, not actual street curvature — that a 3m tolerance mostly
    preserved (117 raw points down to only 74). 8m removed the noise (down
    to 27 points) while still preserving every real intersection turn,
    which involves a much larger deviation than a few meters.
    """
    if len(coords) < 3:
        return coords

    ref_lat = coords[0][0]
    xy = [_latlng_to_xy_m(lat, lng, ref_lat) for lat, lng in coords]

    def rdp(indices: list[int]) -> list[int]:
        if len(indices) < 3:
            return indices
        start, end = indices[0], indices[-1]
        max_dist, max_idx = -1.0, None
        for i in indices[1:-1]:
            d = _perp_distance_m(xy[i], xy[start], xy[end])
            if d > max_dist:
                max_dist, max_idx = d, i
        if max_dist > tolerance_m:
            left = rdp([i for i in indices if i <= max_idx])
            right = rdp([i for i in indices if i >= max_idx])
            return left[:-1] + right
        return [start, end]

    kept = rdp(list(range(len(coords))))
    return [coords[i] for i in kept]
