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
# How much extra weight an "unwanted" edge (shaded, for sun preference;
# unshaded, for shade) gets in Dijkstra's cost function. 1.5 was too weak in
# practice: reproduced on a real ~830m LA route where a meaningfully more-
# shaded path existed (43% longer) but the optimizer never even tried it —
# at 1.5 it picked the exact same path as plain distance (0% detour
# attempted); raising the penalty step by step showed 2.0 barely moved the
# needle (+1%) and it took 3.0 to actually reach that shaded path, with no
# further change all the way up to 20.0 (the graph's best available shaded
# route is a fixed target, not something an ever-higher penalty keeps
# improving). 4.0 leaves comfortable margin above that observed threshold —
# the separate max-detour accept/reject check below is what actually bounds
# how long a resulting detour is allowed to be, so a higher penalty here
# doesn't risk absurd routes, only whether the optimizer bothers looking.
SUN_PENALTY = 4.0
# Shade routes structurally need a bigger detour than sun routes: at any given
# moment most street edges are unshaded, so avoiding them (shade) requires
# deviating much further than avoiding the shaded minority (sun). Without this,
# shade paths routinely blow the same flat detour cap sun paths comfortably
# clear, and silently collapse to the plain distance path.
SHADE_DETOUR_MULTIPLIER = 2.5
EXCLUDED_HIGHWAY_TYPES = {"motorway", "trunk", "motorway_link", "trunk_link"}
# highway=service covers real minor streets (needed for pedestrian routing
# where no separate sidewalk data exists) but also driveways, parking-lot
# access lanes, drive-throughs, and alleys — car/back-lot maneuvering paths,
# not real through-routes. Including them let the router find unrealistic
# loopy "shortcuts" criss-crossing parking lots (confirmed: 73% of service
# ways near a real reported bad route in East Hollywood, LA were exactly
# these sub-types) or zigzagging staircase paths ducking through back alleys
# between blocks instead of following the direct street (also East
# Hollywood — LA's grid has alleys running through the middle of blocks).
EXCLUDED_SERVICE_SUBTYPES = {"driveway", "parking_aisle", "drive-through", "alley"}

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
ROUTE_BBOX_MAX_PADDING_M = 2000.0
ROUTE_BBOX_PADDING_FRACTION = 0.2
# A user's max-detour setting (further multiplied by SHADE_DETOUR_MULTIPLIER
# for shade) only ever decides whether to *accept* a path that's already
# been found over the plain-distance one — it does nothing on its own to
# widen the area that gets searched for a shaded street to route through.
# Raising max detour to 100% changed nothing for a real reported case: the
# bbox stayed the same small size regardless, so if no shaded edge existed
# inside it, none could ever be found no matter how much extra walking the
# user said they'd accept. This weight converts a fraction of the extra
# distance the detour setting allows into extra search-box padding.
ROUTE_BBOX_DETOUR_WEIGHT = 0.5


def route_bbox_padding_m(straight_line_m: float, max_detour_fraction: float = 0.0) -> float:
    """How far to pad a route's start/end bounding box when fetching roads
    and buildings. A fixed 100m pad works for short routes, but a real
    walking path often has to jog sideways to reach a bridge or avoid a
    one-way street — for a multi-km route that detour can be hundreds of
    meters wide, and a too-narrow box then has no road connecting start to
    end at all (start and end resolve to nodes in disconnected components).
    Padding scales with the route's straight-line distance instead of
    staying fixed, clamped so short routes still get a sane minimum and
    very long routes don't balloon the fetched area unboundedly.

    max_detour_fraction (e.g. 0.3 for 30%, already including
    SHADE_DETOUR_MULTIPLIER when relevant) adds further padding
    proportional to the extra distance that detour allowance represents,
    so a higher detour tolerance actually searches a wider area instead of
    only changing whether an already-found path gets accepted.
    """
    detour_allowance_m = straight_line_m * max_detour_fraction
    return min(
        ROUTE_BBOX_MAX_PADDING_M,
        max(
            ROUTE_BBOX_MIN_PADDING_M,
            straight_line_m * ROUTE_BBOX_PADDING_FRACTION + detour_allowance_m * ROUTE_BBOX_DETOUR_WEIGHT,
        ),
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
        # See the identical hint on OsmBuilding's bbox query
        # (src/routers/shadow_analyze.py::_fetch_buildings_from_db) — same
        # optimizer behavior, same fix, confirmed via EXPLAIN (~2.7M rows
        # scanned for LA without this).
        rows = db.query(OsmRoad).with_hint(
            OsmRoad, "FORCE INDEX (ix_osm_roads_region_lat)", "mysql"
        ).filter(
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


# A real reported bad route ("556 Fashion Avenue", NYC) resolved to a 2-node
# dead-end stub with no connection to the actual street network a few meters
# away, so routing correctly-but-uselessly reported "No path found" from a
# start point that was never really reachable. Below this many nodes, a
# component is treated as a stray fragment rather than a real routable area.
MIN_COMPONENT_SIZE_FOR_NEAREST_NODE = 5


def nearest_node_candidates(graph: nx.DiGraph) -> set:
    """The node set nearest_node should search: restricted to nodes in a
    reasonably-sized connected component when the graph has one, so a tiny
    disconnected island right next to the real network is never preferred
    over a real (if very slightly further) point on it. Falls back to every
    node when none reaches the minimum size (e.g. a graph that's entirely
    small, as in tests).

    Split out from nearest_node so a caller that needs it for both a start
    and an end point (every real request does) computes this once — on a
    large graph, nx.connected_components(graph.to_undirected()) is a full
    O(V+E) traversal plus a full graph copy, and doing that twice per
    request measurably adds up (confirmed in production: ~3.4s combined for
    two nearest_node calls on a ~100k-node Vienna graph).
    """
    components = nx.connected_components(graph.to_undirected())
    big_components = [c for c in components if len(c) >= MIN_COMPONENT_SIZE_FOR_NEAREST_NODE]
    return set().union(*big_components) if big_components else set(graph.nodes)


def nearest_node(graph: nx.DiGraph, lat: float, lng: float, candidates: set | None = None) -> int:
    """Nearest node by straight-line distance among `candidates` (computed via
    nearest_node_candidates if not passed in — pass it explicitly when
    calling this more than once for the same graph, to avoid recomputing
    connected components each time)."""
    if candidates is None:
        candidates = nearest_node_candidates(graph)
    return min(
        candidates,
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
