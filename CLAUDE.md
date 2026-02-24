# CLAUDE.md — LandOS Development Guide

## Project Overview

LandOS is a land intelligence platform for Irish property developers. It combines cadastral data, zoning, planning history, census demographics, and market data into a spatial intelligence system to find underutilized land opportunities.

**Core thesis:** Irish real estate runs on relationships ("Golf model"). LandOS shifts it to data ("Moneyball model") by systematically mapping the delta between a parcel's current use and its residual potential.

## Tech Stack

- **Frontend:** Vanilla JavaScript (MapLibre GL JS for mapping, no build step — CDN only)
- **Backend:** Python FastAPI (uvicorn)
- **Database:** PostgreSQL 16 + PostGIS 3.4
- **AI:** Google Gemini 2.0 Flash (hypothesis generation + results ranking)
- **Infrastructure:** Docker Compose (PostGIS container)
- **Data Sources:** Tailte Éireann INSPIRE cadastral, DLR planning apps, scraped property sales, Census 2022 (CSO), RZLT maps, urban area boundaries

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/app.js` | ~2,300 | Map, layers, chat UI, AI results, flyouts, keyboard shortcuts |
| `frontend/index.html` | ~156 | Single-page app DOM structure |
| `frontend/style.css` | Styles | Map + chat panel layout |
| `backend/main.py` | ~1,370 | FastAPI server: 20+ endpoints, 3-phase AI chat pipeline |
| `backend/db.py` | ~26 | PostgreSQL connection pooling (psycopg2) |
| `backend/.env` | Config | `GEMINI_API_KEY`, `DATABASE_URL` |
| `scripts/load_data.sh` | ~285 | Load cadastral, planning, sales data via ogr2ogr |
| `scripts/load_census.sh` | ~454 | Load Census 2022 demographics + urban areas |
| `docker-compose.yml` | ~20 | PostGIS 16-3.4 container (port 5433) |
| `landos-plan.md` | Plan | Original technical plan + schema + spatial ops reference |

## Running Locally

```bash
docker-compose up -d              # Start PostGIS (port 5433)
cd backend && python main.py      # Start API (port 8000)
# Open frontend/index.html in browser
```

## Current Implementation Status

### Data Layers Integrated (8 layers)

| Layer | Table | Source | Records | Status |
|-------|-------|--------|---------|--------|
| Cadastral Freehold | `cadastral_freehold` | Tailte Éireann INSPIRE | ~2M (Dublin clipped) | ✅ Live |
| Cadastral Leasehold | `cadastral_leasehold` | Tailte Éireann INSPIRE | Dublin subset | ✅ Live |
| RZLT Sites | `rzlt` | Local Authorities | ~4k sites | ✅ Live |
| DLR Planning (Polygons) | `dlr_planning_polygons` | Dublin City Council | ~15k features | ✅ Live |
| DLR Planning (Points) | `dlr_planning_points` | Dublin City Council | ~15k features | ✅ Live |
| Sold Properties | `sold_properties` | Property Price Register (PPR) + scraped listings | ~50k properties | ✅ Live |
| Census Small Areas | `census_small_areas` | CSO Census 2022 | ~4.6k Dublin areas | ✅ Live |
| Urban Area Boundaries | `urban_areas` | Tailte Éireann | ~11 Dublin areas | ✅ Live |

### API Endpoints

**Geospatial data** — bbox-based queries for all 8 layers:
- `GET /api/parcels`, `/api/parcels_leasehold`, `/api/rzlt`
- `GET /api/planning_apps`, `/api/planning_apps_points`
- `GET /api/sold_properties`, `/api/census_small_areas`, `/api/urban_areas`

**Analytics:**
- `GET /api/sold_stats` — Aggregated sale stats within circle (avg/median price, type breakdown, comparables)
- `GET /api/census_stats` — Census demographics within circle (population, tenure, age, education, employment)
- `GET /api/parcel/:id` — Full parcel details

**AI:**
- `POST /api/ai/chat` — 3-phase hypothesis-driven explore pipeline (Gemini)

**Utility:**
- `GET /api/search` — Geocoding via Nominatim
- `GET /api/layers` — Layer metadata
- `GET /health` — Health check

### Frontend Features

**Map:**
- 8-layer toggle system with zoom-dependent loading
- Circle analysis mode (click-drag radius → aggregate stats)
- Click-to-detail flyouts for all entity types
- Location search (Nominatim geocoding)

**Chat + AI:**
- Multi-session chat (localStorage persistence, sidebar history)
- 5 starter analysis templates (undervalued areas, RZLT, large sites, planning hotspots, price-per-sqm)
- AI results rendered as ranked cards (8-15 sites) + numbered map markers
- Keyboard navigation: arrows, j/k, number keys, Cmd+N, Cmd+K, Cmd+\
- Follow-up suggestions from AI

**AI Pipeline (backend):**
1. User query → Gemini generates 3-5 spatial hypotheses + PostGIS SQL
2. SQL executed safely (validation, timeout, row limits)
3. Gemini ranks best 8-15 sites by opportunity score

### Database Schema

All tables have GIST spatial indexes on geometry columns. Geometries stored in EPSG:4326 (WGS84). Area/distance calculations transform to EPSG:2157 (Irish Transverse Mercator).

Key tables: `cadastral_freehold`, `cadastral_leasehold`, `rzlt`, `dlr_planning_polygons`, `dlr_planning_points`, `sold_properties`, `census_small_areas`, `urban_areas`, `layers` (metadata).

Census demographics include: population, density, households, age bands, apartment %, tenure (owner/rented), vacancy %, education (3rd level), employment, WFH %, health stats.

## Product Direction

LandOS is evolving toward **"Claude Code for developers exploring a map"** — a chat-driven spatial intelligence tool where the AI helps developers find, research, and act on land opportunities.

### Interaction Model

**Chat is the primary interface.** The map visualizes what's happening as the user works through conversation.

- Chat-based queries drive exploration and analysis
- The map updates in real-time to reflect what's being discussed
- Users can open new sessions (multi-chat)
- The AI reasons about boundary data, spatial relationships, and opportunity signals
- Queries translate to PostGIS SQL under the hood (indexed for performance)

### Entity Taxonomy

**Core entities:**
- **Properties (sites)** — Individual parcels/plots of land
- **Areas** — Geographic regions, neighborhoods, zones
- **Nearby attributes** — Businesses, property prices, public transport, amenities

**Data layers that attach to entities:**
- Parcels of land (cadastral boundaries) ✅
- Sold properties (PPR + scraped listings with price/beds/baths/energy) ✅
- Planning permissions (DLR applications with decisions) ✅
- RZLT sites (motivated seller signal — 3% annual tax) ✅
- Census data (demographics, tenure, education, employment) ✅
- Zoning designations ❌ (not yet integrated)

### User Journey (Progressive Depth)

1. **Save** — Lightweight bookmark/save of interesting sites or areas. Zero friction.
2. **Research** — Dig deeper. Layer on data, comparables, planning history.
3. **Action** — Move toward development. Feasibility, dossier generation, next steps.

### Success Metrics

- Developer finds a site worth exploring (residential or commercial)
- Developer researches a site (layers of data, comparables, history)
- Developer actions a site (development process begins)

### Target User

Property developers — people looking for sites to develop, researching sites they want to develop, and managing the development process.

## Development Principles

- **Iterate incrementally.** Each feature should work standalone and layer toward the full vision.
- **Map is the visualization layer, chat is the interaction layer.** Don't build complex map-native UI controls when a chat command would be simpler.
- **Don't organize for the user.** Keep the save/research/action flow lightweight.
- **SQL-first for spatial queries.** The AI translates natural language to PostGIS SQL.
- **Boundary-aware.** The system should reason about geographic boundaries — parcel edges, zoning borders, area boundaries, proximity.

## Technical Notes

- Geometries stored in EPSG:4326 (WGS84) for web display
- Area/distance calculations use ST_Transform to EPSG:2157 (Irish Transverse Mercator)
- The cadastral GML is ~7GB / 2M+ polygons — always query via PostGIS spatial index, never load fully into memory
- Frontend uses MapLibre GL JS (more performant than Leaflet for large vector datasets)
- AI model is Gemini 2.0 Flash with forced JSON output via `responseMimeType`
- Chat persistence is localStorage (no backend auth needed yet)
- See `landos-plan.md` for original schema design and spatial operations reference
