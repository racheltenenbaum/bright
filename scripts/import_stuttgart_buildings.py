"""One-time (then yearly) import of Baden-Württemberg's official 3D building
model (LoD2, CityGML) for Stuttgart into the local osm_buildings table.

Source: LGL Baden-Württemberg's Open GeoData Portal (opengeodata.lgl-bw.de),
licensed dl-de/by-2-0 — attribution "Datenquelle: LGL, www.lgl-bw.de,
dl-de/by-2-0" is shown on the About page. Heights come from airborne laser
scans (~1m accuracy), versus OSM's Stuttgart height-tag coverage of <30%.

The portal's UI only allows 10 tiles per download, so this fetches the
underlying 2km x 2km tile zips directly (each holds four 1km CityGML files).
Downloaded zips are cached in --cache-dir and reused on re-runs.

Each Building — or each BuildingPart, when a building is split into parts
with their own heights — becomes one row: footprint = its GroundSurface
ring(s), height = bldg:measuredHeight (ground to highest roof point).
Rows are assigned to a chunk by footprint centroid, so adjacent --bbox
chunks never import the same building twice.

Usage:
    # Validate a small area first — always do this before larger chunks.
    python scripts/import_stuttgart_buildings.py --bbox 48.77,9.17,48.78,9.18 --dry-run
    python scripts/import_stuttgart_buildings.py --bbox 48.77,9.17,48.78,9.18

    # Then import chunk by chunk (check DB disk headroom between chunks).
    python scripts/import_stuttgart_buildings.py --bbox 48.69,9.03,48.78,9.175

    # Or everything at once (only once headroom is confirmed).
    python scripts/import_stuttgart_buildings.py --full
"""
import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import IO, Iterator

import requests
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REGION = "stuttgart"
SOURCE = "lgl_lod2"
TILE_URL = "https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_{e}_{n}_2_bw.zip"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "bright" / "lod2"
BATCH_SIZE = 20_000

BLDG = "{http://www.opengis.net/citygml/building/1.0}"
GML = "{http://www.opengis.net/gml}"

# ETRS89 / UTM zone 32N (EPSG:25832) <-> WGS84. always_xy: (x, y) = (lng, lat).
_TO_WGS84 = Transformer.from_crs(25832, 4326, always_xy=True)
_TO_UTM = Transformer.from_crs(4326, 25832, always_xy=True)


def tiles_for_bbox(s: float, w: float, n: float, e: float) -> list[tuple[int, int]]:
    """LGL's 2km tile ids (easting_km, northing_km) covering a lat/lng bbox.
    Tiles sit on odd-km eastings and even-km northings."""
    xs, ys = _TO_UTM.transform([w, e, w, e], [s, s, n, n])
    min_e, max_e = min(xs) / 1000, max(xs) / 1000
    min_n, max_n = min(ys) / 1000, max(ys) / 1000
    e_start = math.floor((min_e - 1) / 2) * 2 + 1
    e_end = math.floor((max_e - 1) / 2) * 2 + 1
    n_start = math.floor(min_n / 2) * 2
    n_end = math.floor(max_n / 2) * 2
    return [
        (te, tn)
        for te in range(e_start, e_end + 1, 2)
        for tn in range(n_start, n_end + 1, 2)
    ]


def tile_url(e: int, n: int) -> str:
    return TILE_URL.format(e=e, n=n)


def download_tile(e: int, n: int, cache_dir: Path) -> Path | None:
    """Returns the cached zip path, or None if LGL has no tile there."""
    path = cache_dir / f"LoD2_32_{e}_{n}_2_bw.zip"
    if path.exists():
        return path
    resp = requests.get(tile_url(e, n), timeout=300)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    tmp = path.with_suffix(".part")
    tmp.write_bytes(resp.content)
    tmp.rename(path)
    return path


def iter_zip_gml(path: Path) -> Iterator[IO[bytes]]:
    # Read members straight from the zip: one bundled file has a non-UTF-8
    # umlaut in its name that makes the `unzip` CLI fail on macOS.
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".gml"):
                with zf.open(name) as f:
                    yield f


def _ground_rings(unit: ET.Element) -> list[list[tuple[float, float]]]:
    """The unit's own GroundSurface exterior rings, as UTM (x, y) points.
    Only direct boundedBy children — a Building's parts carry their own."""
    rings = []
    for ground in unit.findall(f"{BLDG}boundedBy/{BLDG}GroundSurface"):
        for pos_list in ground.iter(f"{GML}posList"):
            vals = [float(v) for v in pos_list.text.split()]
            dim = int(pos_list.get("srsDimension", "3"))
            pts = [(vals[i], vals[i + 1]) for i in range(0, len(vals), dim)]
            if len(pts) >= 3:
                rings.append(pts)
    return rings


def _height(unit: ET.Element) -> float | None:
    el = unit.find(f"{BLDG}measuredHeight")
    if el is None or not el.text:
        return None
    h = float(el.text)
    # 0.0 heights are LGL post-processing artifacts (per their INFO file).
    return h if h > 0 else None


def parse_citygml(
    source: IO[bytes],
    bbox: tuple[float, float, float, float] | None = None,
    stats: dict | None = None,
) -> Iterator[dict]:
    """Yield osm_buildings-shaped dicts from one CityGML file. If bbox
    (s, w, n, e) is given, keep only rows whose footprint centroid is in it."""
    if stats is None:
        stats = {}
    stats.setdefault("skipped_no_height", 0)
    stats.setdefault("skipped_no_ground", 0)

    for _, elem in ET.iterparse(source, events=("end",)):
        if elem.tag != f"{BLDG}Building":
            continue
        parts = elem.findall(f"{BLDG}consistsOfBuildingPart/{BLDG}BuildingPart")
        for unit in parts or [elem]:
            height = _height(unit)
            if height is None:
                stats["skipped_no_height"] += 1
                continue
            rings = _ground_rings(unit)
            if not rings:
                stats["skipped_no_ground"] += 1
                continue
            for ring in rings:
                lngs, lats = _TO_WGS84.transform([p[0] for p in ring], [p[1] for p in ring])
                if bbox:
                    s, w, n, e = bbox
                    c_lat, c_lng = sum(lats) / len(lats), sum(lngs) / len(lngs)
                    if not (s <= c_lat < n and w <= c_lng < e):
                        continue
                yield {
                    "min_lat": min(lats), "max_lat": max(lats),
                    "min_lng": min(lngs), "max_lng": max(lngs),
                    "footprint": [[lat, lng] for lat, lng in zip(lats, lngs)],
                    "height": height,
                }
        elem.clear()  # keep memory flat on 50MB files


def _flush(db, buildings: list[dict]) -> None:
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
    tiles = tiles_for_bbox(*bbox)
    print(f"{len(tiles)} tiles cover bbox {bbox}")

    db = None if dry_run else SessionLocal()
    stats: dict = {}
    total = 0
    batch: list[dict] = []
    try:
        for i, (e, n) in enumerate(tiles, 1):
            path = download_tile(e, n, cache_dir)
            if path is None:
                print(f"[{i}/{len(tiles)}] tile {e}_{n}: none published, skipping")
                continue
            tile_count = 0
            for gml in iter_zip_gml(path):
                for b in parse_citygml(gml, bbox=bbox, stats=stats):
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
    parser.add_argument("--full", action="store_true", help="import all of Stuttgart")
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
