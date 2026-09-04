import json
import logging
import math
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.auth import get_current_user
from src.database import SessionLocal
from src.limiter import limiter, RATE_LIMIT_SHADOW
from src.models import OsmBuilding, User
from src.regions import REGION_BOUNDS, region_for_bbox as _region_for_bbox
from src.shadow import extract_buildings_from_overpass, is_point_shaded, which_side_sunny, _offset_point
from src.utils.astronomy import get_sun_position

logger = logging.getLogger(__name__)

RAY_DISTANCES_M: list[float] = [150.0, 400.0, 900.0, 2000.0, 4000.0]
FLAT_TERRAIN_THRESHOLD_M: float = 20.0
MAX_SUN_ALT_FOR_TERRAIN_DEG: float = 25.0

def _fetch_buildings_from_db(region: str, s: float, w: float, n: float, e: float) -> list:
    db = SessionLocal()
    try:
        rows = db.query(OsmBuilding).filter(
            OsmBuilding.region == region,
            OsmBuilding.min_lat <= n,
            OsmBuilding.max_lat >= s,
            OsmBuilding.min_lng <= e,
            OsmBuilding.max_lng >= w,
        ).all()
        return [{"footprint": json.loads(row.footprint), "height": row.height} for row in rows]
    finally:
        db.close()

router = APIRouter(prefix="/sun", tags=["sun"])

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]
GOOGLE_ELEVATION_URL = "https://maps.googleapis.com/maps/api/elevation/json"

# L1: in-memory cache (fast, lost on restart)
_overpass_cache: dict[str, list] = {}

# L1b: recent fetched bboxes, kept separately from the exact-match cache
# above so a query can be served by any bbox that fully contains it, not
# just an identical one. This matters because a single route search makes
# two independently-shaped building queries — /sun/optimized-route uses the
# start/end bbox, /sun/shadow-analyze uses the actual path's bbox — and the
# second is always a subset of the first (the routing graph itself can't
# contain nodes outside the first bbox), so without this the second call
# always re-hits live Overpass for no reason. Capped to bound memory since
# this never persists to SQLite or gets evicted otherwise.
_BBOX_CACHE_MAX_ENTRIES = 200
_overpass_bbox_cache: list[tuple[float, float, float, float, list]] = []


def _remember_bbox(s: float, w: float, n: float, e: float, buildings: list) -> None:
    _overpass_bbox_cache.append((s, w, n, e, buildings))
    if len(_overpass_bbox_cache) > _BBOX_CACHE_MAX_ENTRIES:
        del _overpass_bbox_cache[0]


def _find_containing_cached_bbox(s: float, w: float, n: float, e: float) -> list | None:
    for cs, cw, cn, ce, buildings in reversed(_overpass_bbox_cache):
        if cs <= s and cw <= w and cn >= n and ce >= e:
            return buildings
    return None

# L2: SQLite cache (persists across restarts)
_CACHE_DB = os.path.join(os.path.dirname(__file__), "../../overpass_cache.db")
_SQLITE_LOCK = threading.Lock()


def _init_db():
    with _SQLITE_LOCK:
        conn = sqlite3.connect(_CACHE_DB)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS building_cache "
            "(bbox_key TEXT PRIMARY KEY, buildings_json TEXT)"
        )
        conn.commit()
        conn.close()


_init_db()


def _sqlite_get(key: str) -> list | None:
    try:
        conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
        row = conn.execute(
            "SELECT buildings_json FROM building_cache WHERE bbox_key=?", (key,)
        ).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def _sqlite_set(key: str, buildings: list) -> None:
    try:
        with _SQLITE_LOCK:
            conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
            conn.execute(
                "INSERT OR REPLACE INTO building_cache VALUES (?, ?)",
                (key, json.dumps(buildings)),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass


class SegmentResult(BaseModel):
    index: int
    shaded: bool
    sunny_side: str | None = None  # "left", "right", "both", "neither"


class ShadowAnalyzeRequest(BaseModel):
    coordinates: list[list[float]]  # [[lat, lng], ...]
    datetime: str                   # ISO string e.g. "2026-05-14T15:30:00"


class ShadowAnalyzeResponse(BaseModel):
    sun_altitude: float
    sun_azimuth: float
    date: str
    segments: list[SegmentResult]
    shadow_available: bool = True


def _bbox_key(s: float, w: float, n: float, e: float) -> str:
    return f"{round(s,3)},{round(w,3)},{round(n,3)},{round(e,3)}"


def _query_overpass(url: str, query: str, timeout: int | tuple[int, int]) -> dict | None:
    try:
        resp = requests.post(url, data=query, headers={"User-Agent": "bright-app/1.0"}, timeout=timeout)
    except Exception as exc:
        logger.warning("Overpass building request to %s failed: %r", url, exc)
        return None
    if resp.status_code == 200 and resp.json().get("elements") is not None:
        return resp.json()
    logger.warning(
        "Overpass building request to %s returned status %s: %s",
        url, resp.status_code, resp.text[:300],
    )
    return None


def _fetch_buildings_for_bbox(s: float, w: float, n: float, e: float) -> list | None:
    """Return buildings list, or None if all API calls failed (vs [] for no buildings found)."""
    region = _region_for_bbox(s, w, n, e)
    if region:
        db_buildings = _fetch_buildings_from_db(region, s, w, n, e)
        # An empty result here is ambiguous: it could mean "this region has
        # no buildings in this bbox" (a park) or "this region is registered
        # but hasn't actually been imported yet." Falling back to live
        # Overpass in both cases is slightly wasteful in the first case but
        # avoids silently returning no shading data in the second.
        if db_buildings:
            return db_buildings

    key = _bbox_key(s, w, n, e)

    if key in _overpass_cache:
        return _overpass_cache[key]

    cached = _sqlite_get(key)
    if cached is not None:
        _overpass_cache[key] = cached
        return cached

    containing = _find_containing_cached_bbox(s, w, n, e)
    if containing is not None:
        return containing

    # natural=tree_row alongside building — extract_buildings_from_overpass
    # converts tree rows into small shadow-casting canopy rectangles using
    # the same {"footprint","height"} shape as buildings.
    query = (
        f'[out:json][timeout:40];(way["building"]({s},{w},{n},{e});'
        f'way["natural"="tree_row"]({s},{w},{n},{e}););out body;>;out skel qt;'
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
        futures = [executor.submit(_query_overpass, url, query, (5, 40)) for url in OVERPASS_URLS]
        for future in as_completed(futures):
            data = future.result()
            if data is not None:
                buildings = extract_buildings_from_overpass(data)
                _overpass_cache[key] = buildings
                _sqlite_set(key, buildings)
                _remember_bbox(s, w, n, e, buildings)
                return buildings
        return None  # All API calls failed
    finally:
        executor.shutdown(wait=False)


def _route_bbox(coords: list[list[float]], padding_m: float = 50) -> tuple[float, float, float, float]:
    lats = [c[0] for c in coords]
    lngs = [c[1] for c in coords]
    delta = padding_m / 111_000
    return min(lats) - delta, min(lngs) - delta, max(lats) + delta, max(lngs) + delta


def _fetch_elevations(coords: list[tuple[float, float]]) -> list[float]:
    if not coords or not GOOGLE_MAPS_API_KEY:
        return [0.0] * len(coords)
    locations = "|".join(f"{lat},{lng}" for lat, lng in coords)
    try:
        resp = requests.get(
            GOOGLE_ELEVATION_URL,
            params={"locations": locations, "key": GOOGLE_MAPS_API_KEY},
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if len(results) == len(coords):
                return [r["elevation"] for r in results]
    except Exception:
        pass
    return [0.0] * len(coords)


def _sample_coords(coords: list[list[float]], target: int = 25) -> list[tuple[int, float, float]]:
    n = len(coords)
    if n <= target:
        return [(i, coords[i][0], coords[i][1]) for i in range(n)]
    step = n / target
    return [(round(i * step), coords[round(i * step)][0], coords[round(i * step)][1]) for i in range(target)]


def _nearest_shaded(shaded_map: dict[int, bool], i: int) -> bool:
    if not shaded_map:
        return False
    nearest = min(shaded_map.keys(), key=lambda k: abs(k - i))
    return shaded_map[nearest]


def _nearest_sunny_side(side_map: dict[int, str], i: int) -> str | None:
    if not side_map:
        return None
    nearest = min(side_map.keys(), key=lambda k: abs(k - i))
    return side_map[nearest]


@router.post("/shadow-analyze", response_model=ShadowAnalyzeResponse)
@limiter.limit(RATE_LIMIT_SHADOW)
def shadow_analyze(
    request: Request,
    body: ShadowAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    if len(body.coordinates) < 2:
        raise HTTPException(status_code=400, detail="At least 2 coordinates required")

    mid = body.coordinates[len(body.coordinates) // 2]
    dt = datetime.fromisoformat(body.datetime)
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    sun_altitude, sun_azimuth = get_sun_position(mid[0], mid[1])

    n = len(body.coordinates)

    if sun_altitude <= 0:
        return ShadowAnalyzeResponse(
            sun_altitude=sun_altitude,
            sun_azimuth=sun_azimuth,
            date=date_str,
            segments=[SegmentResult(index=i, shaded=True) for i in range(n)],
        )

    s, w, north, e = _route_bbox(body.coordinates)
    buildings_result = _fetch_buildings_for_bbox(s, w, north, e)
    shadow_available = buildings_result is not None
    buildings = buildings_result if buildings_result is not None else []

    samples = _sample_coords(body.coordinates, target=25)
    sample_coords_list = [(lat, lng) for _, lat, lng in samples]
    elevations = _fetch_elevations(sample_coords_list)

    shaded_map: dict[int, bool] = {}
    for (idx, lat, lng), elevation in zip(samples, elevations):
        shaded_map[idx] = is_point_shaded(lat, lng, buildings, sun_altitude, sun_azimuth, elevation)

    segments = [
        SegmentResult(
            index=i,
            shaded=shaded_map[i] if i in shaded_map else _nearest_shaded(shaded_map, i),
        )
        for i in range(n)
    ]

    return ShadowAnalyzeResponse(
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
        segments=segments,
        shadow_available=shadow_available,
    )


class ShadowBatchRequest(BaseModel):
    routes: list[list[list[float]]]  # list of routes, each [[lat, lng], ...]
    datetime: str


class ShadowBatchRouteResult(BaseModel):
    segments: list[SegmentResult]


class ShadowBatchResponse(BaseModel):
    sun_altitude: float
    sun_azimuth: float
    date: str
    time: str
    routes: list[ShadowBatchRouteResult]


def _is_terrain_flat(elevations: list[float], threshold_m: float = FLAT_TERRAIN_THRESHOLD_M) -> bool:
    if len(elevations) < 2:
        return True
    return max(elevations) - min(elevations) < threshold_m


def _terrain_ray_points(lat: float, lng: float, sun_azimuth: float, distances_m: list[float]) -> list[tuple[float, float]]:
    back_bearing = (sun_azimuth + 180) % 360
    return [_offset_point(lat, lng, back_bearing, d) for d in distances_m]


def _check_terrain_shadows(
    samples: list[tuple[int, float, float]],
    elevations: list[float],
    sun_altitude: float,
    sun_azimuth: float,
) -> dict[int, bool]:
    if _is_terrain_flat(elevations):
        return {idx: False for idx, _, _ in samples}

    all_ray_coords: list[tuple[float, float]] = []
    for _, lat, lng in samples:
        all_ray_coords.extend(_terrain_ray_points(lat, lng, sun_azimuth, RAY_DISTANCES_M))

    ray_elevs = _fetch_elevations(all_ray_coords)
    tan_alt = math.tan(math.radians(sun_altitude))
    n = len(RAY_DISTANCES_M)
    result: dict[int, bool] = {}
    for i, (idx, _, _) in enumerate(samples):
        point_elev = elevations[i]
        chunk = ray_elevs[i * n : (i + 1) * n]
        result[idx] = any(
            chunk[j] > point_elev + RAY_DISTANCES_M[j] * tan_alt
            for j in range(len(chunk))
        )
    return result


def _analyze_route(route: list[list[float]], buildings: list, sun_altitude: float, sun_azimuth: float) -> ShadowBatchRouteResult:
    samples = _sample_coords(route, target=25)
    elevations = _fetch_elevations([(lat, lng) for _, lat, lng in samples])

    terrain_shaded_map: dict[int, bool] = {}
    if sun_altitude <= MAX_SUN_ALT_FOR_TERRAIN_DEG:
        terrain_shaded_map = _check_terrain_shadows(samples, elevations, sun_altitude, sun_azimuth)

    shaded_map: dict[int, bool] = {}
    side_map: dict[int, str] = {}
    for (idx, lat, lng), elevation in zip(samples, elevations):
        building_shaded = is_point_shaded(lat, lng, buildings, sun_altitude, sun_azimuth, elevation)
        shaded_map[idx] = building_shaded or terrain_shaded_map.get(idx, False)
        next_idx = min(idx + 1, len(route) - 1)
        lat2, lng2 = route[next_idx][0], route[next_idx][1]
        side_map[idx] = which_side_sunny(lat, lng, lat2, lng2, buildings, sun_altitude, sun_azimuth, elevation)

    segments = [
        SegmentResult(
            index=i,
            shaded=shaded_map[i] if i in shaded_map else _nearest_shaded(shaded_map, i),
            sunny_side=side_map[i] if i in side_map else _nearest_sunny_side(side_map, i),
        )
        for i in range(len(route))
    ]
    return ShadowBatchRouteResult(segments=segments)


@router.post("/shadow-analyze-batch", response_model=ShadowBatchResponse)
@limiter.limit(RATE_LIMIT_SHADOW)
def shadow_analyze_batch(
    request: Request,
    body: ShadowBatchRequest,
    current_user: User = Depends(get_current_user),
):
    if not body.routes:
        raise HTTPException(status_code=400, detail="At least one route required")

    all_coords = [c for route in body.routes for c in route]
    mid = all_coords[len(all_coords) // 2]
    dt = datetime.fromisoformat(body.datetime)
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    s, w, north, e = _route_bbox(all_coords)

    sun_altitude, sun_azimuth = get_sun_position(mid[0], mid[1])
    buildings = _fetch_buildings_for_bbox(s, w, north, e)

    if sun_altitude <= 0:
        return ShadowBatchResponse(
            sun_altitude=sun_altitude,
            sun_azimuth=sun_azimuth,
            date=date_str,
            time=time_str,
            routes=[
                ShadowBatchRouteResult(
                    segments=[SegmentResult(index=i, shaded=True) for i in range(len(route))]
                )
                for route in body.routes
            ],
        )

    with ThreadPoolExecutor(max_workers=len(body.routes)) as pool:
        route_results = list(pool.map(
            lambda route: _analyze_route(route, buildings, sun_altitude, sun_azimuth),
            body.routes,
        ))

    return ShadowBatchResponse(
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
        time=time_str,
        routes=route_results,
    )
