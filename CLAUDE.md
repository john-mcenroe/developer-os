# CLAUDE.md — LandOS Development Guide

## Project Overview

LandOS is a land intelligence platform for Irish property developers. It combines cadastral data, zoning, planning history, and market data into a spatial intelligence system to find underutilized land opportunities.

**Core thesis:** Irish real estate runs on relationships ("Golf model"). LandOS shifts it to data ("Moneyball model") by systematically mapping the delta between a parcel's current use and its residual potential.

## Tech Stack

- **Frontend:** JavaScript (Leaflet/MapLibre for mapping)
- **Backend:** Python FastAPI
- **Database:** PostgreSQL + PostGIS
- **Data Sources:** Irish government geospatial datasets (Tailte Éireann INSPIRE, MyPlan.ie, DCC planning apps, Property Price Register)

## Key Files

- `frontend/` — Web UI (map interface): `app.js`, `index.html`, `style.css`
- `backend/` — API server: `main.py`, `db.py`, `requirements.txt`
- `landos-plan.md` — Detailed technical plan, data loading pipeline, schema, spatial operations reference
- `docker-compose.yml` — Local dev environment (PostGIS)

## Running Locally

```bash
docker-compose up -d              # Start PostGIS
cd backend && python main.py      # Start API
# Open frontend/index.html in browser
```

## Product Direction

LandOS is evolving toward **"Claude Code for developers exploring a map"** — a chat-driven spatial intelligence tool where the AI helps developers find, research, and act on land opportunities.

### Interaction Model

**Chat is the primary interface.** The map visualizes what's happening as the user works through conversation. Think of it like Claude Code for software engineers, but for property developers exploring geography and finding plots.

- Chat-based queries drive exploration and analysis
- The map updates in real-time to reflect what's being discussed
- Users can open new map experiences/sessions
- The AI can reason about boundary data, spatial relationships, and opportunity signals
- Queries translate to PostGIS SQL under the hood (indexed for performance)

### Entity Taxonomy

We have a taxonomy of entities that are aggregated, visualized, and help organize focus:

**Core entities:**
- **Properties (sites)** — Individual parcels/plots of land
- **Areas** — Geographic regions, neighborhoods, zones
- **Nearby attributes** — Businesses, property prices, public transport, amenities

**Data layers that attach to entities:**
- Zoning designations
- Parcels of land (cadastral boundaries)
- Sold properties (price register + scraped listings)
- Planning permissions (residential/commercial)
- Census data (demographics)

### User Journey (Progressive Depth)

Design for a lightweight-to-deep workflow. Don't impose organization on the user — let them go deeper naturally:

1. **Save** — Lightweight bookmark/save of interesting sites or areas. Zero friction to start.
2. **Research** — Dig deeper into saved items. Layer on data, comparables, planning history.
3. **Action** — Move toward development. Feasibility, dossier generation, next steps.

### Use Cases

The three interaction patterns map to entity selection:

| Action | Trigger | What happens |
|--------|---------|--------------|
| **Action** | Select a site | Take action on a specific property (feasibility, dossier) |
| **Research** | Select multiple sites | Compare and research a set of properties |
| **Explore** | Select an area | AI-driven exploration of opportunities in a region |

**Explore mode** is where the query engine shines: the user writes a goal (e.g., "Find residential sites over 0.15ha in Liberties with no recent planning") and the AI explores opportunities and surfaces results on the map.

### Success Metrics

- Developer finds a site worth exploring (residential or commercial)
- Developer researches a site (layers of data, comparables, history)
- Developer actions a site (development process begins)

### Target User

Property developers — people looking for sites to develop, researching sites they want to develop, and managing the development process itself.

## Development Principles

- **Iterate incrementally.** This direction doesn't need to ship all at once. Each feature should work standalone and layer toward the full vision.
- **Map is the visualization layer, chat is the interaction layer.** Don't build complex map-native UI controls when a chat command would be simpler.
- **Don't organize for the user.** Keep the save/research/action flow lightweight. No folders, no categories, no mandatory fields.
- **SQL-first for spatial queries.** The AI translates natural language to PostGIS SQL. Build and index queries that support the common patterns.
- **Boundary-aware.** The system should understand and reason about geographic boundaries — parcel edges, zoning borders, area boundaries, proximity.

## Technical Notes

- Geometries stored in EPSG:4326 (WGS84) for web display
- Area/distance calculations use ST_Transform to EPSG:2157 (Irish Transverse Mercator)
- The cadastral GML is ~7GB / 2M+ polygons — always query via PostGIS spatial index, never load fully into memory
- See `landos-plan.md` for full schema, spatial operations reference, and data loading pipeline
