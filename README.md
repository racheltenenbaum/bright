# ☀️ bright

**Sunshine, mapped.** bright is your sun companion - whether you love it or hide away. Plan walking routes street by street using real-time sun position, finding the sunniest (or shadiest) path between any two points.

Instead of the shortest path, bright computes real-time solar geometry, casts building shadows using OpenStreetMap footprints, and re-weights every street segment in the route graph so the sunniest (or shadiest) path wins - not just the shortest path.

---

## Table of contents

- [Why it's interesting](#why-its-interesting)
- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [External APIs](#external-apis)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Running the mobile app (iOS)](#running-the-mobile-app-ios)
- [Testing](#testing)
- [Deployment](#deployment)
- [AI-assisted development](#ai-assisted-development)

---

## Why it's interesting

Most routing apps optimize for distance or time. bright optimizes for a physical quantity that changes minute-to-minute: **where the sun is, and what's blocking it.**

That means the backend has to, on every request:

1. Compute the sun's real position (altitude + azimuth) for any lat/lng and timestamp using low-level astronomical formulas - no third-party ephemeris API, just orbital mechanics (Julian day, mean anomaly, ecliptic longitude, obliquity, hour angle) implemented directly in Python.
2. Pull real building footprints and heights from OpenStreetMap (via the Overpass API) for the bounding box around the route.
3. Cast each building's shadow as a geometric polygon (`shapely`) based on the sun's current angle, then test whether any point on the candidate route falls inside it.
4. Build a walkable street graph from OSM road data (`networkx`), penalize (or reward) shaded edges depending on the user's sun/shade preference, and run shortest-path search on the *reweighted* graph - then cap the detour against the plain-shortest-distance path so a preference for sun/shade never sends someone three times around the block.
5. Layer in terrain shadow-casting (hills/valleys blocking low-angle sun even with zero buildings around) using Google's Elevation API and ray-marching along the sun's back-bearing.

All of this is cached two ways (in-process + SQLite) since Overpass is a shared public service with rate limits, and it fails over across three independent Overpass mirrors for resilience.

## Features

- **Sun/shade-optimized routing** - walk the sunniest (or shadiest) route between any two points, with a configurable max-detour tolerance (%) traded against pure distance.
- **Segment-level shadow analysis** - every leg of a route (and every side of the street) is classified as sunny, shaded, or "which sidewalk is in the sun," including a batch endpoint that analyzes multiple candidate routes in parallel.
- **Terrain shadow modeling** - accounts for hills blocking low sun angles, not just buildings, using elevation ray-marching.
- **Find places that are sunny or shaded right now** - cafes, bars, parks, and restaurants open right now, filtered by sun or shade, with an evening auto-fallback and review/quality filtering.
- **Live weather + sun position** for any point, pulled from Google's Weather API and merged with locally computed solar altitude.
- **Save your frequently taken routes** - bright recalculates sun and shade every time you open them, so home-to-work is always accurate.
- **Save spots** - save sunny benches or shady terraces as spots and use them as route endpoints, each shareable via a public UUID link (no login required to view).
- **Tailored to you** - set your default sun/shade mode, pick your map style (roadmap, terrain or satellite), and control how much of a detour bright can suggest - all persisted server-side.
- **Share anything** - send a route or spot to anyone via link, no account needed to view.
- **Day/night theming** - the frontend computes solar altitude client-side (mirroring the backend algorithm) to auto-switch a night mode based on the user's actual location and time.
- **Rate limiting** per-endpoint (login, weather, shadow computation) to protect shared upstream API quotas.
- **Native iOS app** via Capacitor, sharing 100% of the React web codebase, with native geolocation and native share sheet integration.
- **Currency-aware place details** - automatically formats prices in the correct local currency symbol based on the place's country.

## Architecture

```
┌─────────────────────┐        ┌──────────────────────────────────────────┐
│   React 18 + Vite    │  HTTP  │              FastAPI backend              │
│  (web + Capacitor iOS)│──────▶│                                          │
│                      │  JWT   │  routers/  users · spots · routes ·      │
│  Leaflet / Google Maps│◀──────│  weather · places · sun · shadow_analyze │
└─────────────────────┘        │           · routing                      │
                                │                                          │
                                │  src/shadow.py    - shadow geometry       │
                                │  src/routing.py   - graph + pathfinding   │
                                │  src/utils/astronomy.py - solar position  │
                                └───────────────┬──────────────────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
           MySQL (Railway) via          Overpass API (OSM)           Google Maps Platform
           SQLAlchemy + Alembic     buildings, roads - 3 mirrors    Places · Weather · Elevation
                                    + SQLite L2 cache               + astronomy.com fallback
```

## Tech stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) - async Python web framework
- [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [Alembic](https://alembic.sqlalchemy.org/) - ORM and versioned schema migrations
- [MySQL](https://www.mysql.com/) (production, via `pymysql`) / SQLite (tests)
- [Pydantic v2](https://docs.pydantic.dev/) - request/response validation
- [python-jose](https://github.com/mpdavis/python-jose) + [bcrypt](https://pypi.org/project/bcrypt/) - JWT auth and password hashing
- [slowapi](https://github.com/laurentS/slowapi) - per-route rate limiting
- [NetworkX](https://networkx.org/) - street-graph construction and Dijkstra/shortest-path routing
- [Shapely](https://shapely.readthedocs.io/) - shadow polygon geometry (convex hulls, point-in-polygon)
- [Uvicorn](https://www.uvicorn.org/) - ASGI server

**Frontend**
- [React 18](https://react.dev/) + [Vite](https://vitejs.dev/)
- [React Router](https://reactrouter.com/) - client-side routing, code-split with `React.lazy`
- [@react-google-maps/api](https://www.npmjs.com/package/@react-google-maps/api) + [Leaflet](https://leafletjs.com/) / [react-leaflet](https://react-leaflet.js.org/) - dual mapping support
- [Axios](https://axios-http.com/) - API client
- [Font Awesome](https://fontawesome.com/) - iconography

**Mobile**
- [Capacitor 5](https://capacitorjs.com/) - native iOS shell wrapping the same React build
  - `@capacitor/geolocation`, `@capacitor/share` for native device APIs

**Infra / DevOps**
- [Railway](https://railway.app/) - hosting (backend + frontend), MySQL database
- Docker (`Dockerfile`, `.dockerignore`) - containerized backend
- `nixpacks` build (`railway.toml`) with `/health` healthcheck
- `pytest` + `pytest-cov` - test suite, enforced ≥99% coverage gate

## External APIs

| API | Used for |
|---|---|
| **Google Maps Places API** | Nearby search & place details (ratings, hours, photos, reviews, phone, website) for Find Places |
| **Google Maps Weather API** | Live temperature, UV index, cloud cover, and conditions for a coordinate |
| **Google Maps Elevation API** | Terrain height sampling, used both for building-shadow height correction and ray-marched terrain shadow detection |
| **Google Maps JavaScript API** | Frontend map rendering, autocomplete, geocoding |
| **OpenStreetMap Overpass API** | Building footprints + heights and the walkable street graph - queried against **three independent mirrors** (`overpass-api.de`, `overpass.kumi.systems`, `overpass.openstreetmap.ru`) with automatic failover |

All third-party geodata is cached at two layers (in-memory + SQLite `overpass_cache.db`) keyed by rounded bounding box, so repeated requests over the same area don't re-hit Overpass.

## Project structure

```
bright/
├── src/                      # FastAPI backend
│   ├── main.py                # App factory, CORS, router registration
│   ├── auth.py                 # JWT issuing/verification
│   ├── database.py              # SQLAlchemy engine/session
│   ├── models.py                 # User, Route, Spot ORM models
│   ├── schemas.py                  # Pydantic request/response schemas
│   ├── shadow.py                     # Shadow-casting geometry, sunny-side-of-street logic
│   ├── routing.py                      # OSM graph building + sun/shade-weighted pathfinding
│   ├── limiter.py                        # Rate-limit configuration
│   ├── utils/astronomy.py                  # Sun position (altitude/azimuth) calculation
│   └── routers/                              # users, spots, routes, weather, places,
│                                                 sun, shadow_analyze, routing
├── tests/                    # pytest suite (300+ tests, ≥99% coverage gate)
├── alembic/                  # Versioned DB migrations
├── client/                   # React + Vite frontend
│   ├── src/pages/              # Home, Login, Register, PlanRoute, MyRoutes, MySpots,
│   │                              MyAccount, SharedRoute, SharedSpot, About
│   ├── src/components/           # Navbar, RouteMap, RegisterForm
│   ├── src/context/                 # AuthContext (JWT session state)
│   └── ios/                            # Capacitor-generated native iOS project
├── Dockerfile, Procfile, railway.toml   # Deployment
└── CLAUDE.md                            # TDD workflow instructions for AI-assisted dev
```

## Getting started

**bright is already live** - just open [brightfe-production.up.railway.app](https://brightfe-production.up.railway.app) in your browser. No setup, no API keys.

The steps below are for running a local development copy.

### Prerequisites (local dev only)

- Python 3.12
- Node.js 18+
- A MySQL database (or point `DATABASE_URL` at SQLite for local hacking)
- A Google Maps Platform API key (Places, Weather, Elevation, JS API) - Overpass requires no key

### Backend setup

```bash
git clone https://github.com/racheltenenbaum/bright.git
cd bright
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```bash
DATABASE_URL=mysql://user:password@host:port/dbname
SECRET_KEY=<random secret for JWT signing>
GOOGLE_MAPS_API_KEY=<your Google Maps Platform key>
FRONTEND_URL=http://localhost:5173   # comma-separated for multiple origins
```

Run migrations and start the API:

```bash
alembic upgrade head
uvicorn src.main:app --reload
```

The API is now live at `http://localhost:8000` (interactive docs at `/docs`, health check at `/health`).

### Frontend setup

```bash
cd client
npm install
```

Create `client/.env`:

```bash
VITE_GOOGLE_MAPS_API_KEY=<your Google Maps JS key>
VITE_GOOGLE_MAPS_ID=<your Map ID, for styled/vector maps>
VITE_API_URL=http://localhost:8000
```

```bash
npm run dev
```

Visit `http://localhost:5173`.

## Running the mobile app (iOS)

bright ships as a native iOS app via Capacitor, reusing the same React build:

```bash
cd client
npm run build
npx cap sync ios
npx cap open ios   # opens the Xcode project
```

## Testing

Backend development follows **strict TDD** (see `CLAUDE.md`): tests are written first, confirmed failing, then implemented against - never the reverse.

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

Currently: **300+ tests, 99% statement coverage**, covering auth, routing/pathfinding, shadow geometry, rate limiting, and every router. Tests run against an isolated SQLite database with an autouse `clean_tables` fixture, and all outbound HTTP calls (Overpass, Google APIs) are mocked via `unittest.mock`.

## Deployment

Deployed on **Railway**:
- Backend: Dockerized FastAPI app (`Dockerfile` / `Procfile`), `nixpacks` build, `/health` healthcheck with auto-restart on failure
- Frontend: static Vite build
- Database: managed MySQL

Schema changes are managed with Alembic migrations, each paired with the equivalent raw SQL for direct application against the Railway MySQL instance.

## AI-assisted development

This project is built in close collaboration with **Claude Code**, using a set of project-specific configurations that shape how AI-assisted changes are made:

- **`CLAUDE.md`** - enforces strict test-driven development for all backend feature work: write failing pytest tests first, implement to green, then verify coverage stays ≥99% before anything is marked done.
- **`.claude/commands/ship.md`** - a custom `/ship` slash command that automates the full release loop in one step: stage, commit (with a human-confirmed message), push, rebuild the frontend, sync the Capacitor iOS project, and restart the local dev server.

---

*bright - your sun companion, whether you love it or hide away.*
