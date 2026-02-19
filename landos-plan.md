# LandOS — Development Plan for Claude Code

## Context & Background

LandOS is an intelligence platform that helps Irish property developers find underutilized land opportunities. The core thesis: Irish real estate operates on a "Golf model" (relationships and intuition), and we're building the tools to shift it toward a "Moneyball model" (data and ontology). The value is hidden in the delta between a parcel's current use and its residual potential — a gap created by complex zoning, planning regulations, and market dynamics that no one has systematically mapped.

The founder has a Google product background, a technical co-founder, and ~20hrs/week bandwidth. Long-term vision is to become a "European Palantir" — a sovereign decision-making OS for physical assets across land, energy, infrastructure, and trade. But we're starting with one thing: a map of Dublin parcels scored by development potential.

---

## Data: What We Have & Where It Lives

### Layer 1 — Cadastral Parcels (THE FOUNDATION)

This is the base layer. Every registered land parcel in Ireland.

- **Source:** Tailte Éireann INSPIRE Cadastral Parcels
- **Cost:** FREE (CC BY 4.0)
- **Format:** GML (Geography Markup Language), ~7GB uncompressed
- **Coverage:** ~2 million parcels, all of Ireland
- **Download URL:** `https://te-inspire-atom.s3.eu-west-1.amazonaws.com/files/CP/`
  - `CP_IE_TE_CadastralParcelsFreehold.zip` — freehold parcels
  - `CP_IE_TE_CadastralParcelsLeasehold.zip` — leasehold parcels
- **Coordinate Reference System:** EPSG:4258 (ETRS89) — degrees lat/long
- **What it contains:** Polygon geometry for every registered land title boundary. This is the legal boundary of ownership — the spatial unit everything else attaches to.
- **Key field:** Each parcel has an `INSPIREID` and a `NATIONALCADASTRALREFERENCE` (which maps to the folio number in the Land Registry).

**Important notes:**
- The GML file is very large. Do NOT try to load the entire file into memory or render all polygons at once. It needs to go into a spatial database (PostGIS) and be served as tiles/viewport queries.
- For the initial prototype, we may want to clip to Dublin only to keep things manageable.
- To calculate accurate areas in square metres, geometries must be transformed to EPSG:2157 (Irish Transverse Mercator) before using area functions.
- For web map display, geometries should be served in or converted to EPSG:4326 (WGS84).

### Layer 2 — Development Plan Zoning (FUTURE — NOT YET IMPLEMENTED)

- **Source:** MyPlan.ie / data.gov.ie
- **Cost:** FREE
- **Format:** Shapefile / REST API
- **What it contains:** Zoning designation for every area — residential (Z1), mixed use (Z10), enterprise (Z6), regeneration (Z14), etc.
- **Why it matters:** When you overlay zoning on cadastral parcels, you can answer "what is this parcel allowed to become?" The delta between current use and zoned potential = development opportunity signal.

### Layer 3 — Planning Applications (FUTURE — NOT YET IMPLEMENTED)

- **Source:** Dublin City Council / Smart Dublin
- **Cost:** FREE
- **Format:** Shapefile + CSV
- **What it contains:** Every planning application in Dublin since 2003 — location, description, decision, date.
- **Why it matters:** No recent planning applications on a large residentially-zoned parcel = inactive owner = opportunity signal.

### Layer 4 — Property Prices / Comparables (FUTURE — NOT YET IMPLEMENTED)

- **Source:** Property Price Register (PSRA/Revenue) + user's own residential property dataset (sold + active listings)
- **Cost:** FREE (PPR) / proprietary (user data)
- **Format:** CSV (text addresses, needs geocoding)
- **What it matters:** Comparable sale prices within radius of a site let you estimate Gross Development Value (GDV) for feasibility calculation.

### Layer 5 — RZLT Maps (FUTURE — NOT YET IMPLEMENTED)

- **Source:** Each Local Authority
- **What it contains:** Land zoned residential + serviced, subject to 3% annual tax if undeveloped.
- **Why it matters:** Strongest "motivated seller" signal — owners paying 3% annually on idle land.

### Layer 6 — Derelict & Vacant Sites (FUTURE — NOT YET IMPLEMENTED)

- **Source:** Each Local Authority
- **What it contains:** Officially designated derelict/vacant sites with owner info.

### Layer 7 — Building Footprints (FUTURE — NOT YET IMPLEMENTED)

- **Source:** Tailte Éireann PRIME/DLM (licensed, ~365K buildings)
- **What it contains:** Physical building outlines. Building area vs parcel area = coverage ratio = underutilization signal.

### Layer 8 — Enrichment (Census, Flood Risk, Transport, Protected Structures) (FUTURE)

- Various free sources for feasibility filtering.

---

## Phase 1 Goal: Local Map Explorer with Cadastral Parcels

### What We're Building

A local web application that:

1. **Loads the INSPIRE cadastral parcel GML data into a PostGIS database**
2. **Serves a web map UI** where the user can:
   - See a base map (OpenStreetMap or similar)
   - Type in a location (address or area name in Dublin) and the map navigates there
   - See cadastral parcel boundaries overlaid on the map as the first layer
   - Click a parcel to see its details in a sidebar/popup (parcel ID, area, national cadastral reference)
3. **Architecture supports adding future layers** — zoning, planning, prices, etc. as toggle-able overlays

### Technical Architecture

```
┌─────────────────────────────────────────────────┐
│                  Web Browser                     │
│  ┌───────────────────────────────────────────┐  │
│  │         Map UI (Leaflet or MapLibre)       │  │
│  │  - OpenStreetMap base tiles                │  │
│  │  - Cadastral parcels as vector overlay     │  │
│  │  - Location search bar                     │  │
│  │  - Click-to-inspect sidebar                │  │
│  │  - Layer toggle panel (for future layers)  │  │
│  └───────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────┘
                     │ HTTP requests (GeoJSON for viewport)
                     │
┌────────────────────▼────────────────────────────┐
│              Backend API Server                   │
│  (Python/FastAPI or Node/Express)                │
│                                                   │
│  Endpoints:                                       │
│  GET /api/parcels?bbox=...    → parcels in view  │
│  GET /api/parcel/:id          → single parcel    │
│  GET /api/search?q=...        → geocode location │
│  GET /api/layers               → available layers│
│  (Future: GET /api/zoning, /api/planning, etc.)  │
└────────────────────┬────────────────────────────┘
                     │ SQL queries
                     │
┌────────────────────▼────────────────────────────┐
│              PostgreSQL + PostGIS                 │
│                                                   │
│  Tables:                                          │
│  - cadastral_freehold  (geom, id, area, ref...)  │
│  - cadastral_leasehold (geom, id, area, ref...)  │
│  (Future: zoning, planning_apps, prices, etc.)   │
│                                                   │
│  Spatial indexes on all geometry columns          │
│  Geometries stored in EPSG:4326 for web serving  │
│  Area calculations done via ST_Transform → 2157  │
└─────────────────────────────────────────────────┘
```

### Data Loading Pipeline

1. **Download** the cadastral GML files from the INSPIRE S3 bucket
2. **Load into PostGIS** using `ogr2ogr`:
   ```bash
   ogr2ogr -f "PostgreSQL" PG:"host=localhost dbname=landos user=postgres password=postgres" \
     CP_IE_TE_CadastralParcelsFreehold.gml \
     -nln cadastral_freehold \
     -lco SPATIAL_INDEX=YES \
     -t_srs EPSG:4326
   ```
3. **Optionally clip to Dublin** for faster initial development:
   ```sql
   -- Dublin bounding box approximately:
   -- West: -6.45, South: 53.22, East: -6.05, North: 53.45
   DELETE FROM cadastral_freehold
   WHERE NOT ST_Intersects(
     geom,
     ST_MakeEnvelope(-6.45, 53.22, -6.05, 53.45, 4326)
   );
   ```
4. **Add computed columns:**
   ```sql
   ALTER TABLE cadastral_freehold ADD COLUMN area_sqm DOUBLE PRECISION;
   UPDATE cadastral_freehold SET area_sqm = ST_Area(ST_Transform(geom, 2157));
   ```

### Map UI Requirements

- **Base map:** OpenStreetMap tiles (free, no API key needed) via Leaflet or MapLibre GL JS
- **Parcel overlay:** Vector polygons fetched as GeoJSON from the API, rendered on the map. Only fetch parcels within the current viewport (bounding box query). Don't render parcels at very low zoom levels — show them from zoom ~15 onwards.
- **Location search:** A search bar that takes a text input (e.g. "Stoneybatter", "Manor Street Dublin 7") and geocodes it to coordinates, then flies the map to that location. Use Nominatim (OpenStreetMap's free geocoder) for this.
- **Parcel interaction:** Click a parcel polygon → highlight it → show a sidebar or popup with:
  - Parcel ID / National Cadastral Reference
  - Calculated area (square metres and acres)
  - Parcel type (freehold/leasehold)
  - (Future: zoning, planning history, nearby prices, opportunity score)
- **Layer toggle panel:** A UI panel (could be a simple sidebar or floating panel) with checkboxes for each data layer. For now, only "Cadastral Parcels" is available, but the architecture should make it trivial to add "Zoning", "Planning Applications", "Price Heatmap" etc. as future toggleable layers.
- **Styling:** Parcel boundaries as semi-transparent polygons with visible outlines. Different colours for freehold vs leasehold. Nothing fancy needed yet — functional over beautiful.

### Key Technical Decisions

- **PostGIS over flat files:** The GML is 7GB with 2M+ polygons. You can't load this into a browser or even into QGIS comfortably. PostGIS with spatial indexes lets you query just the parcels in the current viewport in milliseconds.
- **GeoJSON API over vector tiles (for now):** Vector tiles (MVT) are the production-grade approach but add complexity. For a local prototype with Dublin-only data, fetching GeoJSON for the viewport bbox is simpler and sufficient. The API can be upgraded to serve MVT later.
- **Leaflet or MapLibre GL JS:** Either works. Leaflet is simpler to get started; MapLibre is more performant for large vector datasets. Developer's choice.
- **Python/FastAPI or Node/Express for API:** Either works. FastAPI with psycopg2/asyncpg is probably fastest to prototype if the developer is comfortable with Python. The API layer is thin — just translating bbox queries to PostGIS SQL and returning GeoJSON.

### Coordinate Reference Systems (Important)

- **EPSG:4258 (ETRS89):** What the INSPIRE data comes in. Degrees lat/long, European standard.
- **EPSG:4326 (WGS84):** What web maps use. Almost identical to ETRS89 for Ireland — safe to store as 4326.
- **EPSG:2157 (Irish Transverse Mercator):** Ireland's national projection, in metres. Use this for accurate area/distance calculations via `ST_Transform(geom, 2157)`.

### Success Criteria for Phase 1

- [ ] PostGIS database running locally with Dublin cadastral parcels loaded
- [ ] Web map opens in browser showing OpenStreetMap base layer centred on Dublin
- [ ] User can type a location and the map flies there
- [ ] Cadastral parcel boundaries appear as an overlay when zoomed in sufficiently
- [ ] Clicking a parcel shows its ID, area, and type
- [ ] Layer toggle UI exists (even if only one layer is active)
- [ ] Architecture is clean enough that adding a second layer (zoning) would be a matter of: load data into new PostGIS table → add API endpoint → add toggle in UI

---

## Future Phases (Not in Scope Now, But Design For Them)

### Phase 2: Zoning Overlay + "Lazy Land" Scoring
- Load MyPlan.ie zoning shapefiles into PostGIS
- Spatial join: each parcel gets its zoning designation
- Colour parcels by zone type on the map
- Basic scoring: large parcel + residential zone + no building = high score

### Phase 3: Planning History + Comparables
- Load DCC planning applications
- Spatial join: each parcel gets its planning history
- Load property prices, geocode, snap to parcels
- Click a parcel → see last planning app, nearby comps, rough GDV estimate

### Phase 4: Site Dossier Generation
- Click a high-scoring parcel → generate a 1-page feasibility memo
- AI-generated narrative combining all structured data layers
- Residual land value calculation

### Phase 5: AI Query Mode
- Natural language search bar: "Show me sites in Liberties over 0.15 hectares where last planning refused for height"
- LLM translates to PostGIS SQL → results rendered on map

---

## Database Schema (Extensible Design)

Design the schema so new layers are new tables that join spatially, not modifications to existing tables.

```sql
-- Core spatial tables (one per data layer)
CREATE TABLE cadastral_freehold (
    id SERIAL PRIMARY KEY,
    inspire_id TEXT,
    national_ref TEXT,  -- National Cadastral Reference (folio number)
    geom GEOMETRY(MultiPolygon, 4326),
    area_sqm DOUBLE PRECISION
);
CREATE INDEX idx_cadastral_freehold_geom ON cadastral_freehold USING GIST(geom);

CREATE TABLE cadastral_leasehold (
    id SERIAL PRIMARY KEY,
    inspire_id TEXT,
    national_ref TEXT,
    geom GEOMETRY(MultiPolygon, 4326),
    area_sqm DOUBLE PRECISION
);
CREATE INDEX idx_cadastral_leasehold_geom ON cadastral_leasehold USING GIST(geom);

-- Future tables follow same pattern:
-- CREATE TABLE zoning (id, zone_type, zone_name, geom GEOMETRY, ...);
-- CREATE TABLE planning_apps (id, app_ref, description, decision, date, geom GEOMETRY, ...);
-- CREATE TABLE property_prices (id, price, date, address, geom GEOMETRY(Point, 4326), ...);
-- etc.

-- Layers metadata table (drives the UI layer toggle)
CREATE TABLE layers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,           -- e.g. 'cadastral_freehold'
    display_name TEXT NOT NULL,   -- e.g. 'Cadastral Parcels (Freehold)'
    table_name TEXT NOT NULL,     -- actual PostGIS table name
    is_active BOOLEAN DEFAULT true,
    min_zoom INTEGER DEFAULT 15,  -- don't show below this zoom
    style JSONB                   -- colour, opacity, stroke etc.
);
```

---

## Key Spatial Operations Reference

These are the PostGIS functions that power everything:

```sql
-- Parcels within map viewport
SELECT id, national_ref, area_sqm, ST_AsGeoJSON(geom) as geometry
FROM cadastral_freehold
WHERE geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
LIMIT 500;

-- Accurate area in square metres
SELECT ST_Area(ST_Transform(geom, 2157)) FROM cadastral_freehold WHERE id = 1;

-- Spatial join: what zone is this parcel in? (future)
SELECT c.id, z.zone_type
FROM cadastral_freehold c
JOIN zoning z ON ST_Intersects(c.geom, z.geom);

-- Nearby comparables within 500m (future)
SELECT AVG(p.price_per_sqm)
FROM property_prices p
WHERE ST_DWithin(ST_Transform(p.geom, 2157), ST_Transform(:parcel_geom, 2157), 500);
```

---

## Environment Setup

The developer will need:
- **PostgreSQL 14+** with **PostGIS 3+** extension
- **GDAL/OGR** (`ogr2ogr` command) for loading GML into PostGIS
- **Node.js** or **Python 3.10+** for the API server
- A web browser

Docker option (recommended for consistency):
```bash
docker run --name landos-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=landos -p 5432:5432 -d postgis/postgis:16-3.4
```

---

## Summary

**Build this first:** A local web app with a PostGIS database of Dublin cadastral parcels, a map UI with location search, and clickable parcel boundaries. Layer toggle UI ready for future data layers. Nothing more.

**Why this is the right first step:** It proves the core technical pipeline (GML → PostGIS → API → Map) works. It gives the founder something to demo to developers. And the layered architecture means every future capability (zoning, planning, scoring, AI) is just "load more data + add an endpoint + add a toggle."
