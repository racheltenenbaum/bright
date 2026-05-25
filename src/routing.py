import math
import os

import networkx as nx
import requests

from src.shadow import is_point_shaded

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SUN_PENALTY = 2.0
EXCLUDED_HIGHWAY_TYPES = {"motorway", "trunk", "motorway_link", "trunk_link"}

EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


def fetch_osm_road_network(s: float, w: float, n: float, e: float) -> dict:
    query = (
        f'[out:json][timeout:30];'
        f'(way["highway"]'
        f'["highway"!~"^(motorway|trunk|motorway_link|trunk_link)$"]'
        f'({s},{w},{n},{e}););out body;>;out skel qt;'
    )
    try:
        resp = requests.post(
            OVERPASS_URL,
            data=query,
            headers={"User-Agent": "bright-app/1.0"},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
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
