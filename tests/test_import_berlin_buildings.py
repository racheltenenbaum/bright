"""Not part of the src/ coverage gate (scripts/ is one-off bulk-import
tooling) — but Berlin's tiles come from an ATOM feed rather than a computed
grid, and its CityGML is in UTM zone 33 (Stuttgart's is 32), so a wrong tile
pick or projection would silently drop or misplace whole districts.
"""
import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_berlin_buildings import (
    DOWNLOAD_ATTEMPTS,
    TO_WGS84,
    download_tile,
    iter_zip_citygml,
    tile_url,
    tiles_for_bbox,
    tiles_in_feed,
)
from scripts.import_stuttgart_buildings import parse_citygml
from tests.test_import_stuttgart_buildings import _ground, _gml

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link href="https://gdi.berlin.de/data/a_lod2/atom/1X1_EPSG_25833.pdf" rel="describedby"/>
    <link href="https://gdi.berlin.de/data/a_lod2/atom/LoD2_391_5820.zip" rel="section"/>
    <link href="https://gdi.berlin.de/data/a_lod2/atom/LoD2_392_5820.zip" rel="section"/>
    <link href="https://gdi.berlin.de/data/a_lod2/atom/LoD2_371_5809.zip" rel="section"/>
    <link href="https://gdi.berlin.de/data/a_lod2/atom/LoD2_391_5820.zip" rel="alternate"/>
  </entry>
</feed>"""


def test_tiles_in_feed_lists_each_zip_once():
    assert tiles_in_feed(FEED) == [(371, 5809), (391, 5820), (392, 5820)]


def test_tile_url():
    assert tile_url(391, 5820) == "https://gdi.berlin.de/data/a_lod2/atom/LoD2_391_5820.zip"


def test_tiles_for_bbox_keeps_only_tiles_touching_the_bbox():
    # Tile 391_5820 spans UTM33 x 391000-392000, y 5820000-5821000, i.e.
    # roughly 52.519-52.528N, 13.394-13.408E. A bbox inside it picks just it.
    tiles = [(371, 5809), (391, 5820), (392, 5820)]
    assert tiles_for_bbox(tiles, 52.521, 13.396, 52.524, 13.400) == [(391, 5820)]


def test_tiles_for_bbox_spanning_two_tiles():
    tiles = [(371, 5809), (391, 5820), (392, 5820)]
    assert tiles_for_bbox(tiles, 52.521, 13.400, 52.524, 13.415) == [(391, 5820), (392, 5820)]


def test_parse_citygml_in_utm33():
    # SW corner of tile 391_5820 is 391000E 5820000N -> ~52.5192N 13.3935E.
    gml = _gml(f"""
      <bldg:Building gml:id="B1">
        <bldg:measuredHeight uom="urn:adv:uom:m">21.0</bldg:measuredHeight>
        {_ground(391000.0, 5820000.0)}
      </bldg:Building>""")
    rows = list(parse_citygml(io.BytesIO(gml), to_wgs84=TO_WGS84))
    assert len(rows) == 1
    assert rows[0]["height"] == 21.0
    assert abs(rows[0]["min_lat"] - 52.51920) < 1e-4
    assert abs(rows[0]["min_lng"] - 13.39354) < 1e-4


def test_iter_zip_citygml_reads_xml_and_gml_members(tmp_path):
    path = tmp_path / "LoD2_391_5820.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("LoD2_33_391_5820_1_BE.xml", b"<a/>")
        zf.writestr("other.gml", b"<b/>")
        zf.writestr("readme.pdf", b"x")
    assert [f.read() for f in iter_zip_citygml(path)] == [b"<a/>", b"<b/>"]


def test_download_tile_retries_a_stalled_download(tmp_path):
    ok = MagicMock(content=b"zip")
    with patch("scripts.import_berlin_buildings.time.sleep"), \
         patch("scripts.import_berlin_buildings.requests.get",
               side_effect=[requests.ConnectionError("Read timed out"), ok]):
        path = download_tile(391, 5820, tmp_path)
    assert path.read_bytes() == b"zip"


def test_download_tile_gives_up_after_max_attempts(tmp_path):
    with patch("scripts.import_berlin_buildings.time.sleep"), \
         patch("scripts.import_berlin_buildings.requests.get",
               side_effect=requests.ConnectionError("down")) as get:
        with pytest.raises(requests.ConnectionError):
            download_tile(391, 5820, tmp_path)
    assert get.call_count == DOWNLOAD_ATTEMPTS
    assert not (tmp_path / "LoD2_391_5820.zip").exists()
