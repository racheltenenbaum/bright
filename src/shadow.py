from math import radians, tan, sin, cos, degrees, atan2, inf
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree

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

    pt = Point(lat, lng)
    for building in buildings:
        effective_height = building["height"] + building.get("base_elevation", 0.0) - point_elevation
        if effective_height <= 0:
            continue
        poly = cast_shadow_polygon(building["footprint"], effective_height, sun_altitude, sun_azimuth)
        if poly is not None and poly.contains(pt):
            return True
    return False


def precompute_shadow_polygons(
    buildings: list[dict],
    sun_altitude: float,
    sun_azimuth: float,
    point_elevation: float = 0.0,
) -> list[Polygon]:
    """Build each building's shadow polygon once. Unlike is_point_shaded, this
    depends only on building geometry and sun position, never on the query
    point, so it must not be recomputed per point when checking many points
    (e.g. every edge midpoint in a routing graph) against the same buildings.
    """
    if sun_altitude <= 0:
        return []
    polygons = []
    for building in buildings:
        effective_height = building["height"] + building.get("base_elevation", 0.0) - point_elevation
        if effective_height <= 0:
            continue
        poly = cast_shadow_polygon(building["footprint"], effective_height, sun_altitude, sun_azimuth)
        if poly is not None:
            polygons.append(poly)
    return polygons


def is_point_shaded_by_polygons(
    lat: float,
    lng: float,
    shadow_polygons: list[Polygon],
    sun_altitude: float,
) -> bool:
    """Like is_point_shaded, but against polygons already built by
    precompute_shadow_polygons — for checking many points against the same
    set of buildings without rebuilding each building's polygon every time.
    """
    if sun_altitude <= 0:
        return True
    pt = Point(lat, lng)
    return any(poly.contains(pt) for poly in shadow_polygons)


def build_shadow_polygon_index(shadow_polygons: list[Polygon]) -> STRtree | None:
    """Spatial index over precomputed shadow polygons. In dense areas with
    thousands of buildings, checking a point against every polygon linearly
    (is_point_shaded_by_polygons) becomes the dominant cost of a route
    calculation; the index narrows each check to only nearby candidates.
    """
    if not shadow_polygons:
        return None
    return STRtree(shadow_polygons)


def is_point_shaded_by_index(
    lat: float,
    lng: float,
    shadow_polygons: list[Polygon],
    index: STRtree | None,
    sun_altitude: float,
) -> bool:
    if sun_altitude <= 0:
        return True
    if index is None:
        return False
    pt = Point(lat, lng)
    return any(shadow_polygons[i].contains(pt) for i in index.query(pt))


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


def extract_roads_from_overpass(overpass_data: dict) -> list[dict]:
    """
    Parse Overpass API JSON response into a list of road segments.
    Returns [{"lat1": float, "lng1": float, "lat2": float, "lng2": float}, ...]
    Each consecutive node pair in a highway way forms one segment.
    """
    elements = overpass_data.get("elements", [])

    nodes: dict[int, tuple[float, float]] = {}
    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])

    segments = []
    for el in elements:
        if el["type"] != "way":
            continue
        if "highway" not in el.get("tags", {}):
            continue
        node_ids = [nid for nid in el.get("nodes", []) if nid in nodes]
        for i in range(len(node_ids) - 1):
            lat1, lng1 = nodes[node_ids[i]]
            lat2, lng2 = nodes[node_ids[i + 1]]
            segments.append({"lat1": lat1, "lng1": lng1, "lat2": lat2, "lng2": lng2})

    return segments


def _point_to_segment_dist_sq(
    plat: float, plng: float,
    lat1: float, lng1: float,
    lat2: float, lng2: float,
) -> float:
    """Squared approximate distance (in degrees²) from point P to segment AB."""
    cos_lat = cos(radians((lat1 + lat2) / 2))
    bx = (lng2 - lng1) * cos_lat
    by = lat2 - lat1
    px = (plng - lng1) * cos_lat
    py = plat - lat1
    ab_len_sq = bx * bx + by * by
    if ab_len_sq == 0:
        return px * px + py * py
    t = max(0.0, min(1.0, (px * bx + py * by) / ab_len_sq))
    rx = px - t * bx
    ry = py - t * by
    return rx * rx + ry * ry


def find_nearest_road_segment(
    plat: float, plng: float, segments: list[dict]
) -> dict | None:
    """Return the road segment closest to (plat, plng), or None if list is empty."""
    if not segments:
        return None
    return min(
        segments,
        key=lambda s: _point_to_segment_dist_sq(
            plat, plng, s["lat1"], s["lng1"], s["lat2"], s["lng2"]
        ),
    )


def _side_of_segment(
    plat: float, plng: float,
    lat1: float, lng1: float,
    lat2: float, lng2: float,
) -> str:
    """
    Return 'left' or 'right' for which side of segment A→B the point P is on.
    Uses a signed cross-product in approximate Cartesian coordinates.
    """
    cos_lat = cos(radians((lat1 + lat2) / 2))
    dx = (lng2 - lng1) * cos_lat   # A→B direction (x component)
    dy = lat2 - lat1                # A→B direction (y component)
    px = (plng - lng1) * cos_lat   # A→P (x)
    py = plat - lat1                # A→P (y)
    cross = dx * py - dy * px      # z-component of cross product
    return "left" if cross > 0 else "right"


def place_is_sunny(
    plat: float,
    plng: float,
    road_segments: list[dict],
    buildings: list[dict],
    sun_altitude: float,
    sun_azimuth: float,
) -> bool:
    """
    Return True if the place at (plat, plng) is on the sunny side of its nearest road.
    Falls back to is_point_shaded() when no road segments are available.
    """
    if sun_altitude <= 0:
        return False

    nearest = find_nearest_road_segment(plat, plng, road_segments)
    if nearest is None:
        return not is_point_shaded(plat, plng, buildings, sun_altitude, sun_azimuth)

    side = _side_of_segment(plat, plng, nearest["lat1"], nearest["lng1"], nearest["lat2"], nearest["lng2"])
    sunny_side = which_side_sunny(
        nearest["lat1"], nearest["lng1"],
        nearest["lat2"], nearest["lng2"],
        buildings, sun_altitude, sun_azimuth,
    )

    if sunny_side == "both":
        return True
    if sunny_side == "neither":
        return False
    return sunny_side == side


# OSM's natural=tree_row tags a line of trees (e.g. an avenue's street
# trees) with no per-tree height or canopy-width data — these are estimates
# for a mature street tree. Treating tree-lined streets as fully unshaded
# (the only option with no tree data at all) is a worse approximation than
# a rough canopy estimate for the streets that do have tree_row coverage.
TREE_CANOPY_WIDTH_M = 5.0
TREE_CANOPY_HEIGHT_M = 9.0


def tree_row_to_canopy_segments(line_coords: list[tuple[float, float]]) -> list[dict]:
    """Convert a tree-row line into small rectangular canopy footprints, one
    per line segment, each buffered to TREE_CANOPY_WIDTH_M and given
    TREE_CANOPY_HEIGHT_M — reusing the exact same {"footprint", "height"}
    shape as a building, so no other shadow-casting code needs to change.
    """
    segments = []
    half_width = TREE_CANOPY_WIDTH_M / 2
    for i in range(len(line_coords) - 1):
        lat1, lng1 = line_coords[i]
        lat2, lng2 = line_coords[i + 1]
        if (lat1, lng1) == (lat2, lng2):
            continue
        bearing = _bearing(lat1, lng1, lat2, lng2)
        perp = (bearing + 90) % 360
        p1a = _offset_point(lat1, lng1, perp, half_width)
        p1b = _offset_point(lat1, lng1, perp, -half_width)
        p2a = _offset_point(lat2, lng2, perp, half_width)
        p2b = _offset_point(lat2, lng2, perp, -half_width)
        footprint = [list(p1a), list(p2a), list(p2b), list(p1b)]
        segments.append({"footprint": footprint, "height": TREE_CANOPY_HEIGHT_M})
    return segments


def extract_buildings_from_overpass(overpass_data: dict) -> list[dict]:
    """
    Parse Overpass API JSON response into a list of building (and tree-row
    canopy) dicts. Returns [{"footprint": [[lat,lng],...], "height": float}, ...]
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

        if "building" in tags:
            footprint = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
            if len(footprint) < 3:
                continue
            height = _parse_height(tags)
            buildings.append({"footprint": footprint, "height": height})
        elif tags.get("natural") == "tree_row":
            line = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
            if len(line) < 2:
                continue
            buildings.extend(tree_row_to_canopy_segments(line))

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
