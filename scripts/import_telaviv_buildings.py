"""One-time (then periodic) import of Tel Aviv's building model into the
local osm_buildings table.

Source: Tel Aviv Municipality's GIS server, layer "מבנים" (Buildings, id 513)
on the ArcGIS MapServer "IView2_Testing_Alon". Height is derived the same
way as Vienna's WFS import (roof elevation minus ground elevation) via the
gova_simplex_2019 field, which we verified equals max_height - min_height
exactly — see docs/DATA_SOURCES.md for the full provenance note, including
the caveat that this service is on a personal/test-labeled endpoint, not an
official catalog listing, and could change without notice.

Unlike Vienna's WFS (no server-side paging, hence tiling), this ArcGIS
service supports real pagination (resultOffset/resultRecordCount, max 2000
rows/page), so no manual bbox tiling is needed.

Usage:
    # Validate a small slice first — always do this before --full.
    python scripts/import_telaviv_buildings.py --limit 2000

    # Same, but report counts without writing to the DB.
    python scripts/import_telaviv_buildings.py --limit 2000 --dry-run

    # Full city import (run from repo root).
    python scripts/import_telaviv_buildings.py --full
"""
import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import SessionLocal
from src.models import OsmBuilding

QUERY_URL = "https://gisn.tel-aviv.gov.il/arcgis/rest/services/IView2_Testing_Alon/MapServer/513/query"
REGION = "telaviv"
SOURCE = "telaviv_gis"
PAGE_SIZE = 2000  # this service's maxRecordCount


def fetch_page(offset: int, page_size: int) -> dict:
    params = {
        "where": "1=1",
        "outFields": "gova_simplex_2019,min_height,max_height,ms_komot",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page_size,
    }
    resp = requests.get(QUERY_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def feature_to_building(feature: dict) -> dict | None:
    props = feature["properties"]
    # gova_simplex_2019 is the field name itself (verified against
    # max_height - min_height on live samples); fall back to computing it
    # directly if that field is ever null but the two elevations aren't.
    height = props.get("gova_simplex_2019")
    if height is None:
        min_h, max_h = props.get("min_height"), props.get("max_height")
        if min_h is None or max_h is None:
            return None
        height = max_h - min_h
    if height <= 0:
        return None

    geom = feature.get("geometry")
    if not geom or geom.get("type") != "Polygon":
        return None
    # GeoJSON coordinates are [lng, lat] — our internal footprint convention
    # is [lat, lng].
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


def run_import(limit: int | None, dry_run: bool) -> int:
    db = SessionLocal()
    total = 0
    offset = 0
    try:
        while True:
            page_size = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - total)
            if page_size <= 0:
                break
            data = fetch_page(offset, page_size)
            features = data.get("features", [])
            if not features:
                break

            buildings = [b for f in features if (b := feature_to_building(f)) is not None]
            print(f"offset {offset}: {len(features)} features -> {len(buildings)} usable buildings")

            if buildings and not dry_run:
                db.bulk_insert_mappings(OsmBuilding, [
                    {
                        "region": REGION, "source": SOURCE,
                        "min_lat": b["min_lat"], "max_lat": b["max_lat"],
                        "min_lng": b["min_lng"], "max_lng": b["max_lng"],
                        "footprint": json.dumps(b["footprint"]),
                        "height": b["height"],
                    }
                    for b in buildings
                ])
                db.commit()

            total += len(buildings)
            offset += len(features)
            if len(features) < page_size:
                break  # last page
    finally:
        db.close()

    print(f"\nTOTAL buildings imported: {total}")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="import only this many rows (validation)")
    parser.add_argument("--full", action="store_true", help="import all of Tel Aviv")
    parser.add_argument("--dry-run", action="store_true", help="fetch and report counts only, no DB writes")
    args = parser.parse_args()

    if not args.limit and not args.full:
        parser.error("specify --limit N for a test slice, or --full for the whole city")

    run_import(args.limit, args.dry_run)
