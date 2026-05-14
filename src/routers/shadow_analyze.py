import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth import get_current_user
from src.models import User
from src.shadow import extract_buildings_from_overpass, is_point_shaded
from src.utils.astronomy import get_sun_position

router = APIRouter(prefix="/sun", tags=["sun"])

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_ELEVATION_URL = "https://maps.googleapis.com/maps/api/elevation/json"

_overpass_cache: dict[str, list] = {}


class SegmentResult(BaseModel):
    index: int
    shaded: bool


class ShadowAnalyzeRequest(BaseModel):
    coordinates: list[list[float]]  # [[lat, lng], ...]
    datetime: str                   # ISO string e.g. "2026-05-14T15:30:00"


class ShadowAnalyzeResponse(BaseModel):
    sun_altitude: float
    sun_azimuth: float
    date: str
    segments: list[SegmentResult]


def _bbox_key(s: float, w: float, n: float, e: float) -> str:
    return f"{round(s,3)},{round(w,3)},{round(n,3)},{round(e,3)}"


def _fetch_buildings_for_bbox(s: float, w: float, n: float, e: float) -> list:
    key = _bbox_key(s, w, n, e)
    if key in _overpass_cache:
        return _overpass_cache[key]

    query = f"[out:json][timeout:25];(way[\"building\"]({s},{w},{n},{e}););out body;>;out skel qt;"
    try:
        resp = requests.post(
            OVERPASS_URL,
            data=query,
            headers={"User-Agent": "bright-app/1.0"},
            timeout=25,
        )
        if resp.status_code == 200:
            buildings = extract_buildings_from_overpass(resp.json())
            _overpass_cache[key] = buildings
            return buildings
    except Exception:
        pass
    _overpass_cache[key] = []
    return []


def _route_bbox(coords: list[list[float]], padding_m: float = 150) -> tuple[float, float, float, float]:
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


@router.post("/shadow-analyze", response_model=ShadowAnalyzeResponse)
def shadow_analyze(
    body: ShadowAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    if len(body.coordinates) < 2:
        raise HTTPException(status_code=400, detail="At least 2 coordinates required")

    mid = body.coordinates[len(body.coordinates) // 2]
    dt = datetime.fromisoformat(body.datetime)
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    sun_altitude, sun_azimuth = get_sun_position(mid[0], mid[1], date_str, time_str)

    n = len(body.coordinates)

    if sun_altitude <= 0:
        return ShadowAnalyzeResponse(
            sun_altitude=sun_altitude,
            sun_azimuth=sun_azimuth,
            date=date_str,
            segments=[SegmentResult(index=i, shaded=True) for i in range(n)],
        )

    s, w, north, e = _route_bbox(body.coordinates)
    buildings = _fetch_buildings_for_bbox(s, w, north, e)

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
    routes: list[ShadowBatchRouteResult]


def _analyze_route(route: list[list[float]], buildings: list, sun_altitude: float, sun_azimuth: float) -> ShadowBatchRouteResult:
    samples = _sample_coords(route, target=25)
    elevations = _fetch_elevations([(lat, lng) for _, lat, lng in samples])
    shaded_map: dict[int, bool] = {}
    for (idx, lat, lng), elevation in zip(samples, elevations):
        shaded_map[idx] = is_point_shaded(lat, lng, buildings, sun_altitude, sun_azimuth, elevation)
    segments = [
        SegmentResult(
            index=i,
            shaded=shaded_map[i] if i in shaded_map else _nearest_shaded(shaded_map, i),
        )
        for i in range(len(route))
    ]
    return ShadowBatchRouteResult(segments=segments)


@router.post("/shadow-analyze-batch", response_model=ShadowBatchResponse)
def shadow_analyze_batch(
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

    sun_altitude, sun_azimuth = get_sun_position(mid[0], mid[1], date_str, time_str)

    if sun_altitude <= 0:
        return ShadowBatchResponse(
            sun_altitude=sun_altitude,
            sun_azimuth=sun_azimuth,
            date=date_str,
            routes=[
                ShadowBatchRouteResult(
                    segments=[SegmentResult(index=i, shaded=True) for i in range(len(route))]
                )
                for route in body.routes
            ],
        )

    s, w, north, e = _route_bbox(all_coords)
    buildings = _fetch_buildings_for_bbox(s, w, north, e)

    with ThreadPoolExecutor(max_workers=len(body.routes)) as pool:
        route_results = list(pool.map(
            lambda route: _analyze_route(route, buildings, sun_altitude, sun_azimuth),
            body.routes,
        ))

    return ShadowBatchResponse(
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
        routes=route_results,
    )
