from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.auth import get_current_user
from src.limiter import limiter, RATE_LIMIT_SHADOW
from src.models import User
from src.routing import (
    _path_length_m,
    build_graph,
    compute_edge_weights,
    fetch_osm_road_network,
    find_distance_path,
    find_optimized_path,
    nearest_node,
    nodes_to_coords,
    sample_waypoints,
)
from src.routers.shadow_analyze import _fetch_buildings_for_bbox, _route_bbox
from src.utils.astronomy import get_sun_position

router = APIRouter(prefix="/sun", tags=["sun"])


class OptimizedRouteRequest(BaseModel):
    start: list[float]        # [lat, lng]
    end: list[float]          # [lat, lng]
    datetime: str             # ISO string
    preference: str           # "sun" or "shade"
    max_detour: float = 0.30  # max fraction longer than shortest path (0.30 = 30%)


class OptimizedRouteResponse(BaseModel):
    waypoints: list[list[float]]
    sun_altitude: float
    sun_azimuth: float
    date: str


@router.post("/optimized-route", response_model=OptimizedRouteResponse)
@limiter.limit(RATE_LIMIT_SHADOW)
def optimized_route(
    request: Request,
    body: OptimizedRouteRequest,
    current_user: User = Depends(get_current_user),
):
    dt = datetime.fromisoformat(body.datetime)
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    mid_lat = (body.start[0] + body.end[0]) / 2
    mid_lng = (body.start[1] + body.end[1]) / 2

    all_coords = [body.start, body.end]
    s, w, n, e = _route_bbox(all_coords, padding_m=100)

    # Fetch sun position, road network, and buildings in parallel
    with ThreadPoolExecutor(max_workers=3) as pool:
        sun_future = pool.submit(get_sun_position, mid_lat, mid_lng, date_str, time_str)
        road_future = pool.submit(fetch_osm_road_network, s, w, n, e)
        bldg_future = pool.submit(_fetch_buildings_for_bbox, s, w, n, e)
        sun_altitude, sun_azimuth = sun_future.result()
        osm_data = road_future.result()
        buildings = bldg_future.result() if sun_altitude > 0 else []

    graph = build_graph(osm_data)
    if graph.number_of_nodes() == 0:
        raise HTTPException(status_code=400, detail="No road network found for this area")

    compute_edge_weights(graph, buildings, sun_altitude, sun_azimuth, body.preference)

    start_node = nearest_node(graph, body.start[0], body.start[1])
    end_node = nearest_node(graph, body.end[0], body.end[1])
    path_nodes = find_optimized_path(graph, start_node, end_node)

    if not path_nodes:
        raise HTTPException(status_code=400, detail="No path found between these locations")

    dist_path_nodes = find_distance_path(graph, start_node, end_node)
    if dist_path_nodes:
        sun_len = _path_length_m(graph, path_nodes)
        dist_len = _path_length_m(graph, dist_path_nodes)
        if dist_len > 0 and sun_len > dist_len * (1 + body.max_detour):
            path_nodes = dist_path_nodes

    coords = nodes_to_coords(graph, path_nodes)
    waypoints = sample_waypoints(coords, n=25)

    return OptimizedRouteResponse(
        waypoints=[list(c) for c in waypoints],
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
    )
