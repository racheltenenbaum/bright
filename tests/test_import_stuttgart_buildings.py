"""Not part of the src/ coverage gate (scripts/ is one-off bulk-import
tooling, not application code) — but the CityGML parsing has several
non-obvious cases (multi-part buildings, 0.0-height artifacts, UTM -> WGS84,
tile-grid math) that would silently corrupt production shade data if wrong.
"""
import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_stuttgart_buildings import (
    parse_citygml,
    tiles_for_bbox,
    tile_url,
    iter_zip_gml,
)

NS = (
    'xmlns:core="http://www.opengis.net/citygml/1.0" '
    'xmlns:bldg="http://www.opengis.net/citygml/building/1.0" '
    'xmlns:gml="http://www.opengis.net/gml" '
    'xmlns:gen="http://www.opengis.net/citygml/generics/1.0"'
)


def _ground(x: float, y: float, size: float = 10.0, z: float = 250.0) -> str:
    """A square GroundSurface with its SW corner at (x, y), in UTM metres."""
    ring = [(x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)]
    pos = " ".join(f"{px} {py} {z}" for px, py in ring)
    return f"""
      <bldg:boundedBy><bldg:GroundSurface><bldg:lod2MultiSurface><gml:MultiSurface>
        <gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing>
          <gml:posList srsDimension="3">{pos}</gml:posList>
        </gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember>
      </gml:MultiSurface></bldg:lod2MultiSurface></bldg:GroundSurface></bldg:boundedBy>"""


def _roof(x: float, y: float) -> str:
    """A RoofSurface — must never be mistaken for a footprint."""
    pos = f"{x} {y} 270 {x + 5} {y} 270 {x + 5} {y + 5} 270 {x} {y} 270"
    return f"""
      <bldg:boundedBy><bldg:RoofSurface><bldg:lod2MultiSurface><gml:MultiSurface>
        <gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing>
          <gml:posList srsDimension="3">{pos}</gml:posList>
        </gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember>
      </gml:MultiSurface></bldg:lod2MultiSurface></bldg:RoofSurface></bldg:boundedBy>"""


def _gml(*buildings: str) -> bytes:
    members = "".join(f"<core:cityObjectMember>{b}</core:cityObjectMember>" for b in buildings)
    return f'<?xml version="1.0" encoding="UTF-8"?><core:CityModel {NS}>{members}</core:CityModel>'.encode()


SIMPLE = f"""
  <bldg:Building gml:id="B1">
    <bldg:measuredHeight uom="urn:adv:uom:m">12.5</bldg:measuredHeight>
    {_ground(513450.0, 5402278.0)}{_roof(513450.0, 5402278.0)}
  </bldg:Building>"""

MULTI_PART = f"""
  <bldg:Building gml:id="B2">
    <bldg:consistsOfBuildingPart><bldg:BuildingPart gml:id="P1">
      <bldg:measuredHeight uom="urn:adv:uom:m">20.0</bldg:measuredHeight>
      {_ground(513500.0, 5402300.0)}
    </bldg:BuildingPart></bldg:consistsOfBuildingPart>
    <bldg:consistsOfBuildingPart><bldg:BuildingPart gml:id="P2">
      <bldg:measuredHeight uom="urn:adv:uom:m">6.0</bldg:measuredHeight>
      {_ground(513510.0, 5402300.0)}
    </bldg:BuildingPart></bldg:consistsOfBuildingPart>
  </bldg:Building>"""

ZERO_HEIGHT = f"""
  <bldg:Building gml:id="B3">
    <bldg:measuredHeight uom="urn:adv:uom:m">0.0</bldg:measuredHeight>
    {_ground(513600.0, 5402300.0)}
  </bldg:Building>"""

NO_HEIGHT = f"""
  <bldg:Building gml:id="B4">
    {_ground(513700.0, 5402300.0)}
  </bldg:Building>"""

NO_GROUND = """
  <bldg:Building gml:id="B5">
    <bldg:measuredHeight uom="urn:adv:uom:m">9.0</bldg:measuredHeight>
  </bldg:Building>"""


def test_simple_building_footprint_converted_to_lat_lng():
    rows = list(parse_citygml(io.BytesIO(_gml(SIMPLE))))
    assert len(rows) == 1
    b = rows[0]
    assert b["height"] == 12.5
    # SW corner (513450, 5402278) in ETRS89/UTM32 is ~48.77336N, 9.18306E —
    # footprint uses our internal [lat, lng] convention.
    lat, lng = b["footprint"][0]
    assert lat == pytest.approx(48.773360, abs=1e-5)
    assert lng == pytest.approx(9.183058, abs=1e-5)
    # Only the 5-point ground ring, never the roof polygon.
    assert len(b["footprint"]) == 5
    # UTM grid north isn't true north, so the SW corner isn't necessarily
    # the min-lat point — the bbox must come from the whole ring.
    assert b["min_lat"] == min(p[0] for p in b["footprint"])
    assert b["max_lng"] == max(p[1] for p in b["footprint"])
    assert b["max_lat"] > b["min_lat"] and b["max_lng"] > b["min_lng"]


def test_multi_part_building_yields_one_row_per_part_with_own_height():
    rows = list(parse_citygml(io.BytesIO(_gml(MULTI_PART))))
    assert sorted(r["height"] for r in rows) == [6.0, 20.0]
    # The two parts are 10m apart, so their footprints must differ.
    assert rows[0]["footprint"] != rows[1]["footprint"]


def test_zero_or_missing_height_and_missing_ground_are_skipped():
    stats: dict = {}
    rows = list(parse_citygml(io.BytesIO(_gml(ZERO_HEIGHT, NO_HEIGHT, NO_GROUND, SIMPLE)), stats=stats))
    assert [r["height"] for r in rows] == [12.5]
    assert stats["skipped_no_height"] == 2
    assert stats["skipped_no_ground"] == 1


def test_bbox_filter_uses_footprint_centroid():
    # Bbox around SIMPLE only (~48.7734N, 9.1831E); MULTI_PART sits ~60m
    # east/north of it, outside this tight box.
    bbox = (48.7733, 9.1830, 48.7736, 9.1834)
    rows = list(parse_citygml(io.BytesIO(_gml(SIMPLE, MULTI_PART)), bbox=bbox))
    assert [r["height"] for r in rows] == [12.5]


def test_tiles_for_bbox_matches_lgl_grid():
    # LGL's 2km tiles sit on odd-km eastings and even-km northings
    # (e.g. LoD2_32_513_5402_2_bw.zip covers E 513-515km, N 5402-5404km).
    tiles = tiles_for_bbox(48.775, 9.185, 48.78, 9.19)
    assert tiles == [(513, 5402)]


def test_tiles_for_full_stuttgart_bbox():
    tiles = tiles_for_bbox(48.69, 9.03, 48.87, 9.32)
    eastings = sorted({e for e, _ in tiles})
    northings = sorted({n for _, n in tiles})
    assert eastings == list(range(501, 524, 2))
    assert northings == list(range(5392, 5413, 2))
    assert len(tiles) == 12 * 11


def test_tile_url():
    assert tile_url(513, 5402) == "https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_513_5402_2_bw.zip"


def test_iter_zip_gml_reads_only_gml_members(tmp_path):
    path = tmp_path / "tile.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("t/LoD2_32_513_5402_1_BW.gml", _gml(SIMPLE))
        zf.writestr("t/Meta-3D-Gebäudemodell-LoD2.txt", "not xml")
        zf.writestr("t/GOVDATA-Datenlizenz_Deutschland.pdf", b"%PDF")
    contents = [f.read() for f in iter_zip_gml(path)]
    assert contents == [_gml(SIMPLE)]
