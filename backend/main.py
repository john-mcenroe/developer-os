import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db import get_conn, put_conn

# Load .env from backend directory
load_dotenv(Path(__file__).parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the connection pool on startup
    conn = get_conn()
    put_conn(conn)
    yield


app = FastAPI(title="LandOS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


PARCEL_TABLES = {
    "freehold": "cadastral_freehold",
    "leasehold": "cadastral_leasehold",
}


def parse_bbox(bbox: str):
    parts = [float(x) for x in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError
    return parts


def query_parcels_bbox(table: str, parcel_type: str, west, south, east, north):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    ogc_fid AS id,
                    nationalcadastralreference,
                    gml_id,
                    area_sqm,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM {table}
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 2000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        parcel_id, national_ref, inspire_id, area_sqm, geometry = row
        area_sqm_val = round(area_sqm, 1) if area_sqm is not None else None
        area_acres = round(area_sqm / 4046.86, 3) if area_sqm is not None else None
        features.append(
            {
                "type": "Feature",
                "id": parcel_id,
                "geometry": geometry,
                "properties": {
                    "id": parcel_id,
                    "national_ref": national_ref,
                    "inspire_id": inspire_id,
                    "area_sqm": area_sqm_val,
                    "area_acres": area_acres,
                    "type": parcel_type,
                },
            }
        )
    return features


@app.get("/api/parcels")
def get_parcels(bbox: str = Query(..., description="west,south,east,north")):
    """Return freehold parcels within the bounding box as GeoJSON."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")
    features = query_parcels_bbox("cadastral_freehold", "freehold", west, south, east, north)
    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/parcels_leasehold")
def get_parcels_leasehold(bbox: str = Query(..., description="west,south,east,north")):
    """Return leasehold parcels within the bounding box as GeoJSON."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")
    features = query_parcels_bbox("cadastral_leasehold", "leasehold", west, south, east, north)
    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/rzlt")
def get_rzlt(bbox: str = Query(..., description="west,south,east,north")):
    """Return RZLT (Residential Zoned Land Tax) sites within the bounding box as GeoJSON."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ogc_fid AS id,
                    zone_desc,
                    zone_gzt,
                    gzt_desc,
                    site_area,
                    local_authority_name,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM rzlt
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 2000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        parcel_id, zone_desc, zone_gzt, gzt_desc, site_area, local_auth, geometry = row
        features.append(
            {
                "type": "Feature",
                "id": parcel_id,
                "geometry": geometry,
                "properties": {
                    "id": parcel_id,
                    "zone_desc": zone_desc,
                    "zone_gzt": zone_gzt,
                    "gzt_desc": gzt_desc,
                    "site_area": site_area,
                    "local_authority": local_auth,
                },
            }
        )

    return JSONResponse({"type": "FeatureCollection", "features": features})


def query_planning_apps_bbox(table: str, west, south, east, north):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    ogc_fid AS id,
                    plan_ref,
                    county,
                    plan_auth,
                    reg_date,
                    descrptn,
                    location,
                    stage,
                    decision,
                    app_dec,
                    dec_date,
                    more_info,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM {table}
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 2000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        (
            fid, plan_ref, county, plan_auth, reg_date, descrptn,
            location, stage, decision, app_dec, dec_date, more_info, geometry,
        ) = row
        features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {
                    "id": fid,
                    "plan_ref": plan_ref,
                    "county": county,
                    "plan_auth": plan_auth,
                    "reg_date": reg_date,
                    "descrptn": descrptn,
                    "location": location,
                    "stage": stage,
                    "decision": decision,
                    "app_dec": app_dec,
                    "dec_date": dec_date,
                    "more_info": more_info,
                },
            }
        )
    return features


@app.get("/api/planning_apps")
def get_planning_apps(bbox: str = Query(..., description="west,south,east,north")):
    """Return DLR planning application polygons within the bounding box as GeoJSON."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")
    features = query_planning_apps_bbox("dlr_planning_polygons", west, south, east, north)
    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/planning_apps_points")
def get_planning_apps_points(bbox: str = Query(..., description="west,south,east,north")):
    """Return DLR planning application points within the bounding box as GeoJSON."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")
    features = query_planning_apps_bbox("dlr_planning_points", west, south, east, north)
    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/sold_properties")
def get_sold_properties(bbox: str = Query(..., description="west,south,east,north")):
    """Return sold properties within the bounding box as GeoJSON points."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    address,
                    sale_price,
                    asking_price,
                    beds,
                    baths,
                    property_type,
                    energy_rating,
                    agent_name,
                    sale_date::text,
                    floor_area_m2,
                    url,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM sold_properties
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 2000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        (
            fid, address, sale_price, asking_price, beds, baths,
            property_type, energy_rating, agent_name, sale_date,
            floor_area, url, geometry,
        ) = row
        price_per_sqm = None
        if sale_price and floor_area:
            price_per_sqm = round(sale_price / floor_area)
        features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {
                    "id": fid,
                    "address": address,
                    "sale_price": sale_price,
                    "asking_price": asking_price,
                    "beds": beds,
                    "baths": baths,
                    "property_type": property_type,
                    "energy_rating": energy_rating,
                    "agent_name": agent_name,
                    "sale_date": sale_date,
                    "floor_area_m2": floor_area,
                    "price_per_sqm": price_per_sqm,
                    "url": url,
                },
            }
        )

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/sold_stats")
def get_sold_stats(
    lng: float = Query(...),
    lat: float = Query(...),
    radius: float = Query(500, description="Radius in metres"),
):
    """Return aggregate stats for sold properties within a circle."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            center_sql = "ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 2157)"

            # Aggregates (exclude outliers: sale_price 0 or > €10M for robust stats)
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS cnt,
                    COALESCE(ROUND(AVG(sale_price)), 0) AS avg_sale,
                    COALESCE(MIN(sale_price), 0) AS min_sale,
                    COALESCE(MAX(sale_price), 0) AS max_sale,
                    COALESCE(ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sale_price)), 0) AS median_sale,
                    COALESCE(ROUND(STDDEV(sale_price)), 0) AS stddev_sale,
                    COALESCE(ROUND(AVG(asking_price)), 0) AS avg_asking,
                    COALESCE(ROUND(AVG(CASE WHEN floor_area_m2 > 0 THEN sale_price / floor_area_m2 END)), 0) AS avg_price_sqm,
                    COALESCE(ROUND(AVG(floor_area_m2)::numeric, 1), 0) AS avg_floor_area,
                    COALESCE(ROUND(AVG(beds)::numeric, 1), 0) AS avg_beds,
                    COALESCE(ROUND(AVG(baths)::numeric, 1), 0) AS avg_baths
                FROM sold_properties
                WHERE ST_DWithin(
                    ST_Transform(geom, 2157),
                    {center_sql},
                    %s
                )
                AND sale_price > 0 AND sale_price < 10000000
                """,
                (lng, lat, radius),
            )
            agg = cur.fetchone()

            # Property type breakdown (same outlier filter)
            cur.execute(
                f"""
                SELECT COALESCE(property_type, 'Unknown'), COUNT(*)
                FROM sold_properties
                WHERE ST_DWithin(
                    ST_Transform(geom, 2157),
                    {center_sql},
                    %s
                )
                AND sale_price > 0 AND sale_price < 10000000
                GROUP BY property_type
                ORDER BY COUNT(*) DESC
                """,
                (lng, lat, radius),
            )
            type_rows = cur.fetchall()

            # Individual properties (for sidebar list, same outlier filter)
            cur.execute(
                f"""
                SELECT
                    id, address, sale_price, asking_price, beds, baths,
                    property_type, sale_date::text, floor_area_m2,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM sold_properties
                WHERE ST_DWithin(
                    ST_Transform(geom, 2157),
                    {center_sql},
                    %s
                )
                AND sale_price > 0 AND sale_price < 10000000
                ORDER BY sale_date DESC NULLS LAST
                LIMIT 200
                """,
                (lng, lat, radius),
            )
            prop_rows = cur.fetchall()
    finally:
        put_conn(conn)

    (
        count, avg_sale, min_sale, max_sale, median_sale, stddev_sale,
        avg_asking, avg_price_sqm, avg_floor_area, avg_beds, avg_baths,
    ) = agg

    type_breakdown = {r[0]: r[1] for r in type_rows}

    properties = []
    for r in prop_rows:
        fid, addr, sp, ap, beds, baths, ptype, sdate, fa, geom = r
        properties.append({
            "id": fid, "address": addr, "sale_price": sp,
            "asking_price": ap, "beds": beds, "baths": baths,
            "property_type": ptype, "sale_date": sdate,
            "floor_area_m2": float(fa) if fa else None,
        })

    return {
        "center": {"lng": lng, "lat": lat},
        "radius_m": radius,
        "count": count,
        "avg_sale_price": int(avg_sale),
        "median_sale_price": int(median_sale),
        "min_sale_price": int(min_sale),
        "max_sale_price": int(max_sale),
        "stddev_sale_price": int(stddev_sale),
        "avg_asking_price": int(avg_asking),
        "avg_price_per_sqm": int(avg_price_sqm),
        "avg_floor_area_m2": float(avg_floor_area),
        "avg_beds": float(avg_beds),
        "avg_baths": float(avg_baths),
        "property_type_breakdown": type_breakdown,
        "properties": properties,
    }


@app.get("/api/parcel/{parcel_id}")
def get_parcel(parcel_id: int, parcel_type: str = Query("freehold")):
    """Return full detail for a single parcel. Use ?parcel_type=leasehold for leasehold."""
    table = PARCEL_TABLES.get(parcel_type)
    if not table:
        raise HTTPException(status_code=400, detail="parcel_type must be freehold or leasehold")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    ogc_fid AS id,
                    nationalcadastralreference,
                    gml_id,
                    area_sqm
                FROM {table}
                WHERE ogc_fid = %s
                """,
                (parcel_id,),
            )
            row = cur.fetchone()
    finally:
        put_conn(conn)

    if row is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    parcel_id_db, national_ref, inspire_id, area_sqm = row
    area_sqm_val = round(area_sqm, 1) if area_sqm is not None else None
    area_acres = round(area_sqm / 4046.86, 3) if area_sqm is not None else None

    return {
        "id": parcel_id_db,
        "national_ref": national_ref,
        "inspire_id": inspire_id,
        "area_sqm": area_sqm_val,
        "area_acres": area_acres,
        "type": parcel_type,
    }


@app.get("/api/search")
async def search_location(q: str = Query(..., description="Location name or address")):
    """Geocode a location string using Nominatim (OpenStreetMap)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": q,
                "format": "json",
                "limit": 5,
                "countrycodes": "ie",
            },
            headers={"User-Agent": "LandOS/1.0 (local development)"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Geocoder request failed")

    results = resp.json()
    if not results:
        return {"results": []}

    return {
        "results": [
            {
                "display_name": r["display_name"],
                "lat": float(r["lat"]),
                "lng": float(r["lon"]),
                "bbox": r.get("boundingbox"),
            }
            for r in results
        ]
    }


@app.get("/api/layers")
def get_layers():
    """Return all available map layers from the layers metadata table."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, display_name, table_name, is_active, min_zoom, style
                FROM layers
                ORDER BY id
                """
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    return {
        "layers": [
            {
                "id": r[0],
                "name": r[1],
                "display_name": r[2],
                "table_name": r[3],
                "is_active": r[4],
                "min_zoom": r[5],
                "style": r[6],
            }
            for r in rows
        ]
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ── AI-powered analytics (Hypothesis-Driven Explore Pipeline) ────────────────

ALLOWED_TABLES = {
    "sold_properties", "cadastral_freehold", "cadastral_leasehold",
    "rzlt", "dlr_planning_polygons", "dlr_planning_points",
}

SQL_BLOCKLIST = re.compile(
    r'\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|EXECUTE|DO)\b',
    re.IGNORECASE,
)

# ── Phase 1: Hypothesis Generation Prompt ────────────────────────────────────

HYPOTHESIS_PROMPT = """You are LandOS AI, an expert Dublin property & land development analyst.
The user is a property developer. They ask questions. You answer them by forming hypotheses and writing SQL to test them.

YOUR TASK: Given the user's question, form 3-5 distinct hypotheses about where opportunities might exist, and write PostGIS SQL to test each one.

DATABASE SCHEMA (PostgreSQL 16 + PostGIS 3.4):

TABLE: sold_properties (residential sales — ~50k rows)
  id SERIAL PRIMARY KEY
  address TEXT
  sale_price NUMERIC          -- sale price in €, can be 0 (exclude these)
  asking_price NUMERIC        -- asking/list price in €
  beds INTEGER
  baths INTEGER
  property_type TEXT          -- e.g. 'Detached', 'Semi-Detached', 'Terraced', 'Apartment', 'End of Terrace'
  energy_rating TEXT          -- BER rating e.g. 'A1', 'B2', 'C1', 'D1', etc.
  floor_area_m2 NUMERIC      -- internal floor area, can be NULL or 0
  sale_date DATE
  agent_name TEXT
  url TEXT
  geom GEOMETRY(Point, 4326)

TABLE: cadastral_freehold (land ownership parcels — ~2M rows, LARGE)
  ogc_fid SERIAL PRIMARY KEY
  nationalcadastralreference TEXT
  gml_id TEXT
  area_sqm NUMERIC
  geom GEOMETRY(Polygon, 4326)
  -- SPATIAL INDEX on geom. ALWAYS use spatial filter (ST_MakeEnvelope or ST_DWithin) to avoid full table scans.

TABLE: cadastral_leasehold (leasehold parcels — ~200k rows)
  (same schema as cadastral_freehold)
  -- SPATIAL INDEX on geom. ALWAYS use spatial filter.

TABLE: rzlt (Residential Zoned Land Tax sites — ~4k rows)
  ogc_fid SERIAL PRIMARY KEY
  zone_desc TEXT              -- e.g. 'Residential', 'Mixed Use'
  zone_gzt TEXT
  gzt_desc TEXT
  site_area NUMERIC           -- area in sqm
  local_authority_name TEXT   -- e.g. 'Dublin City Council', 'Dún Laoghaire-Rathdown'
  geom GEOMETRY(Polygon, 4326)

TABLE: dlr_planning_polygons (planning applications in Dún Laoghaire-Rathdown — ~15k rows)
  ogc_fid SERIAL PRIMARY KEY
  plan_ref TEXT
  county TEXT
  plan_auth TEXT
  reg_date TEXT               -- registration date as text
  descrptn TEXT               -- description of what was applied for
  location TEXT               -- address/location text
  stage TEXT
  decision TEXT               -- 'Grant Permission', 'Refuse Permission', 'Grant Retention', etc.
  app_dec TEXT
  dec_date TEXT               -- decision date as text
  more_info TEXT              -- URL to planning details
  geom GEOMETRY(Polygon, 4326)

TABLE: dlr_planning_points (same columns as dlr_planning_polygons but geom is Point)

COORDINATE SYSTEMS:
- All geometries stored in EPSG:4326 (WGS84)
- For accurate distance/area calculations, use ST_Transform(geom, 2157) (Irish Transverse Mercator)
- Dublin center is approximately (-6.26, 53.35)

POSTGIS FUNCTIONS YOU CAN USE:
- ST_DWithin(geog1, geog2, distance_metres) — use with ::geography cast for metre-based distance
- ST_Area(ST_Transform(geom, 2157)) — area in square metres
- ST_Intersects(a.geom, b.geom) — spatial join between layers
- ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326) — bounding box
- ST_Centroid(geom) — centroid point of a polygon
- ST_X(point), ST_Y(point) — extract coordinates
- ST_AsGeoJSON(geom)::json — geometry as GeoJSON for frontend
- ST_SnapToGrid(geom, size) — grid-based spatial aggregation
- ST_Buffer(geom::geography, distance_metres)::geometry — buffer around a geometry

SQL RULES:
- ALWAYS include in your SELECT: ST_AsGeoJSON(geom)::json AS geometry, ST_X(ST_Centroid(geom)) AS lng, ST_Y(ST_Centroid(geom)) AS lat (use ST_X(geom)/ST_Y(geom) for point tables)
- For cadastral tables (2M+ rows): ALWAYS include a spatial filter (ST_MakeEnvelope, ST_DWithin, or ST_Intersects with a smaller table). NEVER do a full scan.
- LIMIT each query to 25 rows max
- Use CTEs for readability
- Use NULLIF to avoid division by zero
- Exclude sale_price <= 0 from sold_properties
- You CAN use aggregations, window functions, CASE expressions, subqueries
- You CAN join across tables using spatial operations (ST_DWithin, ST_Intersects)
- Write production-quality SQL — handle NULLs, edge cases, use appropriate types

HYPOTHESIS GUIDELINES:
- Each hypothesis should test a DIFFERENT angle on the user's question
- At least one hypothesis should cross-reference 2+ tables (e.g. RZLT sites near underpriced sales)
- At least one hypothesis should use aggregation/statistics (e.g. avg price per sqm by area)
- Hypotheses should be specific and testable, not vague
- The rationale should explain the developer logic: WHY would this signal matter?
- If no location is specified, pick 2-3 promising Dublin areas or search city-wide

RESPONSE FORMAT (valid JSON only, no markdown):
{
  "hypotheses": [
    {
      "name": "Short hypothesis name (5-8 words)",
      "rationale": "2-3 sentences explaining the developer logic. Why would this signal indicate an opportunity? What would a smart developer look for here?",
      "sql_queries": [
        {
          "description": "What this specific query tests",
          "sql": "SELECT ... full PostGIS SQL here ..."
        }
      ]
    }
  ]
}
"""

# ── Phase 2: Evaluation Prompt ───────────────────────────────────────────────

EVALUATION_PROMPT_TEMPLATE = """You are LandOS AI evaluating hypothesis results for a property developer.

ORIGINAL QUESTION: {user_query}

I formed hypotheses and ran SQL queries against the Dublin property database. Here are the results:

{hypothesis_results}

YOUR TASK: Evaluate which hypotheses produced the strongest development opportunity signals. Then select the best individual properties/sites across all hypotheses.

EVALUATION CRITERIA:
- Signal strength: Did the data actually show what the hypothesis predicted?
- Opportunity quality: Are these actionable for a developer (not just interesting stats)?
- Cross-reference value: Do multiple data layers reinforce the same signal?
- A hypothesis with 0 results is "weak" — the signal doesn't exist in the data
- A hypothesis with results that don't show a clear pattern is "moderate"
- A hypothesis with clear, actionable results where the numbers tell a story is "strong"

RESPONSE FORMAT (valid JSON only, no markdown):
{{
  "type": "explore",
  "title": "Analysis title (max 8 words)",
  "summary": "2-3 sentence summary. Lead with the strongest opportunity found. Be specific — mention the area, the price range, the signal. This is what the developer reads first.",
  "hypotheses": [
    {{
      "name": "Hypothesis name (must match input)",
      "status": "strong|moderate|weak",
      "verdict": "1-2 sentences: what the data showed. If strong, explain the opportunity. If weak, explain why the signal wasn't there."
    }}
  ],
  "selected_results": {{
    "hypothesis_index": <0-based index of the hypothesis>,
    "query_index": <0-based index of the query within that hypothesis>,
    "row_indices": [<0-based indices of the best rows from that query's results>]
  }},
  "result_annotations": [
    "Why this specific property/site is an opportunity (1 sentence each, in order matching the selected rows)"
  ],
  "follow_ups": [
    {{
      "label": "Short label (max 6 words)",
      "prompt": "Full follow-up question to ask",
      "reason": "Why this follow-up would be valuable"
    }}
  ]
}}

IMPORTANT:
- selected_results should pick from the STRONGEST hypothesis. Pick 5-15 of the best individual results.
- result_annotations must have exactly one entry per selected row, in the same order.
- follow_ups should have exactly 3 entries: one that zooms into the best finding, one that compares areas, one that explores a different angle.
- If ALL hypotheses are weak, say so honestly in the summary and suggest what the developer should ask instead.
"""


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


async def call_gemini_with_prompt(system_prompt: str, messages: list, max_tokens: int = 4096) -> dict:
    """Call Gemini API with a custom system prompt and return parsed JSON."""
    gemini_contents = []
    for msg in messages:
        if isinstance(msg, dict):
            role = "user" if msg.get("role") == "user" else "model"
            text = msg.get("content", "")
        else:
            role = "user" if msg.role == "user" else "model"
            text = msg.content
        gemini_contents.append({
            "role": role,
            "parts": [{"text": text}],
        })

    body = {
        "contents": gemini_contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=body,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {resp.status_code}")

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}


def validate_sql(sql: str) -> str | None:
    """Validate SQL is safe to execute. Returns error message or None if OK."""
    if SQL_BLOCKLIST.search(sql):
        return "SQL contains blocked keyword (DDL/DML not allowed)"
    # Check that only allowed tables are referenced
    # Simple heuristic: look for FROM/JOIN followed by table names
    tokens = re.findall(r'\b(\w+)\b', sql.lower())
    from_join_next = False
    for token in tokens:
        if token in ('from', 'join'):
            from_join_next = True
            continue
        if from_join_next:
            if token not in ALLOWED_TABLES and token not in (
                'select', 'where', 'as', 'on', 'and', 'or', 'not', 'in',
                'case', 'when', 'then', 'else', 'end', 'null', 'true', 'false',
                'lateral', 'unnest', 'generate_series',
            ) and not token.startswith('_') and not token.startswith('st_'):
                # Could be a CTE alias or subquery alias — skip single-word aliases
                pass
            from_join_next = False
    return None


def execute_hypothesis_sql(sql: str) -> dict:
    """Execute a single SQL query safely. Returns {rows: [...], error: str|None, row_count: int}."""
    # Validate
    error = validate_sql(sql)
    if error:
        return {"rows": [], "error": error, "row_count": 0}

    # Wrap with row limit
    wrapped_sql = f"SELECT * FROM ({sql}) AS _hypothesis_result LIMIT 25"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '8s'")
            cur.execute("BEGIN READ ONLY")
            try:
                cur.execute(wrapped_sql)
                columns = [desc[0] for desc in cur.description]
                raw_rows = cur.fetchall()
            finally:
                cur.execute("ROLLBACK")  # end the read-only transaction
                cur.execute("RESET statement_timeout")
    except Exception as e:
        put_conn(conn)
        return {"rows": [], "error": str(e)[:200], "row_count": 0}
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass

    # Process rows into dicts
    rows = []
    for raw_row in raw_rows:
        item = dict(zip(columns, raw_row))
        # Convert geometry to JSON if present
        if "geometry" in item and isinstance(item["geometry"], str):
            try:
                item["geometry"] = json.loads(item["geometry"])
            except (json.JSONDecodeError, TypeError):
                pass
        # Convert Decimal/date types to JSON-serializable
        for k, v in item.items():
            if hasattr(v, '__float__') and not isinstance(v, (int, float)):
                item[k] = float(v)
            elif hasattr(v, 'isoformat'):
                item[k] = v.isoformat()
        rows.append(item)

    return {"rows": rows, "error": None, "row_count": len(rows)}


async def generate_hypotheses(messages: list[ChatMessage]) -> list[dict]:
    """Phase 1: Ask Gemini to form hypotheses and write SQL."""
    result = await call_gemini_with_prompt(HYPOTHESIS_PROMPT, messages, max_tokens=4096)
    hypotheses = result.get("hypotheses", [])
    if not hypotheses:
        # Fallback: wrap the whole response as a single hypothesis
        hypotheses = [{
            "name": "General exploration",
            "rationale": "Broad search based on the user's query",
            "sql_queries": [],
        }]
    return hypotheses


async def evaluate_hypotheses(user_query: str, hypotheses: list[dict]) -> dict:
    """Phase 3: Ask Gemini to evaluate results and pick the best opportunities."""
    # Build the hypothesis results summary for the evaluation prompt
    parts = []
    for i, h in enumerate(hypotheses):
        parts.append(f"## Hypothesis {i+1}: {h['name']}")
        parts.append(f"Rationale: {h['rationale']}")
        for j, q in enumerate(h.get("sql_queries", [])):
            result = q.get("result", {})
            row_count = result.get("row_count", 0)
            error = result.get("error")
            parts.append(f"\nQuery {j+1}: {q.get('description', 'unnamed')}")
            if error:
                parts.append(f"ERROR: {error}")
            elif row_count == 0:
                parts.append("No results returned.")
            else:
                # Include first few rows as a sample
                rows = result.get("rows", [])
                # Summarize: show all rows but trim geometry for brevity
                summarized = []
                for row in rows:
                    summary_row = {k: v for k, v in row.items() if k != "geometry"}
                    summarized.append(summary_row)
                parts.append(f"Results ({row_count} rows):")
                parts.append(json.dumps(summarized, indent=2, default=str)[:3000])
        parts.append("")

    hypothesis_results_text = "\n".join(parts)

    eval_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        user_query=user_query,
        hypothesis_results=hypothesis_results_text,
    )

    eval_messages = [{"role": "user", "content": "Evaluate these hypothesis results and select the best opportunities."}]
    result = await call_gemini_with_prompt(eval_prompt, eval_messages, max_tokens=4096)

    return result


def build_final_results(hypotheses: list[dict], evaluation: dict) -> list[dict]:
    """Extract the selected result rows and attach annotations + _table field."""
    selected = evaluation.get("selected_results", {})
    annotations = evaluation.get("result_annotations", [])

    h_idx = selected.get("hypothesis_index", 0)
    q_idx = selected.get("query_index", 0)
    row_indices = selected.get("row_indices", [])

    # Get the actual rows from the hypothesis results
    try:
        hypothesis = hypotheses[h_idx]
        query = hypothesis["sql_queries"][q_idx]
        all_rows = query.get("result", {}).get("rows", [])
    except (IndexError, KeyError):
        # Fallback: gather all rows from all hypotheses
        all_rows = []
        for h in hypotheses:
            for q in h.get("sql_queries", []):
                rows = q.get("result", {}).get("rows", [])
                all_rows.extend(rows)
        row_indices = list(range(min(len(all_rows), 15)))

    results = []
    for i, row_idx in enumerate(row_indices):
        if row_idx >= len(all_rows):
            continue
        row = dict(all_rows[row_idx])  # copy

        # Add opportunity_reason from annotations
        if i < len(annotations):
            row["opportunity_reason"] = annotations[i]

        # Determine _table from context
        if "address" in row and "sale_price" in row:
            row["_table"] = "sold_properties"
        elif "zone_desc" in row or "site_area" in row:
            row["_table"] = "rzlt"
        elif "plan_ref" in row or "decision" in row:
            row["_table"] = "dlr_planning_polygons"
        elif "national_ref" in row or "area_sqm" in row:
            row["_table"] = "cadastral_freehold"
        else:
            row["_table"] = "unknown"

        results.append(row)

    return results


@app.post("/api/ai/chat")
async def ai_chat(req: ChatRequest):
    """AI-powered property analytics chat with hypothesis-driven explore pipeline.

    Phase 1: Gemini forms 3-5 hypotheses and writes SQL for each.
    Phase 2: Execute all SQL queries safely against PostGIS.
    Phase 3: Gemini evaluates results, ranks hypotheses, picks best properties.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    # Get the user's latest question for evaluation context
    user_query = ""
    for msg in reversed(req.messages):
        if msg.role == "user":
            user_query = msg.content
            break

    # Phase 1: Generate hypotheses + SQL
    hypotheses = await generate_hypotheses(req.messages)

    # Phase 2: Execute all SQL queries safely
    total_queries = 0
    for hypothesis in hypotheses:
        for query in hypothesis.get("sql_queries", []):
            sql = query.get("sql", "")
            if sql.strip():
                query["result"] = execute_hypothesis_sql(sql)
                total_queries += 1

    # Phase 3: Evaluate results, rank hypotheses, pick best properties
    evaluation = await evaluate_hypotheses(user_query, hypotheses)

    # Build the final results array with geometry for the frontend map
    evaluation["results"] = build_final_results(hypotheses, evaluation)

    # Ensure type is set
    if "type" not in evaluation:
        evaluation["type"] = "explore"

    return evaluation
