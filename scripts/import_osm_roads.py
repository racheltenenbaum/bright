"""One-time (then periodic) bulk import of a region's road network from a
Geofabrik/BBBike .osm.pbf extract into the local osm_roads table.

This mirrors import_vienna_buildings.py's motivation: fetch_osm_road_network
in src/routing.py hits live Overpass on every single request, with no bulk
fallback — unlike buildings, which now have one for Vienna. Public Overpass
mirrors are shared infrastructure that can be slow or memory-limited for
heavily-used areas (LA is a much more common query target than e.g. Vienna),
so importing once removes that live dependency for the region entirely.

Edges are pre-split and pre-computed here (distance_m, oneway) using the same
highway-type filter as fetch_osm_road_network's live Overpass query, so
build_graph_from_edges() can build the routing graph directly from a local
query with zero re-parsing.

Usage:
    # Validate a small area first — always do this before --full.
    python scripts/import_osm_roads.py path/to/LosAngeles.osm.pbf --region la --bbox 34.04,-118.26,34.06,-118.24

    # Same, but report counts without writing to the DB.
    python scripts/import_osm_roads.py path/to/LosAngeles.osm.pbf --region la --bbox 34.04,-118.26,34.06,-118.24 --dry-run

    # Full-extract import (run from repo root).
    python scripts/import_osm_roads.py path/to/LosAngeles.osm.pbf --region la --full
"""
import argparse
import math
import sys
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import SessionLocal
from src.models import OsmRoad

# Must match fetch_osm_road_network's Overpass query in src/routing.py.
ALLOWED_HIGHWAY_TYPES = {
    "footway", "path", "pedestrian", "living_street", "residential",
    "service", "unclassified", "tertiary", "secondary", "primary",
    "cycleway", "steps", "track",
}

EARTH_RADIUS_M = 6_371_000.0
BATCH_SIZE = 20_000


def _haversine_m(lat1, lng1, lat2, lng2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


class RoadHandler(osmium.SimpleHandler):
    def __init__(self, bbox: tuple[float, float, float, float] | None):
        super().__init__()
        self.bbox = bbox  # (s, w, n, e) — skip edges entirely outside this, if given
        self.edges: list[dict] = []
        self.skipped_invalid_location = 0

    def way(self, w):
        highway = w.tags.get("highway")
        if highway not in ALLOWED_HIGHWAY_TYPES:
            return
        oneway = w.tags.get("oneway") == "yes"

        for i in range(len(w.nodes) - 1):
            try:
                n1, n2 = w.nodes[i], w.nodes[i + 1]
                lat1, lng1 = n1.lat, n1.lon
                lat2, lng2 = n2.lat, n2.lon
            except osmium.InvalidLocationError:
                self.skipped_invalid_location += 1
                continue

            if self.bbox:
                s, west, n, e = self.bbox
                if not (s <= lat1 <= n or s <= lat2 <= n) or not (west <= lng1 <= e or west <= lng2 <= e):
                    continue

            self.edges.append({
                "min_lat": min(lat1, lat2), "max_lat": max(lat1, lat2),
                "min_lng": min(lng1, lng2), "max_lng": max(lng1, lng2),
                "from_lat": lat1, "from_lng": lng1,
                "to_lat": lat2, "to_lng": lng2,
                "distance_m": _haversine_m(lat1, lng1, lat2, lng2),
                "oneway": oneway,
            })


def _flush(db, region: str, edges: list[dict]) -> None:
    db.bulk_insert_mappings(OsmRoad, [{**e, "region": region} for e in edges])
    db.commit()


def run_import(pbf_path: str, region: str, bbox: tuple[float, float, float, float] | None, dry_run: bool) -> int:
    handler = RoadHandler(bbox)
    handler.apply_file(pbf_path, locations=True)

    print(f"parsed {len(handler.edges)} edges "
          f"({handler.skipped_invalid_location} skipped for missing node location)")

    if dry_run:
        return len(handler.edges)

    db = SessionLocal()
    total = 0
    try:
        batch: list[dict] = []
        for edge in handler.edges:
            batch.append(edge)
            if len(batch) >= BATCH_SIZE:
                _flush(db, region, batch)
                total += len(batch)
                print(f"  inserted {total}/{len(handler.edges)}")
                batch = []
        if batch:
            _flush(db, region, batch)
            total += len(batch)
    finally:
        db.close()

    print(f"\nTOTAL edges imported: {total}")
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pbf_path", help="path to a .osm.pbf extract")
    parser.add_argument("--region", required=True, help="region tag, e.g. 'la' — must match src/regions.py")
    parser.add_argument("--bbox", help="s,w,n,e — import just one area (validation)")
    parser.add_argument("--full", action="store_true", help="import the whole extract, no bbox filter")
    parser.add_argument("--dry-run", action="store_true", help="parse and report counts only, no DB writes")
    args = parser.parse_args()

    if not args.bbox and not args.full:
        parser.error("specify --bbox s,w,n,e for a test area, or --full for the whole extract")

    bbox = tuple(map(float, args.bbox.split(","))) if args.bbox else None
    run_import(args.pbf_path, args.region, bbox, args.dry_run)
