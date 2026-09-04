"""One-time (then periodic) bulk import of a region's buildings from a
Geofabrik/BBBike .osm.pbf extract into the local osm_buildings table.

Unlike Vienna (see import_vienna_buildings.py), this uses plain OSM
height/building:levels tags rather than a city-specific dataset — NYC's OSM
height-tag coverage is already strong (~68%, thanks to an official LiDAR
dataset import), so there's no accuracy gap to close there the way there was
for Vienna. Height is parsed with the exact same _parse_height() logic
src/shadow.py already uses for live Overpass data, so bulk-imported and
live-fetched buildings are scored identically.

Usage:
    # Validate a small area first — always do this before --full.
    python scripts/import_osm_buildings.py path/to/NewYork.osm.pbf --region nyc --bbox 40.74,-74.00,40.76,-73.98

    # Same, but report counts without writing to the DB.
    python scripts/import_osm_buildings.py path/to/NewYork.osm.pbf --region nyc --bbox 40.74,-74.00,40.76,-73.98 --dry-run

    # Full-extract import (run from repo root).
    python scripts/import_osm_buildings.py path/to/NewYork.osm.pbf --region nyc --full
"""
import argparse
import json
import sys
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import SessionLocal
from src.models import OsmBuilding
from src.shadow import _parse_height

BATCH_SIZE = 20_000


class BuildingHandler(osmium.SimpleHandler):
    def __init__(self, bbox: tuple[float, float, float, float] | None):
        super().__init__()
        self.bbox = bbox  # (s, w, n, e) — skip buildings entirely outside this, if given
        self.buildings: list[dict] = []
        self.skipped_invalid_location = 0

    def way(self, w):
        tags = w.tags
        if "building" not in tags:
            return

        footprint = []
        try:
            for node in w.nodes:
                footprint.append((node.lat, node.lon))
        except osmium.InvalidLocationError:
            self.skipped_invalid_location += 1
            return

        if len(footprint) < 3:
            return

        lats = [p[0] for p in footprint]
        lngs = [p[1] for p in footprint]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)

        if self.bbox:
            s, west, n, e = self.bbox
            if max_lat < s or min_lat > n or max_lng < west or min_lng > e:
                return

        self.buildings.append({
            "min_lat": min_lat, "max_lat": max_lat,
            "min_lng": min_lng, "max_lng": max_lng,
            "footprint": [[lat, lng] for lat, lng in footprint],
            "height": _parse_height(dict(tags)),
        })


def _flush(db, region: str, buildings: list[dict]) -> None:
    db.bulk_insert_mappings(OsmBuilding, [
        {**b, "footprint": json.dumps(b["footprint"]), "region": region, "source": "osm"}
        for b in buildings
    ])
    db.commit()


def run_import(pbf_path: str, region: str, bbox: tuple[float, float, float, float] | None, dry_run: bool) -> int:
    handler = BuildingHandler(bbox)
    handler.apply_file(pbf_path, locations=True)

    print(f"parsed {len(handler.buildings)} buildings "
          f"({handler.skipped_invalid_location} skipped for missing node location)")

    if dry_run:
        return len(handler.buildings)

    db = SessionLocal()
    total = 0
    try:
        batch: list[dict] = []
        for building in handler.buildings:
            batch.append(building)
            if len(batch) >= BATCH_SIZE:
                _flush(db, region, batch)
                total += len(batch)
                print(f"  inserted {total}/{len(handler.buildings)}")
                batch = []
        if batch:
            _flush(db, region, batch)
            total += len(batch)
    finally:
        db.close()

    print(f"\nTOTAL buildings imported: {total}")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pbf_path", help="path to a .osm.pbf extract")
    parser.add_argument("--region", required=True, help="region tag, e.g. 'nyc' — must match src/regions.py")
    parser.add_argument("--bbox", help="s,w,n,e — import just one area (validation)")
    parser.add_argument("--full", action="store_true", help="import the whole extract, no bbox filter")
    parser.add_argument("--dry-run", action="store_true", help="parse and report counts only, no DB writes")
    args = parser.parse_args()

    if not args.bbox and not args.full:
        parser.error("specify --bbox s,w,n,e for a test area, or --full for the whole extract")

    bbox = tuple(map(float, args.bbox.split(","))) if args.bbox else None
    run_import(args.pbf_path, args.region, bbox, args.dry_run)
