import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from src.auth import get_current_user_optional
from src.limiter import limiter, RATE_LIMIT_SHADOW
from src.models import User
from src.routing import (
    ROUTE_BBOX_MAX_PADDING_M,
    SHADE_DETOUR_MULTIPLIER,
    _haversine_m,
    _path_length_m,
    compute_edge_weights,
    describe_no_path_found,
    fetch_road_graph,
    find_distance_path,
    find_optimized_path,
    nearest_node,
    nearest_node_candidates,
    nodes_to_coords,
    route_bbox_padding_m,
    simplify_path,
)
from src.routers.shadow_analyze import _fetch_buildings_for_bbox, _route_bbox
from src.utils.astronomy import get_sun_position

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sun", tags=["sun"])


def _timed(fn, *args):
    """Runs fn(*args) and returns (result, elapsed_seconds) — used so the two
    functions raced in the road/buildings ThreadPoolExecutor each report their
    own wall time, rather than only the pool's combined (max of the two)
    duration."""
    start = time.perf_counter()
    result = fn(*args)
    return result, time.perf_counter() - start

# Matches User.pref_max_detour's own column default.
DEFAULT_MAX_DETOUR = 30


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


def _attempt_route(s, w, n, e, body, sun_altitude, sun_azimuth):
    """One fetch-graph-and-pathfind attempt for a given bbox. Split out from
    optimized_route so it can be retried with a wider bbox when start/end
    land in disconnected chunks of the first, narrower fetch (see the
    retry-on-disconnect logic below) — a real reported case: Heldenplatz's
    internal pedestrian paths came back as an isolated ~20-node island, not
    reachable from the surrounding street grid within the default bbox,
    even though it's obviously a real, well-connected central square.
    Returns a dict of everything the caller needs either to finish building
    a response or to log a rich diagnosis if even the retry fails.
    """
    timings = {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        road_future = pool.submit(_timed, fetch_road_graph, s, w, n, e)
        bldg_future = pool.submit(_timed, _fetch_buildings_for_bbox, s, w, n, e)
        graph, timings["road_graph_s"] = road_future.result()
        if sun_altitude > 0:
            bldg_result, timings["buildings_s"] = bldg_future.result()
        else:
            bldg_result, timings["buildings_s"] = [], None
        buildings = bldg_result if bldg_result is not None else []

    if graph.number_of_nodes() == 0:
        return {"graph": graph, "buildings": buildings, "path_nodes": None,
                "start_node": None, "end_node": None, "timings": timings, "empty_graph": True}

    edge_weights_start = time.perf_counter()
    compute_edge_weights(graph, buildings, sun_altitude, sun_azimuth, body.preference)
    timings["edge_weights_s"] = time.perf_counter() - edge_weights_start

    nearest_node_start = time.perf_counter()
    candidates = nearest_node_candidates(graph)
    start_node = nearest_node(graph, body.start[0], body.start[1], candidates=candidates)
    end_node = nearest_node(graph, body.end[0], body.end[1], candidates=candidates)
    timings["nearest_node_s"] = time.perf_counter() - nearest_node_start

    optimized_path_start = time.perf_counter()
    path_nodes = find_optimized_path(graph, start_node, end_node)
    timings["optimized_path_s"] = time.perf_counter() - optimized_path_start

    return {"graph": graph, "buildings": buildings, "path_nodes": path_nodes,
            "start_node": start_node, "end_node": end_node, "timings": timings, "empty_graph": False}


@router.post("/optimized-route", response_model=OptimizedRouteResponse)
@limiter.limit(RATE_LIMIT_SHADOW)
def optimized_route(
    request: Request,
    body: OptimizedRouteRequest,
    current_user: User | None = Depends(get_current_user_optional),
):
    request_start = time.perf_counter()

    dt = datetime.fromisoformat(body.datetime)  # already validated by Pydantic
    date_str = dt.strftime("%Y-%m-%d")

    mid_lat = (body.start[0] + body.end[0]) / 2
    mid_lng = (body.start[1] + body.end[1]) / 2
    sun_altitude, sun_azimuth = get_sun_position(mid_lat, mid_lng)

    # Routing works without an account — a logged-out user just gets the
    # same default detour tolerance a new account would start with
    # (User.pref_max_detour's own default), rather than being blocked.
    pref_max_detour = current_user.pref_max_detour if current_user else DEFAULT_MAX_DETOUR
    max_detour = pref_max_detour / 100
    if body.preference == "shade":
        max_detour *= SHADE_DETOUR_MULTIPLIER

    bbox_start = time.perf_counter()
    all_coords = [body.start, body.end]
    straight_line_m = _haversine_m(body.start[0], body.start[1], body.end[0], body.end[1])
    padding_m = route_bbox_padding_m(straight_line_m, max_detour)
    s, w, n, e = _route_bbox(all_coords, padding_m=padding_m)
    bbox_s = time.perf_counter() - bbox_start

    attempt = _attempt_route(s, w, n, e, body, sun_altitude, sun_azimuth)
    retried = False

    if attempt["empty_graph"]:
        raise HTTPException(status_code=400, detail="No road network found for this area")

    if not attempt["path_nodes"] and padding_m < ROUTE_BBOX_MAX_PADDING_M:
        # Start/end came back in disconnected chunks of the graph — before
        # giving up, retry once with the widest bbox this app ever uses, in
        # case the missing connector (e.g. a plaza's internal paths linking
        # to the surrounding street grid) just fell outside the narrower
        # search area. Widening can only ever help here, never hurt.
        logger.warning(
            "optimized_route retrying with max bbox padding after disconnected first attempt: "
            "preference=%s start=%s end=%s original_padding_m=%.0f",
            body.preference, body.start, body.end, padding_m,
        )
        s, w, n, e = _route_bbox(all_coords, padding_m=ROUTE_BBOX_MAX_PADDING_M)
        attempt = _attempt_route(s, w, n, e, body, sun_altitude, sun_azimuth)
        retried = True

        if attempt["empty_graph"]:
            raise HTTPException(status_code=400, detail="No road network found for this area")

    graph = attempt["graph"]
    buildings = attempt["buildings"]
    start_node = attempt["start_node"]
    end_node = attempt["end_node"]
    path_nodes = attempt["path_nodes"]
    road_graph_s = attempt["timings"]["road_graph_s"]
    buildings_s = attempt["timings"]["buildings_s"]
    edge_weights_s = attempt["timings"]["edge_weights_s"]
    nearest_node_s = attempt["timings"]["nearest_node_s"]
    optimized_path_s = attempt["timings"]["optimized_path_s"]

    if not path_nodes:
        diagnosis = describe_no_path_found(graph, start_node, end_node)
        logger.warning(
            "optimized_route no path found (retried=%s): preference=%s start=%s end=%s nodes=%d edges=%d "
            "num_components=%d component_sizes=%s start_component=%s end_component=%s same_component=%s",
            retried, body.preference, body.start, body.end, graph.number_of_nodes(), graph.number_of_edges(),
            diagnosis["num_components"], diagnosis["component_sizes"],
            diagnosis["start_component"], diagnosis["end_component"], diagnosis["same_component"],
        )
        raise HTTPException(status_code=400, detail="No path found between these locations")

    distance_path_start = time.perf_counter()
    dist_path_nodes = find_distance_path(graph, start_node, end_node)
    if dist_path_nodes:
        sun_len = _path_length_m(graph, path_nodes)
        dist_len = _path_length_m(graph, dist_path_nodes)
        if dist_len > 0 and sun_len > dist_len * (1 + max_detour):
            path_nodes = dist_path_nodes
    distance_path_s = time.perf_counter() - distance_path_start

    # Geometry-preserving simplification, not the fixed-count downsampling
    # this used to do — thinning to evenly-spaced indices could skip a real
    # turn entirely and draw a straight line cutting across the street.
    # simplify_path only drops a point when it's within a few meters of the
    # line between its neighbors, so every real turn survives while the many
    # near-duplicate OSM shape points along straight stretches collapse away
    # instead of rendering as visual noise. /sun/shadow-analyze still
    # handles whatever length list comes out of this correctly (its own
    # internal sampling for the shading computation, then nearest-neighbor
    # fill for every index).
    simplify_start = time.perf_counter()
    waypoints = simplify_path(nodes_to_coords(graph, path_nodes))
    simplify_s = time.perf_counter() - simplify_start

    logger.info(
        "optimized_route timing preference=%s distance_m=%.0f nodes=%d edges=%d retried=%s "
        "bbox=%.3fs road_graph=%.3fs buildings=%s edge_weights=%.3fs nearest_node=%.3fs "
        "optimized_path=%.3fs distance_path=%.3fs simplify=%.3fs total=%.3fs",
        body.preference,
        straight_line_m,
        graph.number_of_nodes(),
        graph.number_of_edges(),
        retried,
        bbox_s,
        road_graph_s,
        f"{buildings_s:.3f}s" if buildings_s is not None else "skipped(sun-below-horizon)",
        edge_weights_s,
        nearest_node_s,
        optimized_path_s,
        distance_path_s,
        simplify_s,
        time.perf_counter() - request_start,
    )

    return OptimizedRouteResponse(
        waypoints=[list(c) for c in waypoints],
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
    )
