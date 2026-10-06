"""One-time (then yearly) import of Berlin's tree cadastre (Baumbestand)
into the local osm_buildings table as round tree-canopy footprints.

Source: GDI Berlin WFS `gdi.berlin.de/services/wfs/baumbestand`, licensed
dl-de/zero-2-0. Two layers:
  - street: baumbestand:strassenbaeume — ~435k street trees
  - park:   baumbestand:anlagenbaeume  — ~528k trees in parks/green spaces
Each tree is a surveyed point with crown diameter (kronedurch, m) and height
(baumhoehe, m) — far better than OSM's tree_row lines, which carry no
per-tree data at all (see import_tree_rows.py). Each becomes one
src.shadow.tree_to_canopy footprint with source="berlin_trees", so the
shadow-casting code needs no changes; missing crown/height values fall back
to the same estimates tree rows use.

Points come back in UTM 33 (EPSG:25833) and are projected here. The WFS's
BBOX filter is inclusive on every edge, so rows are re-filtered half-open
(s <= lat < n, w <= lng < e) — adjacent --bbox chunks never import the same
tree twice. Paging is sorted by gisid so pages are stable.

Usage:
    # Validate a small area first — always do this before larger chunks.
    python scripts/import_berlin_trees.py --layer street --bbox 52.52,13.40,52.53,13.42 --dry-run
    python scripts/import_berlin_trees.py --layer street --bbox 52.52,13.40,52.53,13.42

    # Then import chunk by chunk (check DB disk headroom between chunks).
    python scripts/import_berlin_trees.py --layer street --bbox 52.33,13.08,52.505,13.425

    # Or everything at once (only once headroom is confirmed).
    python scripts/import_berlin_trees.py --layer street --full
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

import requests
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.shadow import tree_to_canopy

REGION = "berlin"
SOURCE = "berlin_trees"
WFS_URL = "https://gdi.berlin.de/services/wfs/baumbestand"
LAYERS = {
    "street": "baumbestand:strassenbaeume",
    "park": "baumbestand:anlagenbaeume",
}
PAGE_SIZE = 10_000
BATCH_SIZE = 20_000

# ETRS89 / UTM zone 33N (EPSG:25833) -> WGS84. always_xy: (x, y) = (lng, lat).
TO_WGS84 = Transformer.from_crs(25833, 4326, always_xy=True)


def fetch_page(layer: str, bbox: tuple[float, float, float, float], start: int, count: int) -> dict:
    s, w, n, e = bbox
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": LAYERS[layer],
        "outputFormat": "application/json",
        "propertyName": "gisid,geom,kronedurch,baumhoehe",
        # CQL BBOX order is minLng,minLat,maxLng,maxLat — verified live
        # against a known Alexanderplatz bbox.
        "CQL_FILTER": f"BBOX(geom,{w},{s},{e},{n},'EPSG:4326')",
        "sortBy": "gisid",
        "startIndex": start,
        "count": count,
    }
    resp = requests.get(WFS_URL, params=params, timeout=300)
    resp.raise_for_status()
    return resp.json()


def feature_to_canopy(feature: dict, bbox: tuple[float, float, float, float]) -> dict | None:
    geom = feature.get("geometry")
    if not geom or not geom.get("coordinates"):
        return None
    x, y = geom["coordinates"][:2]
    lng, lat = TO_WGS84.transform(x, y)
    s, w, n, e = bbox
    if not (s <= lat < n and w <= lng < e):
        return None
    props = feature.get("properties") or {}
    canopy = tree_to_canopy(lat, lng, props.get("kronedurch"), props.get("baumhoehe"))
    lats = [p[0] for p in canopy["footprint"]]
    lngs = [p[1] for p in canopy["footprint"]]
    return {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lng": min(lngs), "max_lng": max(lngs),
        "footprint": canopy["footprint"],
        "height": canopy["height"],
    }


def iter_canopies(
    layer: str, bbox: tuple[float, float, float, float], page_size: int = PAGE_SIZE,
) -> Iterator[dict]:
    LAYERS[layer]  # fail fast on an unknown layer name
    start = 0
    while True:
        features = fetch_page(layer, bbox, start=start, count=page_size)["features"]
        for feature in features:
            row = feature_to_canopy(feature, bbox)
            if row is not None:
                yield row
        if len(features) < page_size:
            return
        start += page_size


def _flush(db, rows: list[dict]) -> None:
    from src.models import OsmBuilding

    db.bulk_insert_mappings(OsmBuilding, [
        {
            "region": REGION, "source": SOURCE,
            "min_lat": r["min_lat"], "max_lat": r["max_lat"],
            "min_lng": r["min_lng"], "max_lng": r["max_lng"],
            "footprint": json.dumps(r["footprint"]),
            "height": r["height"],
        }
        for r in rows
    ])
    db.commit()


def run_import(layer: str, bbox: tuple[float, float, float, float], dry_run: bool) -> int:
    from src.database import SessionLocal

    db = None if dry_run else SessionLocal()
    total = 0
    batch: list[dict] = []
    try:
        for row in iter_canopies(layer, bbox):
            batch.append(row)
            total += 1
            if len(batch) >= BATCH_SIZE:
                if db:
                    _flush(db, batch)
                batch = []
                print(f"  {total} trees so far")
        if batch and db:
            _flush(db, batch)
    finally:
        if db:
            db.close()

    print(f"\nTOTAL {layer} trees {'found (dry run)' if dry_run else 'imported'}: {total}")
    return total


if __name__ == "__main__":
    from src.regions import REGION_BOUNDS

    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", choices=sorted(LAYERS), required=True)
    parser.add_argument("--bbox", help="s,w,n,e — import only this chunk")
    parser.add_argument("--full", action="store_true", help="import all of Berlin")
    parser.add_argument("--dry-run", action="store_true", help="fetch + parse, report counts only, no DB writes")
    args = parser.parse_args()

    if args.bbox:
        bbox = tuple(float(v) for v in args.bbox.split(","))
    elif args.full:
        bbox = REGION_BOUNDS[REGION]
    else:
        parser.error("specify --bbox s,w,n,e for a chunk, or --full for the whole city")

    run_import(args.layer, bbox, args.dry_run)
