# Bulk-imported regional data sources

Tracks, per region, where each region's `osm_buildings`/`osm_roads` data
actually came from — so we know what "version" is live in production and
whether a newer one has since been published. See `src/regions.py` for the
region bounding boxes and `scripts/import_*.py` for the ingestion scripts.

Update this file whenever a region's data is (re-)imported.

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

**Roads** — not yet imported (as of 2026-09-04). Vienna still falls back to
live Overpass for road data.

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

**Not yet live in production** (as of 2026-09-04) — `la` is registered in
`REGION_BOUNDS` but has zero rows in either table, so it currently falls
back to live Overpass for everything.

- Extract on hand for whenever this is picked up: `LosAngeles.osm.pbf`
  (BBBike), downloaded **2026-09-03 22:24 (local time)**.
- A small validation tile (roads only) was imported and verified working,
  then deleted — no real data has been committed anywhere.

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

**Roads** — not yet imported (as of 2026-09-04). Tel Aviv still falls back
to live Overpass for road data. OSM's own road coverage there was checked
and found reasonable (~17,700 routable ways) when this region was scoped.
