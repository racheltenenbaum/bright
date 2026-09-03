"""Bulk-imported-data region definitions, shared between the roads pipeline
(src/routing.py) and the buildings pipeline (src/routers/shadow_analyze.py).

A region here is just a geographic box — it does NOT mean "this region has
data for every data type." Vienna's buildings come from its own WFS, while
Vienna's roads (if/when imported) would come from bulk OSM, and a region can
have one without the other. Callers must treat an empty local-DB result as
"not actually imported yet" and fall back to live Overpass, not assume that
matching a region here means data exists.
"""

REGION_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "vienna": (48.10, 16.18, 48.32, 16.58),
    "nyc": (40.49, -74.26, 40.92, -73.68),
    "la": (33.70, -118.67, 34.34, -118.15),
}


def region_for_bbox(s: float, w: float, n: float, e: float) -> str | None:
    for region, (rs, rw, rn, re) in REGION_BOUNDS.items():
        if s >= rs and w >= rw and n <= rn and e <= re:
            return region
    return None
