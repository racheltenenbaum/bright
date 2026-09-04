# Bulk-imported regional data sources

Tracks, per region, where each region's `osm_buildings`/`osm_roads` data
actually came from — so we know what "version" is live in production and
whether a newer one has since been published. See `src/regions.py` for the
region bounding boxes and `scripts/import_*.py` for the ingestion scripts.

Update this file whenever a region's data is (re-)imported.

## Tree canopy (all regions, via `scripts/import_tree_rows.py`)

OSM's `natural=tree_row` tag (a line of street trees) is converted into
small rectangular canopy footprints (`src/shadow.py:tree_row_to_canopy_segments`,
assumed 5m width / 9m height — no per-tree data exists in OSM) and stored in
`osm_buildings` with `source="tree_row"`, so they shade routes exactly like
buildings with zero changes to the shadow-casting code. Live-fetched
(unimported) regions get this automatically via the same Overpass query
that fetches buildings; bulk-imported regions needed this separate import
since they bypass that live query entirely.

**Coverage is real but patchy everywhere checked — this is additive, not a
complete fix.** OSM's tree-row tagging is inconsistent city to city and even
street to street; e.g. Vienna's Praterstrasse (fully tree-lined in reality)
has only 1 tagged way in OSM. Expect some correctly-shaded tree-lined
streets and many still showing as unshaded due to missing tags, not a data
bug.

| Region | Tree-row ways found | Canopy segments imported | Imported |
|---|---|---|---|
| Vienna | 2,046 | 4,681 | 2026-09-04 |
| NYC | 409 | 1,103 | 2026-09-04 |
| Tel Aviv | 15 | 33 | 2026-09-04 |
| LA | ~150 | 357 | 2026-09-04 |

Uses the same extracts already listed below for each region's roads/buildings
import — no separate download needed.

## Vienna

**Buildings** — source: Vienna's own WFS, layer `ogdwien:FMZKBKMOGD`
("Baukörpermodell" / building-body model), `data.wien.gv.at`. Height =
`O_KOTE - HOEHE_DGM` (rooftop elevation minus ground elevation).

- Dataset version/date: not exposed by the WFS API — it's a live city
  service with no version number, so "data as of" = whenever it was queried.
- Imported: 2026-09-04 (production), via `scripts/import_vienna_buildings.py --full`.
- To check for updates: no versioned changelog found; periodically re-run
  the import (see the quarterly reminder routine) since the underlying
  cadastral data updates on the city's own schedule, not ours.

**Roads** — source: OSM data via a BBBike pre-clipped extract (`Wien.osm.pbf`),
downloaded from `download.bbbike.org` **2026-09-03 11:39 (local time)**.

- Imported: 2026-09-04 (production), via
  `scripts/import_osm_roads.py --region vienna --full` — 1,544,326 edges.

## New York City

**Buildings** — source: OSM data via a BBBike pre-clipped extract
(`NewYork.osm.pbf`), downloaded from `download.bbbike.org`. Height parsed
via `src/shadow.py:_parse_height` (OSM `height`/`building:levels` tags),
same logic used for live Overpass data.

- Dataset version/date: BBBike extracts are generated from OSM's live
  database on request — this specific file was downloaded **2026-09-03
  11:39 (local time)**, so it reflects OSM's NYC data as of that moment.
- Imported: 2026-09-03/04 (production), per-borough via
  `scripts/import_osm_buildings.py --region nyc --bbox <borough bbox>`
  (Manhattan, Brooklyn, Queens, Bronx, Staten Island).
- Coverage note: OSM height-tag coverage for NYC is ~68% (good — an
  official NYC LiDAR dataset was previously imported into OSM there).

**Roads** — same extract/source as buildings above, via
`scripts/import_osm_roads.py --region nyc`. Imported per-borough, plus four
supplementary "seam" imports (Harlem River, East River, Verrazzano, Throgs
Neck/Whitestone bboxes) to close bridge/connector gaps the borough
rectangles missed at their edges.

## Los Angeles

**Buildings, roads, and tree canopy** — source: OSM data via a BBBike
pre-clipped extract (`LosAngeles.osm.pbf`), downloaded from
`download.bbbike.org` **2026-09-03 22:24 (local time)**. Height parsed via
`src/shadow.py:_parse_height`, same as NYC.

- Imported: 2026-09-04 (production), in 4 quadrants (splitting LA's bbox at
  its midpoint lat/lng) via `scripts/import_osm_buildings.py --region la`
  and `scripts/import_osm_roads.py --region la` for each quadrant, plus
  `scripts/import_tree_rows.py --region la --full` (whole extract, no
  quadranting needed — tree-row count was small enough).
- Totals: 1,468,294 buildings, 1,620,590 road edges, 357 tree canopy segments.

## Tel Aviv

**Buildings** — source: Tel Aviv Municipality's GIS server, ArcGIS
MapServer service `IView2_Testing_Alon`, layer 513 ("מבנים" / Buildings),
`gisn.tel-aviv.gov.il`. Height = field `gova_simplex_2019` (verified against
live samples to equal `max_height - min_height` exactly); floor count
(`ms_komot`) and LiDAR-derived heights (`dsm_mean`/`dsm_max`) are also
available in the source layer if ever needed but not currently stored.

- ⚠️ **Stability caveat**: this service is on a personal/test-labeled
  endpoint (`IView2_Testing_Alon`), not an official open-data catalog
  listing. It's publicly accessible and working as of this writing, but
  could be renamed, restricted, or removed without notice — unlike a
  cataloged dataset. Re-verify this URL still resolves before any future
  re-import; if it's gone, the coverage search done on 2026-09-04 (checked
  `opendata.tel-aviv.gov.il`, this ArcGIS server, and Israel's national
  `data.gov.il` portal) found no other building-height dataset for Tel
  Aviv, so this may need to be redone from scratch.
- Dataset version/date: the field name `gova_simplex_2019` suggests the
  underlying height computation dates to **2019** — no explicit
  last-updated metadata is exposed via the ArcGIS service API
  (`editingInfo` was empty). Actual building footprints/attributes could
  still be edited more recently than 2019 without that being visible to us.
- Imported: 2026-09-04 (production), via
  `scripts/import_telaviv_buildings.py --full` (43,875 of 45,795 total rows
  had usable height + geometry data).

**Roads** — source: OSM data via Geofabrik's `israel-and-palestine-latest.osm.pbf`
extract, downloaded 2026-09-04 (whole-country file, filtered to Tel Aviv's
bbox at import time — no pre-clipped city extract was available).

- Imported: 2026-09-04 (production), via
  `scripts/import_osm_roads.py --region telaviv --bbox 32.02,34.74,32.15,34.85`
  — 121,940 edges.
