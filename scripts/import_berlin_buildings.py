"""One-time (then yearly) import of Berlin's official 3D building model
(LoD2, CityGML) into the local osm_buildings table.

Source: Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin, via
the GDI Berlin INSPIRE ATOM feed (gdi.berlin.de/data/a_lod2/atom), licensed
dl-de/zero-2-0 (no attribution required; credited on the About page anyway).
~540k buildings, footprints straight from the property cadastre, heights
(bldg:measuredHeight) from airborne laser scans.

The data uses the same AdV CityGML profile as Stuttgart's, so parsing is
shared with import_stuttgart_buildings.parse_citygml — only the projection
(UTM zone 33 here, 32 there) and the tiling differ. Berlin's tiles are
1km x 1km zips, each holding one CityGML .xml file, listed in the ATOM
dataset feed rather than on a computable grid (edge tiles only exist where
Berlin does), so the tile list comes from the feed.

Rows are assigned to a chunk by footprint centroid, so adjacent --bbox
chunks never import the same building twice.

Usage:
    # Validate a small area first — always do this before larger chunks.
    python scripts/import_berlin_buildings.py --bbox 52.52,13.40,52.53,13.42 --dry-run
    python scripts/import_berlin_buildings.py --bbox 52.52,13.40,52.53,13.42

    # Then import chunk by chunk (check DB disk headroom between chunks).
    python scripts/import_berlin_buildings.py --bbox 52.33,13.08,52.505,13.425

    # Or everything at once (only once headroom is confirmed).
    python scripts/import_berlin_buildings.py --full
"""
import argparse
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import IO, Iterator

import requests
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_stuttgart_buildings import BATCH_SIZE, parse_citygml

REGION = "berlin"
SOURCE = "berlin_lod2"
FEED_URL = "https://gdi.berlin.de/data/a_lod2/atom/0.atom"
TILE_URL = "https://gdi.berlin.de/data/a_lod2/atom/LoD2_{e}_{n}.zip"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "bright" / "lod2_berlin"
DOWNLOAD_ATTEMPTS = 4
RETRY_DELAY_S = 10

# ETRS89 / UTM zone 33N (EPSG:25833) <-> WGS84. always_xy: (x, y) = (lng, lat).
TO_WGS84 = Transformer.from_crs(25833, 4326, always_xy=True)
_TO_UTM = Transformer.from_crs(4326, 25833, always_xy=True)

_TILE_RE = re.compile(r"LoD2_(\d+)_(\d+)\.zip")


def tiles_in_feed(feed_xml: str) -> list[tuple[int, int]]:
    """Every (easting_km, northing_km) tile the ATOM feed links to, sorted."""
    return sorted({(int(e), int(n)) for e, n in _TILE_RE.findall(feed_xml)})


def tiles_for_bbox(
    tiles: list[tuple[int, int]], s: float, w: float, n: float, e: float,
) -> list[tuple[int, int]]:
    """The published tiles whose 1km square touches a lat/lng bbox."""
    xs, ys = _TO_UTM.transform([w, e, w, e], [s, s, n, n])
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    return [
        (te, tn) for te, tn in tiles
        if te * 1000 < max_x and (te + 1) * 1000 > min_x
        and tn * 1000 < max_y and (tn + 1) * 1000 > min_y
    ]


def tile_url(e: int, n: int) -> str:
    return TILE_URL.format(e=e, n=n)


def fetch_tiles(cache_dir: Path) -> list[tuple[int, int]]:
    path = cache_dir / "0.atom"
    if not path.exists():
        resp = requests.get(FEED_URL, timeout=60)
        resp.raise_for_status()
        path.write_text(resp.text, encoding="utf-8")
    return tiles_in_feed(path.read_text(encoding="utf-8"))


def download_tile(e: int, n: int, cache_dir: Path) -> Path:
    path = cache_dir / f"LoD2_{e}_{n}.zip"
    if path.exists():
        return path
    # gdi.berlin.de occasionally stalls mid-download on a full-city run
    # (seen once in ~660 tiles); retry rather than abort the whole import.
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            resp = requests.get(tile_url(e, n), timeout=300)
            resp.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == DOWNLOAD_ATTEMPTS:
                raise
            print(f"  tile {e}_{n}: download failed (attempt {attempt}), retrying")
            time.sleep(RETRY_DELAY_S * attempt)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(resp.content)
    tmp.rename(path)
    return path


def iter_zip_citygml(path: Path) -> Iterator[IO[bytes]]:
    # Berlin ships its CityGML as .xml; accept .gml too in case that changes.
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.lower().endswith((".xml", ".gml")):
                with zf.open(name) as f:
                    yield f


def _flush(db, buildings: list[dict]) -> None:
    import json

    from src.models import OsmBuilding

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


def run_import(bbox: tuple[float, float, float, float], cache_dir: Path, dry_run: bool) -> int:
    from src.database import SessionLocal

    cache_dir.mkdir(parents=True, exist_ok=True)
    tiles = tiles_for_bbox(fetch_tiles(cache_dir), *bbox)
    print(f"{len(tiles)} tiles cover bbox {bbox}")

    db = None if dry_run else SessionLocal()
    stats: dict = {}
    total = 0
    batch: list[dict] = []
    try:
        for i, (e, n) in enumerate(tiles, 1):
            path = download_tile(e, n, cache_dir)
            tile_count = 0
            for gml in iter_zip_citygml(path):
                for b in parse_citygml(gml, bbox=bbox, stats=stats, to_wgs84=TO_WGS84):
                    batch.append(b)
                    tile_count += 1
                    if len(batch) >= BATCH_SIZE:
                        if db:
                            _flush(db, batch)
                        batch = []
            total += tile_count
            print(f"[{i}/{len(tiles)}] tile {e}_{n}: {tile_count} buildings (running total {total})")
        if batch and db:
            _flush(db, batch)
    finally:
        if db:
            db.close()

    print(f"\nTOTAL buildings {'found (dry run)' if dry_run else 'imported'}: {total}")
    print(f"Skipped: {stats.get('skipped_no_height', 0)} without height, "
          f"{stats.get('skipped_no_ground', 0)} without ground footprint")
    return total


if __name__ == "__main__":
    from src.regions import REGION_BOUNDS

    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", help="s,w,n,e — import only this chunk")
    parser.add_argument("--full", action="store_true", help="import all of Berlin")
    parser.add_argument("--dry-run", action="store_true", help="download + parse, report counts only, no DB writes")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    if args.bbox:
        bbox = tuple(float(v) for v in args.bbox.split(","))
    elif args.full:
        bbox = REGION_BOUNDS[REGION]
    else:
        parser.error("specify --bbox s,w,n,e for a chunk, or --full for the whole city")

    run_import(bbox, args.cache_dir, args.dry_run)
