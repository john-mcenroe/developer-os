# LandOS — Land Intelligence for Irish Property Development

LandOS is an intelligence platform that helps Irish property developers find underutilized land opportunities. We're building a "Moneyball" approach to Irish real estate by combining cadastral data, zoning information, and planning history into a spatial intelligence system.

## Project Overview

**Long-term Vision:** A "European Palantir" for decision-making on physical assets (land, energy, infrastructure, trade).

**Current Focus:** Phase 1 — A local web application that visualizes Dublin cadastral parcels on an interactive map with location search and parcel inspection capabilities.

### Core Thesis

The Irish property market operates on relationships and intuition ("Golf model"). The opportunity is in the delta between a parcel's current use and its residual potential—a gap created by zoning, planning regulations, and market dynamics. LandOS systematically maps this gap using open data.

## Tech Stack

- **Frontend:** JavaScript (Leaflet/MapLibre for mapping)
- **Backend:** Python (FastAPI or similar)
- **Database:** PostgreSQL + PostGIS (spatial data)
- **Data Sources:** Free Irish government geospatial datasets (Tailte Éireann INSPIRE, MyPlan.ie, DCC planning apps)

## Project Structure

```
.
├── frontend/              # Web UI (map interface)
│   ├── app.js
│   ├── index.html
│   └── style.css
├── backend/               # API server
│   ├── main.py
│   ├── db.py
│   └── requirements.txt
├── dlrplanningapps/       # Sample planning data (shapefiles)
├── docker-compose.yml     # Local development environment
└── landos-plan.md         # Detailed development plan
```

## Getting Started

### Prerequisites

- **PostgreSQL 14+** with **PostGIS 3+** extension
- **Python 3.10+**
- **Node.js** (if using Node for the frontend)
- **Docker** (optional, recommended for database)

### Local Setup

1. **Start the database** (using Docker):
   ```bash
   docker-compose up -d
   ```

2. **Install backend dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Start the API server:**
   ```bash
   python main.py
   ```

4. **Open the frontend:**
   Open `frontend/index.html` in a web browser

### Data: What We Have

| Layer | Source | Status | What It Contains |
|-------|--------|--------|------------------|
| **Cadastral Parcels** | Tailte Éireann INSPIRE | ✅ Available | 2M+ registered land parcels (legal boundaries) |
| **Zoning (MyPlan)** | MyPlan.ie | 🔄 Planned | Zoning designations (residential, enterprise, etc.) |
| **Planning Applications** | Dublin City Council | 🔄 Planned | Planning history since 2003 |
| **Property Prices** | Property Price Register | 🔄 Planned | Comparable sales data |
| **Building Footprints** | Tailte Éireann PRIME | 🔄 Planned | Physical building outlines |

## Phase 1 Goals

- [ ] PostGIS database with Dublin cadastral parcels
- [ ] Web map showing OpenStreetMap base layer
- [ ] Location search (geocoding via Nominatim)
- [ ] Cadastral parcel overlay with click inspection
- [ ] Layer toggle UI (ready for future data)
- [ ] Clean architecture for adding future layers

## Key Technical Decisions

### PostGIS for Spatial Data
The cadastral GML file is ~7GB with 2M+ polygons. PostGIS with spatial indexes enables millisecond viewport queries without loading everything into memory.

### GeoJSON API (for now)
Vector tiles (MVT) are more performant, but GeoJSON from a simple API is sufficient for initial development. Can upgrade to MVT later.

### Extensible Schema
Each data layer is a separate PostGIS table. Adding "zoning" or "planning" layers is: load data → add API endpoint → add UI toggle.

## Database Schema Overview

```sql
-- Cadastral parcels (freehold and leasehold)
CREATE TABLE cadastral_freehold (
    id SERIAL PRIMARY KEY,
    inspire_id TEXT,
    national_ref TEXT,  -- National Cadastral Reference (folio number)
    geom GEOMETRY(MultiPolygon, 4326),
    area_sqm DOUBLE PRECISION
);

-- Layer metadata (drives UI toggles)
CREATE TABLE layers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    min_zoom INTEGER DEFAULT 15,
    style JSONB
);
```

## Coordinate Reference Systems

- **EPSG:4258 (ETRS89):** INSPIRE data standard (degrees lat/long)
- **EPSG:4326 (WGS84):** Web maps standard
- **EPSG:2157 (ITM):** Ireland's national projection — use for accurate area/distance calculations

## API Endpoints (Planned)

```
GET /api/parcels?bbox=west,south,east,north   → Parcels in viewport
GET /api/parcel/:id                             → Single parcel details
GET /api/search?q=location_name                 → Geocode location
GET /api/layers                                 → Available data layers
```

## Future Phases

### Phase 2: Zoning Overlay + Opportunity Scoring
- Load MyPlan.ie zoning data
- Spatial join zoning to cadastral parcels
- Score parcels: large + residential zone + no building = high opportunity

### Phase 3: Planning & Comparables
- Load DCC planning applications (2003–present)
- Geocode and join property prices to parcels
- Calculate rough GDV estimates

### Phase 4: Site Dossier Generation
- Click a high-scoring parcel → generate 1-page feasibility memo
- AI-generated narrative combining all layers

### Phase 5: AI Query Mode
- "Show me sites in Liberties over 0.15 hectares where last planning was refused for height"
- LLM translates natural language → PostGIS SQL → map visualization

## Key Resources

- **Tailte Éireann INSPIRE Data:** https://te-inspire-atom.s3.eu-west-1.amazonaws.com/files/CP/
- **MyPlan.ie Zoning:** https://www.myplan.ie/
- **DCC Planning Apps:** https://data.smartdublin.ie/
- **Property Price Register:** https://www.propertyprices.ie/
- **PostGIS Documentation:** https://postgis.net/documentation/

## Development Notes

See `landos-plan.md` for detailed technical specifications, spatial operations, and full schema design.

## Contributing

This is early-stage. Focus areas:
1. Get cadastral data loaded into PostGIS
2. Build the map UI with location search
3. Enable parcel interaction and inspection
4. Keep architecture clean for future layers

## License

Data sources are open (CC BY 4.0 from Tailte Éireann). Code license TBD.

---

**Built with the vision of shifting Irish property development from "Golf model" to "Moneyball model."**
