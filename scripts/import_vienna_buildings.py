"""One-time (then periodic) import of Vienna's official building-body model
(Baukörpermodell, ogdwien:FMZKBKMOGD) into the local osm_buildings table.

This gives Vienna real per-building height (O_KOTE - HOEHE_DGM: rooftop
elevation minus ground elevation), ~400k buildings, near-complete city
coverage — versus OSM's height-tag coverage for Vienna, which is only ~12%.

The WFS has no reliable server-side paging for this feature count, so we
tile the city into small bbox queries instead (each well under any page-size
limit) and bulk-insert into our own bbox-indexed table.

Usage:
    # Validate a small area first — always do this before --full.
    python scripts/import_vienna_buildings.py --bbox 48.20,16.36,48.21,16.37

    # Same, but report counts without writing to the DB.
    python scripts/import_vienna_buildings.py --bbox 48.20,16.36,48.21,16.37 --dry-run

    # Full city import (run from repo root; takes a while — ~880 tiles).
    python scripts/import_vienna_buildings.py --full
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import SessionLocal
from src.models import OsmBuilding

WFS_URL = "https://data.wien.gv.at/daten/geo"
LAYER = "ogdwien:FMZKBKMOGD"
REGION = "vienna"
SOURCE = "vienna_wfs"

# Vienna's administrative extent (s, w, n, e) — must match REGION_BOUNDS["vienna"]
# in src/routers/shadow_analyze.py.
VIENNA_BBOX = (48.10, 16.18, 48.32, 16.58)
TILE_SIZE_DEG = 0.01


def fetch_tile(s: float, w: float, n: float, e: float) -> dict:
    # The plain bbox= param stopped working server-side at some point (it
    # started silently returning zero features, likely because the layer's
    # native CRS is EPSG:31256 and the server now requires the query CRS to
    # be stated explicitly). CQL_FILTER=BBOX(SHAPE,...,'EPSG:4326') is the
    # confirmed-working equivalent — verified against a known tile that
    # returns 2320 features. SHAPE is this layer's geometry column name
    # (from DescribeFeatureType); order is minLng,minLat,maxLng,maxLat.
    params = {
        "service": "WFS",
        "request": "GetFeature",
        "version": "1.1.0",
        "typeName": LAYER,
        "srsName": "EPSG:4326",
        "outputFormat": "json",
        "CQL_FILTER": f"BBOX(SHAPE,{w},{s},{e},{n},'EPSG:4326')",
    }
    resp = requests.get(WFS_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def feature_to_building(feature: dict) -> dict | None:
    props = feature["properties"]
    o_kote = props.get("O_KOTE")
    hoehe_dgm = props.get("HOEHE_DGM")
    if o_kote is None or hoehe_dgm is None:
        return None
    height = o_kote - hoehe_dgm
    if height <= 0:
        return None

    geom = feature.get("geometry")
    if not geom or geom.get("type") != "Polygon":
        return None
    # GeoJSON coordinates are [lng, lat] — our internal footprint convention
    # (matching extract_buildings_from_overpass) is [lat, lng].
    ring = geom["coordinates"][0]
    footprint = [[lat, lng] for lng, lat in ring]
    lats = [p[0] for p in footprint]
    lngs = [p[1] for p in footprint]

    return {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lng": min(lngs), "max_lng": max(lngs),
        "footprint": footprint,
        "height": height,
    }


def import_bbox(s: float, w: float, n: float, e: float, dry_run: bool = False) -> int:
    data = fetch_tile(s, w, n, e)
    features = data.get("features", [])
    buildings = [b for f in features if (b := feature_to_building(f)) is not None]
    print(f"tile ({s},{w},{n},{e}): {len(features)} features -> {len(buildings)} usable buildings")

    if dry_run or not buildings:
        return len(buildings)

    db = SessionLocal()
    try:
        for b in buildings:
            db.add(OsmBuilding(
                region=REGION, source=SOURCE,
                min_lat=b["min_lat"], max_lat=b["max_lat"],
                min_lng=b["min_lng"], max_lng=b["max_lng"],
                footprint=json.dumps(b["footprint"]),
                height=b["height"],
            ))
        db.commit()
    finally:
        db.close()
    return len(buildings)


def import_full_city() -> None:
    s0, w0, n0, e0 = VIENNA_BBOX
    total = 0
    lat = s0
    while lat < n0:
        lat_end = min(lat + TILE_SIZE_DEG, n0)
        lng = w0
        while lng < e0:
            lng_end = min(lng + TILE_SIZE_DEG, e0)
            total += import_bbox(lat, lng, lat_end, lng_end)
            lng = lng_end
            time.sleep(0.2)  # be polite to Vienna's WFS
        lat = lat_end
    print(f"\nTOTAL buildings imported: {total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", help="s,w,n,e — import just one area (validation)")
    parser.add_argument("--full", action="store_true", help="import all of Vienna, tiled")
    parser.add_argument("--dry-run", action="store_true", help="fetch and report counts only, no DB writes")
    args = parser.parse_args()

    if args.bbox:
        s, w, n, e = map(float, args.bbox.split(","))
        import_bbox(s, w, n, e, dry_run=args.dry_run)
    elif args.full:
        import_full_city()
    else:
        parser.error("specify --bbox s,w,n,e for a test area, or --full for the whole city")
