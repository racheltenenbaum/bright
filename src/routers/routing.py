from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from src.auth import get_current_user
from src.limiter import limiter, RATE_LIMIT_SHADOW
from src.models import User
from src.routing import (
    SHADE_DETOUR_MULTIPLIER,
    _path_length_m,
    compute_edge_weights,
    fetch_road_graph,
    find_distance_path,
    find_optimized_path,
    nearest_node,
    nodes_to_coords,
)
from src.routers.shadow_analyze import _fetch_buildings_for_bbox, _route_bbox
from src.utils.astronomy import get_sun_position

router = APIRouter(prefix="/sun", tags=["sun"])


class OptimizedRouteRequest(BaseModel):
    start: list[float]   # [lat, lng]
    end: list[float]     # [lat, lng]
    datetime: str        # ISO string
    preference: str      # "sun" or "shade"

    @field_validator("datetime")
    @classmethod
    def valid_datetime(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("datetime must be a valid ISO 8601 string")
        return v

    @field_validator("preference")
    @classmethod
    def valid_preference(cls, v):
        if v not in ("sun", "shade"):
            raise ValueError("preference must be 'sun' or 'shade'")
        return v


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
    dt = datetime.fromisoformat(body.datetime)  # already validated by Pydantic
    date_str = dt.strftime("%Y-%m-%d")

    mid_lat = (body.start[0] + body.end[0]) / 2
    mid_lng = (body.start[1] + body.end[1]) / 2
    sun_altitude, sun_azimuth = get_sun_position(mid_lat, mid_lng)

    all_coords = [body.start, body.end]
    s, w, n, e = _route_bbox(all_coords, padding_m=100)

    # Fetch road network and buildings in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        road_future = pool.submit(fetch_road_graph, s, w, n, e)
        bldg_future = pool.submit(_fetch_buildings_for_bbox, s, w, n, e)
        graph = road_future.result()
        bldg_result = bldg_future.result() if sun_altitude > 0 else []
        buildings = bldg_result if bldg_result is not None else []

    if graph.number_of_nodes() == 0:
        raise HTTPException(status_code=400, detail="No road network found for this area")

    compute_edge_weights(graph, buildings, sun_altitude, sun_azimuth, body.preference)

    start_node = nearest_node(graph, body.start[0], body.start[1])
    end_node = nearest_node(graph, body.end[0], body.end[1])
    path_nodes = find_optimized_path(graph, start_node, end_node)

    if not path_nodes:
        raise HTTPException(status_code=400, detail="No path found between these locations")

    max_detour = current_user.pref_max_detour / 100
    if body.preference == "shade":
        max_detour *= SHADE_DETOUR_MULTIPLIER
    dist_path_nodes = find_distance_path(graph, start_node, end_node)
    if dist_path_nodes:
        sun_len = _path_length_m(graph, path_nodes)
        dist_len = _path_length_m(graph, dist_path_nodes)
        if dist_len > 0 and sun_len > dist_len * (1 + max_detour):
            path_nodes = dist_path_nodes

    # The full node-by-node path is returned rather than downsampled to a
    # fixed count — thinning to evenly-spaced indices was cutting straight
    # lines across curves and intersections whenever a real turn fell
    # between two sampled points, making the drawn route visibly cut across
    # the street. /sun/shadow-analyze already handles a full-resolution
    # coordinate list correctly (it does its own internal sampling for the
    # expensive shading computation, then fills every index via nearest-
    # neighbor), so nothing downstream needs the point count capped.
    waypoints = nodes_to_coords(graph, path_nodes)

    return OptimizedRouteResponse(
        waypoints=[list(c) for c in waypoints],
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
    )
