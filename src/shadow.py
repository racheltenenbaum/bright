from math import radians, tan, sin, cos, degrees, atan2
from shapely.geometry import Polygon, Point

EARTH_RADIUS_M = 6_371_000.0


def _offset_point(lat: float, lng: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Move a point by distance_m in bearing_deg direction. Returns (lat, lng).
    Small-angle approximation — accurate to <1m error for distances under 500m.
    """
    bearing = radians(bearing_deg)
    lat_rad = radians(lat)
    dlat = distance_m * cos(bearing) / EARTH_RADIUS_M
    dlng = distance_m * sin(bearing) / (EARTH_RADIUS_M * cos(lat_rad))
    return lat + degrees(dlat), lng + degrees(dlng)


def cast_shadow_polygon(
    footprint_coords: list[list[float]],
    height_m: float,
    sun_altitude_deg: float,
    sun_azimuth_deg: float,
) -> Polygon | None:
    """
    Returns a shapely Polygon representing the shadow cast by a building,
    or None if the sun is below the horizon or almost directly overhead.
    footprint_coords: [[lat, lng], ...]
    """
    if sun_altitude_deg <= 0 or sun_altitude_deg >= 88:
        return None

    shadow_length = height_m / tan(radians(sun_altitude_deg))
    shadow_bearing = (sun_azimuth_deg + 180) % 360

    all_points = []
    for coord in footprint_coords:
        lat, lng = coord[0], coord[1]
        all_points.append((lat, lng))
        tip_lat, tip_lng = _offset_point(lat, lng, shadow_bearing, shadow_length)
        all_points.append((tip_lat, tip_lng))

    if len(all_points) < 3:
        return None

    return Polygon(all_points).convex_hull


def is_point_shaded(
    lat: float,
    lng: float,
    buildings: list[dict],
    sun_altitude: float,
    sun_azimuth: float,
    point_elevation: float = 0.0,
) -> bool:
    """
    Returns True if the point at (lat, lng) falls inside any building's shadow.
    buildings: [{"footprint": [[lat,lng],...], "height": float, "base_elevation": float}, ...]
    """
    if sun_altitude <= 0:
        return True

    # 8m buffer in degrees (~0.000072°) so that street-centreline route points
    # register as shaded when they run alongside a building's shadow zone.
    BUFFER_DEG = 8 / 111_000

    pt = Point(lat, lng)
    for building in buildings:
        effective_height = building["height"] + building.get("base_elevation", 0.0) - point_elevation
        if effective_height <= 0:
            continue
        poly = cast_shadow_polygon(building["footprint"], effective_height, sun_altitude, sun_azimuth)
        if poly is not None and poly.buffer(BUFFER_DEG).contains(pt):
            return True
    return False


def _bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Forward bearing in degrees from point 1 to point 2."""
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlng = lng2 - lng1
    x = sin(dlng) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlng)
    return degrees(atan2(x, y)) % 360


def which_side_sunny(
    lat1: float, lng1: float,
    lat2: float, lng2: float,
    buildings: list[dict],
    sun_altitude: float,
    sun_azimuth: float,
    elevation: float = 0.0,
) -> str:
    """
    Returns 'left', 'right', 'both', or 'neither' — which sidewalk is in sun
    for the segment running from (lat1,lng1) to (lat2,lng2).
    Left/right are relative to the direction of travel.
    """
    if sun_altitude <= 0:
        return "neither"

    bearing = _bearing(lat1, lng1, lat2, lng2)
    mid_lat = (lat1 + lat2) / 2
    mid_lng = (lng1 + lng2) / 2

    left_lat, left_lng = _offset_point(mid_lat, mid_lng, (bearing - 90) % 360, 4.0)
    right_lat, right_lng = _offset_point(mid_lat, mid_lng, (bearing + 90) % 360, 4.0)

    left_shaded = is_point_shaded(left_lat, left_lng, buildings, sun_altitude, sun_azimuth, elevation)
    right_shaded = is_point_shaded(right_lat, right_lng, buildings, sun_altitude, sun_azimuth, elevation)

    if not left_shaded and not right_shaded:
        return "both"
    if left_shaded and right_shaded:
        return "neither"
    return "right" if left_shaded else "left"


def extract_buildings_from_overpass(overpass_data: dict) -> list[dict]:
    """
    Parse Overpass API JSON response into a list of building dicts.
    Returns [{"footprint": [[lat,lng],...], "height": float}, ...]
    """
    elements = overpass_data.get("elements", [])

    nodes: dict[int, tuple[float, float]] = {}
    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])

    buildings = []
    for el in elements:
        if el["type"] != "way":
            continue
        tags = el.get("tags", {})
        if "building" not in tags:
            continue

        footprint = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
        if len(footprint) < 3:
            continue

        height = _parse_height(tags)
        buildings.append({"footprint": footprint, "height": height})

    return buildings


def _parse_height(tags: dict) -> float:
    for key in ("height", "building:height"):
        val = tags.get(key)
        if val:
            try:
                return float(str(val).replace("m", "").strip())
            except ValueError:
                pass
    levels = tags.get("building:levels")
    if levels:
        try:
            return float(levels) * 3.0
        except ValueError:
            pass
    return 10.0
