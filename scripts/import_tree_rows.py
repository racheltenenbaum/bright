"""One-time (then periodic) bulk import of a region's OSM tree rows
(natural=tree_row — a line of trees, e.g. an avenue's street trees) into
the local osm_buildings table.

Bulk-imported regions (Vienna, NYC, Tel Aviv) bypass the live Overpass path
entirely for buildings, so tree-row canopy shade — added there via the same
query that already fetches buildings — never reaches them without this
separate import. Each tree-row line is converted into small rectangular
canopy footprints (src.shadow.tree_row_to_canopy_segments) and stored with
source="tree_row", identical in shape to a building row so the existing
shadow-casting code needs no changes.

Coverage is real but patchy everywhere checked so far (OSM tree-row tagging
is inconsistent) — see docs/DATA_SOURCES.md for per-region counts. This
still strictly improves accuracy for whatever streets are tagged; it does
not regress anywhere.

Usage:
    # Validate a small area first — always do this before --full.
    python scripts/import_tree_rows.py path/to/Wien.osm.pbf --region vienna --bbox 48.20,16.36,48.21,16.37

    # Same, but report counts without writing to the DB.
    python scripts/import_tree_rows.py path/to/Wien.osm.pbf --region vienna --bbox 48.20,16.36,48.21,16.37 --dry-run

    # Full-extract import (run from repo root).
    python scripts/import_tree_rows.py path/to/Wien.osm.pbf --region vienna --full
"""
import argparse
import json
import sys
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import SessionLocal
from src.models import OsmBuilding
from src.shadow import tree_row_to_canopy_segments

SOURCE = "tree_row"
BATCH_SIZE = 20_000


class TreeRowHandler(osmium.SimpleHandler):
    def __init__(self, bbox: tuple[float, float, float, float] | None):
        super().__init__()
        self.bbox = bbox  # (s, w, n, e) — skip rows entirely outside this, if given
        self.canopies: list[dict] = []
        self.skipped_invalid_location = 0

    def way(self, w):
        if w.tags.get("natural") != "tree_row":
            return

        line = []
        try:
            for node in w.nodes:
                line.append((node.lat, node.lon))
        except osmium.InvalidLocationError:
            self.skipped_invalid_location += 1
            return

        if len(line) < 2:
            return

        if self.bbox:
            s, west, n, e = self.bbox
            lats = [p[0] for p in line]
            lngs = [p[1] for p in line]
            if max(lats) < s or min(lats) > n or max(lngs) < west or min(lngs) > e:
                return

        for segment in tree_row_to_canopy_segments(line):
            lats = [p[0] for p in segment["footprint"]]
            lngs = [p[1] for p in segment["footprint"]]
            self.canopies.append({
                "min_lat": min(lats), "max_lat": max(lats),
                "min_lng": min(lngs), "max_lng": max(lngs),
                "footprint": segment["footprint"],
                "height": segment["height"],
            })


def _flush(db, region: str, canopies: list[dict]) -> None:
    db.bulk_insert_mappings(OsmBuilding, [
        {**c, "footprint": json.dumps(c["footprint"]), "region": region, "source": SOURCE}
        for c in canopies
    ])
    db.commit()


def run_import(pbf_path: str, region: str, bbox: tuple[float, float, float, float] | None, dry_run: bool) -> int:
    handler = TreeRowHandler(bbox)
    handler.apply_file(pbf_path, locations=True)

    print(f"parsed {len(handler.canopies)} canopy segments "
          f"({handler.skipped_invalid_location} ways skipped for missing node location)")

    if dry_run:
        return len(handler.canopies)

    db = SessionLocal()
    total = 0
    try:
        batch: list[dict] = []
        for canopy in handler.canopies:
            batch.append(canopy)
            if len(batch) >= BATCH_SIZE:
                _flush(db, region, batch)
                total += len(batch)
                print(f"  inserted {total}/{len(handler.canopies)}")
                batch = []
        if batch:
            _flush(db, region, batch)
            total += len(batch)
    finally:
        db.close()

    print(f"\nTOTAL canopy segments imported: {total}")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pbf_path", help="path to a .osm.pbf extract")
    parser.add_argument("--region", required=True, help="region tag, e.g. 'vienna' — must match src/regions.py")
    parser.add_argument("--bbox", help="s,w,n,e — import just one area (validation)")
    parser.add_argument("--full", action="store_true", help="import the whole extract, no bbox filter")
    parser.add_argument("--dry-run", action="store_true", help="parse and report counts only, no DB writes")
    args = parser.parse_args()

    if not args.bbox and not args.full:
        parser.error("specify --bbox s,w,n,e for a test area, or --full for the whole extract")

    bbox = tuple(map(float, args.bbox.split(","))) if args.bbox else None
    run_import(args.pbf_path, args.region, bbox, args.dry_run)
