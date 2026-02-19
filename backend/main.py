import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import get_conn, put_conn


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
    allow_methods=["GET"],
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
