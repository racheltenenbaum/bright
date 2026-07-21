import json
import math
import os
import sqlite3
import threading

import networkx as nx
import requests

from src.shadow import is_point_shaded

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]
SUN_PENALTY = 1.5
EXCLUDED_HIGHWAY_TYPES = {"motorway", "trunk", "motorway_link", "trunk_link"}

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


def fetch_osm_road_network(s: float, w: float, n: float, e: float) -> dict:
    key = _road_bbox_key(s, w, n, e)

    if key in _road_cache:
        return _road_cache[key]

    cached = _road_sqlite_get(key)
    if cached is not None:
        _road_cache[key] = cached
        return cached

    query = (
        f'[out:json][timeout:25][maxsize:8388608];'
        f'(way["highway"~"^(footway|path|pedestrian|living_street|residential|'
        f'service|unclassified|tertiary|secondary|primary|cycleway|steps|track)$"]'
        f'({s},{w},{n},{e}););out body;>;out skel qt;'
    )
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(
                url,
                data=query,
                headers={"User-Agent": "bright-app/1.0"},
                timeout=30,
            )
            if resp.status_code == 200 and resp.json().get("elements") is not None:
                data = resp.json()
                _road_cache[key] = data
                _road_sqlite_set(key, data)
                return data
        except Exception:
            continue
    return {"elements": []}


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


def compute_edge_weights(
    graph: nx.DiGraph,
    buildings: list,
    sun_altitude: float,
    sun_azimuth: float,
    preference: str,
) -> None:
    for u, v, data in graph.edges(data=True):
        if sun_altitude <= 0:
            data["weight"] = data["distance_m"]
            continue
        shaded = is_point_shaded(data["mid_lat"], data["mid_lng"], buildings, sun_altitude, sun_azimuth)
        if preference == "sun":
            data["weight"] = data["distance_m"] * (SUN_PENALTY if shaded else 1.0)
        else:
            data["weight"] = data["distance_m"] * (SUN_PENALTY if not shaded else 1.0)


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
