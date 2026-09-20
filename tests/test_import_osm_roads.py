"""Not part of the src/ coverage gate (scripts/ is one-off bulk-import
tooling, not application code) — but this specific bug (plazas mapped as
OSM multipolygon relations coming back disconnected from the road network)
was real and reported in production, so it's worth locking in with a test.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_osm_roads import RoadHandler

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _write_plaza_osm(tmp_path) -> str:
    """A minimal OSM XML reproducing the real Josefsplatz/Heldenplatz
    pattern: a closed-ring way with NO highway tag of its own, wrapped by a
    type=multipolygon relation that carries highway=pedestrian — plus one
    plain footway sharing a node with the ring, to prove real connectivity."""
    osm_xml = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="48.2050" lon="16.3640"/>
  <node id="2" lat="48.2050" lon="16.3650"/>
  <node id="3" lat="48.2040" lon="16.3650"/>
  <node id="4" lat="48.2040" lon="16.3640"/>
  <node id="10" lat="48.2060" lon="16.3640"/>
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <nd ref="4"/>
    <nd ref="1"/>
  </way>
  <way id="200">
    <nd ref="10"/>
    <nd ref="1"/>
    <tag k="highway" v="footway"/>
  </way>
  <relation id="50">
    <member type="way" ref="100" role="outer"/>
    <tag k="type" v="multipolygon"/>
    <tag k="highway" v="pedestrian"/>
    <tag k="name" v="Test Plaza"/>
  </relation>
</osm>
"""
    path = tmp_path / "plaza.osm"
    path.write_text(osm_xml)
    return str(path)


def test_multipolygon_plaza_becomes_routable_and_connects_to_surrounding_ways(tmp_path):
    osm_path = _write_plaza_osm(tmp_path)
    handler = RoadHandler(bbox=None)
    handler.apply_file(osm_path, locations=True)

    # 4 ring edges (the plaza's perimeter, from the relation) + 1 footway edge.
    assert len(handler.edges) == 5

    all_coords = set()
    for e in handler.edges:
        all_coords.add((round(e["from_lat"], 6), round(e["from_lng"], 6)))
        all_coords.add((round(e["to_lat"], 6), round(e["to_lng"], 6)))

    # The plaza ring's node 1 (48.205, 16.364) and the footway's endpoint
    # must be the *same* coordinate — real shared-node connectivity, not
    # just two disjoint edge sets that happen to be geographically close.
    assert (48.205, 16.364) in all_coords
    footway_edge = next(e for e in handler.edges if e["from_lat"] == 48.206 or e["to_lat"] == 48.206)
    plaza_edges = [e for e in handler.edges if e is not footway_edge]
    assert len(plaza_edges) == 4
    shared_node = (round(footway_edge["to_lat"], 6), round(footway_edge["to_lng"], 6))
    assert any(
        (round(e["from_lat"], 6), round(e["from_lng"], 6)) == shared_node
        or (round(e["to_lat"], 6), round(e["to_lng"], 6)) == shared_node
        for e in plaza_edges
    )


def test_areas_only_skips_plain_way_edges(tmp_path):
    """For a targeted patch into a region that's already fully imported —
    only the newly-handled relation/area edges should be written, so a
    re-run can't duplicate way edges the region already has."""
    osm_path = _write_plaza_osm(tmp_path)
    handler = RoadHandler(bbox=None, areas_only=True)
    handler.apply_file(osm_path, locations=True)

    # Only the 4 plaza-ring edges — the footway (a plain way) must be skipped.
    assert len(handler.edges) == 4
    assert not any(e["from_lat"] == 48.206 or e["to_lat"] == 48.206 for e in handler.edges)


def test_multipolygon_without_allowed_highway_tag_is_skipped(tmp_path):
    """A multipolygon relation for something irrelevant (e.g. a building
    footprint, or a highway type not in ALLOWED_HIGHWAY_TYPES) must not
    produce routing edges."""
    osm_xml = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="48.2050" lon="16.3640"/>
  <node id="2" lat="48.2050" lon="16.3650"/>
  <node id="3" lat="48.2040" lon="16.3650"/>
  <node id="4" lat="48.2040" lon="16.3640"/>
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <nd ref="4"/>
    <nd ref="1"/>
  </way>
  <relation id="50">
    <member type="way" ref="100" role="outer"/>
    <tag k="type" v="multipolygon"/>
    <tag k="building" v="yes"/>
  </relation>
</osm>
"""
    path = tmp_path / "building.osm"
    path.write_text(osm_xml)

    handler = RoadHandler(bbox=None)
    handler.apply_file(str(path), locations=True)

    assert handler.edges == []
