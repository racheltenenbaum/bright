import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from src.auth import get_current_user
from src.limiter import limiter, RATE_LIMIT_SHADOW
from src.models import User
from src.routers.shadow_analyze import _fetch_buildings_for_bbox, _bbox_key, _route_bbox
from src.shadow import extract_roads_from_overpass, place_is_sunny, is_point_shaded
from src.utils.astronomy import get_sun_position

router = APIRouter(prefix="/places", tags=["places"])

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
GOOGLE_PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

VALID_TYPES = {"cafe", "restaurant", "bar", "park"}

# Place types that pollute results when searching for cafes/restaurants
_EXCLUDE_TYPES = {"gas_station", "convenience_store", "car_wash", "car_repair", "car_dealer"}

_COUNTRY_CURRENCY: dict[str, str] = {
    "GB": "£", "US": "$", "CA": "CA$", "AU": "A$", "NZ": "NZ$",
    "JP": "¥", "CN": "¥", "KR": "₩", "IN": "₹", "TH": "฿",
    "SG": "S$", "HK": "HK$", "TW": "NT$",
    "BR": "R$", "MX": "$", "AR": "$", "CL": "$", "CO": "$",
    "DE": "€", "FR": "€", "IT": "€", "ES": "€", "NL": "€",
    "PT": "€", "BE": "€", "AT": "€", "IE": "€", "FI": "€",
    "GR": "€", "LU": "€", "MT": "€", "CY": "€", "SK": "€",
    "SI": "€", "EE": "€", "LV": "€", "LT": "€",
    "SE": "kr", "NO": "kr", "DK": "kr",
    "CH": "Fr", "PL": "zł", "CZ": "Kč", "HU": "Ft",
    "RU": "₽", "TR": "₺", "ZA": "R",
    "AE": "د.إ", "SA": "﷼", "IL": "₪",
}

# In-memory L1 cache for road data
_road_cache: dict[str, list] = {}

_CACHE_DB = os.path.join(os.path.dirname(__file__), "../../overpass_cache.db")
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


def _road_sqlite_get(key: str) -> list | None:
    try:
        conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
        row = conn.execute(
            "SELECT roads_json FROM road_cache WHERE bbox_key=?", (key,)
        ).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def _road_sqlite_set(key: str, roads: list) -> None:
    try:
        with _SQLITE_LOCK:
            conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
            conn.execute(
                "INSERT OR REPLACE INTO road_cache VALUES (?, ?)",
                (key, json.dumps(roads)),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass


def _fetch_roads_for_bbox(s: float, w: float, n: float, e: float) -> list:
    key = _bbox_key(s, w, n, e)

    if key in _road_cache:
        return _road_cache[key]

    cached = _road_sqlite_get(key)
    if cached is not None:
        _road_cache[key] = cached
        return cached

    # Exclude motorways, paths, and service roads — keep walkable street-level roads
    query = (
        f"[out:json][timeout:25];"
        f"(way[\"highway\"][\"highway\"!~\"motorway|motorway_link|trunk|trunk_link"
        f"|footway|cycleway|service|track|path|steps\"]({s},{w},{n},{e}););"
        f"out body;>;out skel qt;"
    )
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(
                url,
                data=query,
                headers={"User-Agent": "bright-app/1.0"},
                timeout=25,
            )
            if resp.status_code == 200 and resp.json().get("elements") is not None:
                roads = extract_roads_from_overpass(resp.json())
                _road_cache[key] = roads
                _road_sqlite_set(key, roads)
                return roads
        except Exception:
            continue
    return []


def _fetch_places_from_google(lat: float, lng: float, radius: int, place_type: str, keyword: str | None = None) -> list:
    if not GOOGLE_MAPS_API_KEY:
        return []
    try:
        params = {
            "location": f"{lat},{lng}",
            "radius": radius,
            "type": place_type,
            "opennow": "true",
            "key": GOOGLE_MAPS_API_KEY,
        }
        if keyword:
            params["keyword"] = keyword
        resp = requests.get(GOOGLE_PLACES_URL, params=params, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            return [r for r in results if not _EXCLUDE_TYPES.intersection(r.get("types", []))]
    except Exception:
        pass
    return []




class PlaceSearchRequest(BaseModel):
    lat: float
    lng: float
    radius: int = 500
    preference: str
    types: list[str]
    keyword: str | None = None

    @field_validator("preference")
    @classmethod
    def validate_preference(cls, v):
        if v not in ("sun", "shade"):
            raise ValueError("preference must be 'sun' or 'shade'")
        return v

    @field_validator("types")
    @classmethod
    def validate_types(cls, v):
        if not v:
            raise ValueError("types must not be empty")
        invalid = set(v) - VALID_TYPES
        if invalid:
            raise ValueError(f"invalid types: {invalid}. Must be one of {VALID_TYPES}")
        return v


class PlaceReview(BaseModel):
    author_name: str
    rating: int | None
    text: str
    relative_time: str


class PlaceDetailsResponse(BaseModel):
    name: str
    rating: float | None
    user_ratings_total: int | None
    price_level: int | None
    formatted_phone_number: str | None
    website: str | None
    open_now: bool | None
    weekday_text: list[str]
    photo_references: list[str]
    currency_symbol: str = "$"
    postal_code: str | None = None
    reviews: list[PlaceReview]


class PlaceResult(BaseModel):
    place_id: str
    name: str
    lat: float
    lng: float
    address: str
    rating: float | None
    photo_reference: str | None
    type: str
    is_sunny: bool


class PlaceSearchResponse(BaseModel):
    places: list[PlaceResult]
    sun_altitude: float
    sun_azimuth: float


class PlaceSunCheckRequest(BaseModel):
    lat: float
    lng: float


class PlaceSunCheckResponse(BaseModel):
    is_sunny: bool
    sun_altitude: float


@router.post("/sun-check", response_model=PlaceSunCheckResponse)
@limiter.limit(RATE_LIMIT_SHADOW)
def check_place_sun(
    request: Request,
    body: PlaceSunCheckRequest,
    current_user: User = Depends(get_current_user),
):
    sun_altitude, sun_azimuth = get_sun_position(body.lat, body.lng)

    if sun_altitude <= 0:
        return PlaceSunCheckResponse(is_sunny=False, sun_altitude=sun_altitude)

    padding = 200 / 111_000
    buildings = _fetch_buildings_for_bbox(
        body.lat - padding, body.lng - padding,
        body.lat + padding, body.lng + padding,
    )
    is_sunny = place_is_sunny(body.lat, body.lng, [], buildings, sun_altitude, sun_azimuth)
    return PlaceSunCheckResponse(is_sunny=is_sunny, sun_altitude=sun_altitude)


@router.post("/search", response_model=PlaceSearchResponse)
@limiter.limit(RATE_LIMIT_SHADOW)
def search_places(
    request: Request,
    body: PlaceSearchRequest,
    current_user: User = Depends(get_current_user),
):
    sun_altitude, sun_azimuth = get_sun_position(body.lat, body.lng)

    is_nighttime = sun_altitude <= 0

    if not is_nighttime:
        padding = body.radius / 111_000
        s = body.lat - padding
        w = body.lng - padding
        n = body.lat + padding
        e = body.lng + padding
        buildings = _fetch_buildings_for_bbox(s, w, n, e)
    else:
        buildings = []

    utc_now = datetime.now(timezone.utc)
    local_hour = (utc_now.hour + body.lng / 15) % 24
    evening = local_hour >= 20

    # If bar is requested and it's evening, also fetch cafes and promote them to bar type
    types_to_fetch: list[tuple[str, str]] = [(t, t) for t in body.types]
    if "bar" in body.types and "cafe" not in body.types and evening:
        types_to_fetch.append(("cafe", "bar"))

    # Collect places from Google for each requested type; deduplicate by place_id
    seen: dict[str, str] = {}  # place_id → assigned type
    raw_places: list[tuple[dict, str]] = []  # (raw_place, assigned_type)
    for fetch_type, assigned_type in types_to_fetch:
        for raw in _fetch_places_from_google(body.lat, body.lng, body.radius, fetch_type, body.keyword):
            pid = raw.get("place_id", "")
            if pid and pid not in seen:
                seen[pid] = assigned_type
                raw_places.append((raw, assigned_type))

    # Filter out low-review venues (parks exempt)
    raw_places = [
        (raw, pt) for raw, pt in raw_places
        if pt == "park" or raw.get("user_ratings_total", 0) > 10
    ]

    want_sunny = body.preference == "sun"
    results: list[PlaceResult] = []
    for raw, place_type in raw_places:
        loc = raw["geometry"]["location"]
        plat = loc["lat"]
        plng = loc["lng"]
        if is_nighttime:
            is_sunny = False
        else:
            is_sunny = not is_point_shaded(plat, plng, buildings, sun_altitude, sun_azimuth)
            if not body.keyword and is_sunny != want_sunny:
                continue
        photos = raw.get("photos", [])
        photo_reference = photos[0].get("photo_reference") if photos else None
        results.append(PlaceResult(
            place_id=raw["place_id"],
            name=raw["name"],
            lat=plat,
            lng=plng,
            address=raw.get("vicinity", ""),
            rating=raw.get("rating"),
            photo_reference=photo_reference,
            type=place_type,
            is_sunny=is_sunny,
        ))

    return PlaceSearchResponse(
        places=results,
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
    )


@router.get("/{place_id}/details", response_model=PlaceDetailsResponse)
@limiter.limit(RATE_LIMIT_SHADOW)
def get_place_details(
    request: Request,
    place_id: str,
    current_user: User = Depends(get_current_user),
):
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=503, detail="Maps API not configured")

    fields = (
        "name,rating,user_ratings_total,price_level,"
        "formatted_phone_number,website,opening_hours,photos,reviews,address_components"
    )
    try:
        resp = requests.get(
            GOOGLE_PLACE_DETAILS_URL,
            params={"place_id": place_id, "fields": fields, "key": GOOGLE_MAPS_API_KEY},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Places API request failed")

        data = resp.json().get("result", {})
        hours = data.get("opening_hours", {})
        country_code = next(
            (c["short_name"] for c in data.get("address_components", [])
             if "country" in c.get("types", [])),
            "US",
        )
        postal_code = next(
            (c["short_name"] for c in data.get("address_components", [])
             if "postal_code" in c.get("types", [])),
            None,
        )

        return PlaceDetailsResponse(
            name=data.get("name", ""),
            rating=data.get("rating"),
            user_ratings_total=data.get("user_ratings_total"),
            price_level=data.get("price_level"),
            formatted_phone_number=data.get("formatted_phone_number"),
            website=data.get("website"),
            open_now=hours.get("open_now"),
            weekday_text=hours.get("weekday_text", []),
            photo_references=[p["photo_reference"] for p in data.get("photos", [])[:5]],
            currency_symbol=_COUNTRY_CURRENCY.get(country_code, "$"),
            postal_code=postal_code,
            reviews=[
                PlaceReview(
                    author_name=r.get("author_name", ""),
                    rating=r.get("rating"),
                    text=r.get("text", ""),
                    relative_time=r.get("relative_time_description", ""),
                )
                for r in data.get("reviews", [])[:5]
            ],
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Could not fetch place details")
