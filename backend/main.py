import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from db import get_conn, put_conn

# Load .env from backend directory
load_dotenv(Path(__file__).parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# GEMINI_MODEL = "gemini-2.0-flash"  # cheaper, faster — good for testing
# GEMINI_MODEL = "gemini-3.1-pro-preview"
GEMINI_MODEL = "gemini-3-flash-preview"
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


@app.get("/api/census_small_areas")
def get_census_small_areas(bbox: str = Query(..., description="west,south,east,north")):
    """Return Census 2022 Small Area polygons with demographic stats as GeoJSON."""
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
                    sa_pub2022,
                    sa_urban_area_name,
                    county_english,
                    total_population,
                    total_households,
                    avg_household_size,
                    apartment_pct,
                    owner_occupied_pct,
                    rented_pct,
                    vacancy_rate,
                    employment_rate,
                    third_level_pct,
                    wfh_pct,
                    population_density,
                    avg_rooms,
                    health_good_pct,
                    built_pre_1919,
                    built_2016_plus,
                    area_sqm,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM census_small_areas
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                  AND total_population IS NOT NULL
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
            fid, sa_code, urban_area, county, pop, households, hh_size,
            apt_pct, owner_pct, rent_pct, vac_rate, emp_rate, edu_pct,
            wfh, pop_density, avg_rooms, health_pct,
            pre_1919, post_2016, area_sqm, geometry,
        ) = row
        features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {
                    "id": fid,
                    "sa_code": sa_code,
                    "urban_area": urban_area,
                    "county": county,
                    "total_population": pop,
                    "total_households": households,
                    "avg_household_size": float(hh_size) if hh_size else None,
                    "apartment_pct": float(apt_pct) if apt_pct else None,
                    "owner_occupied_pct": float(owner_pct) if owner_pct else None,
                    "rented_pct": float(rent_pct) if rent_pct else None,
                    "vacancy_rate": float(vac_rate) if vac_rate else None,
                    "employment_rate": float(emp_rate) if emp_rate else None,
                    "third_level_pct": float(edu_pct) if edu_pct else None,
                    "wfh_pct": float(wfh) if wfh else None,
                    "population_density": float(pop_density) if pop_density else None,
                    "avg_rooms": float(avg_rooms) if avg_rooms else None,
                    "health_good_pct": float(health_pct) if health_pct else None,
                    "built_pre_1919": pre_1919,
                    "built_2016_plus": post_2016,
                    "area_sqm": round(area_sqm, 1) if area_sqm else None,
                },
            }
        )

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/urban_areas")
def get_urban_areas(bbox: str = Query(..., description="west,south,east,north")):
    """Return Urban Area boundary polygons as GeoJSON."""
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
                    urban_area_name,
                    urban_area_code,
                    county,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM urban_areas
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 500
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        fid, name, code, county, geometry = row
        features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {
                    "id": fid,
                    "urban_area_name": name,
                    "urban_area_code": code,
                    "county": county,
                },
            }
        )

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/census_stats")
def get_census_stats(
    lng: float = Query(...),
    lat: float = Query(...),
    radius: float = Query(500, description="Radius in metres"),
):
    """Return aggregated census demographics for Small Areas within a circle."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            center_sql = "ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 2157)"
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS sa_count,
                    COALESCE(SUM(total_population), 0) AS total_pop,
                    COALESCE(SUM(total_households), 0) AS total_hh,
                    COALESCE(ROUND(AVG(avg_household_size)::numeric, 2), 0) AS avg_hh_size,
                    COALESCE(ROUND(AVG(apartment_pct)::numeric, 1), 0) AS avg_apt_pct,
                    COALESCE(ROUND(AVG(owner_occupied_pct)::numeric, 1), 0) AS avg_owner_pct,
                    COALESCE(ROUND(AVG(rented_pct)::numeric, 1), 0) AS avg_rented_pct,
                    COALESCE(ROUND(AVG(vacancy_rate)::numeric, 1), 0) AS avg_vacancy,
                    COALESCE(ROUND(AVG(employment_rate)::numeric, 1), 0) AS avg_employment,
                    COALESCE(ROUND(AVG(third_level_pct)::numeric, 1), 0) AS avg_edu,
                    COALESCE(ROUND(AVG(wfh_pct)::numeric, 1), 0) AS avg_wfh,
                    COALESCE(ROUND(AVG(population_density)::numeric, 0), 0) AS avg_density,
                    COALESCE(ROUND(AVG(avg_rooms)::numeric, 1), 0) AS avg_rooms,
                    COALESCE(SUM(age_0_14), 0) AS age_0_14,
                    COALESCE(SUM(age_15_24), 0) AS age_15_24,
                    COALESCE(SUM(age_25_44), 0) AS age_25_44,
                    COALESCE(SUM(age_45_64), 0) AS age_45_64,
                    COALESCE(SUM(age_65_plus), 0) AS age_65_plus
                FROM census_small_areas
                WHERE ST_DWithin(
                    ST_Transform(geom, 2157),
                    {center_sql},
                    %s
                )
                AND total_population IS NOT NULL
                AND total_population > 0
                """,
                (lng, lat, radius),
            )
            row = cur.fetchone()
    finally:
        put_conn(conn)

    (
        sa_count, total_pop, total_hh, avg_hh_size, avg_apt_pct,
        avg_owner_pct, avg_rented_pct, avg_vacancy, avg_employment,
        avg_edu, avg_wfh, avg_density, avg_rooms,
        age_0_14, age_15_24, age_25_44, age_45_64, age_65_plus,
    ) = row

    return {
        "center": {"lng": lng, "lat": lat},
        "radius_m": radius,
        "small_area_count": sa_count,
        "total_population": int(total_pop),
        "total_households": int(total_hh),
        "avg_household_size": float(avg_hh_size),
        "avg_apartment_pct": float(avg_apt_pct),
        "avg_owner_occupied_pct": float(avg_owner_pct),
        "avg_rented_pct": float(avg_rented_pct),
        "avg_vacancy_rate": float(avg_vacancy),
        "avg_employment_rate": float(avg_employment),
        "avg_third_level_pct": float(avg_edu),
        "avg_wfh_pct": float(avg_wfh),
        "avg_population_density": float(avg_density),
        "avg_rooms": float(avg_rooms),
        "age_profile": {
            "0-14": int(age_0_14),
            "15-24": int(age_15_24),
            "25-44": int(age_25_44),
            "45-64": int(age_45_64),
            "65+": int(age_65_plus),
        },
    }


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


@app.get("/api/lap_boundaries")
def get_lap_boundaries(bbox: str = Query(..., description="west,south,east,north")):
    """Return South Dublin Local Area Plan boundaries as GeoJSON."""
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
                    objective,
                    map_number,
                    feature_type1 AS feature_type,
                    hyperlink,
                    area__ha_ AS area_ha,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM sd_lap_boundaries
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 500
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        fid, objective, map_number, feature_type, hyperlink, area_ha, geometry = row
        features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {
                    "id": fid,
                    "objective": objective,
                    "map_number": map_number,
                    "feature_type": feature_type,
                    "hyperlink": hyperlink,
                    "area_ha": float(area_ha) if area_ha else None,
                },
            }
        )
    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/sd_planning_register")
def get_sd_planning_register(bbox: str = Query(..., description="west,south,east,north")):
    """Return South Dublin Planning Register applications within the bounding box as GeoJSON."""
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
                    ref,
                    regref,
                    link,
                    location,
                    applicantname AS applicant_name,
                    status,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM sd_planning_register
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
        fid, ref, regref, link, location, applicant_name, status, geometry = row
        features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {
                    "id": fid,
                    "ref": ref,
                    "regref": regref,
                    "link": link,
                    "location": location,
                    "applicant_name": (applicant_name or "").strip() or None,
                    "status": status,
                },
            }
        )
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


ENRICHMENT_RADIUS_M = 500


@app.get("/api/parcel/{parcel_id}/enriched")
def get_parcel_enriched(parcel_id: int, parcel_type: str = Query("freehold")):
    """Return parcel details plus spatial enrichment: RZLT overlap, nearby planning, sales, census."""
    table = PARCEL_TABLES.get(parcel_type)
    if not table:
        raise HTTPException(status_code=400, detail="parcel_type must be freehold or leasehold")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1) Fetch parcel basics + geometry centroid + full geom for overlap queries
            cur.execute(
                f"""
                SELECT
                    ogc_fid,
                    nationalcadastralreference,
                    gml_id,
                    area_sqm,
                    ST_X(ST_Centroid(geom)) AS centroid_lng,
                    ST_Y(ST_Centroid(geom)) AS centroid_lat,
                    geom
                FROM {table}
                WHERE ogc_fid = %s
                """,
                (parcel_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Parcel not found")

            ogc_fid, national_ref, gml_id, area_sqm, centroid_lng, centroid_lat, parcel_geom = row
            area_sqm_val = round(area_sqm, 1) if area_sqm is not None else None
            area_acres = round(area_sqm / 4046.86, 3) if area_sqm is not None else None

            centroid_2157 = "ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 2157)"

            # 2) RZLT overlap — does any RZLT zone intersect this parcel?
            cur.execute(
                f"""
                SELECT zone_desc, site_area, local_authority_name, zone_gzt
                FROM rzlt
                WHERE ST_Intersects(geom, (SELECT geom FROM {table} WHERE ogc_fid = %s))
                LIMIT 5
                """,
                (parcel_id,),
            )
            rzlt_rows = cur.fetchall()
            rzlt_overlap = [
                {"zone_desc": r[0], "site_area": r[1], "local_authority_name": r[2], "zone_gzt": r[3]}
                for r in rzlt_rows
            ]

            # 3) Nearby planning apps within radius (sorted by distance)
            cur.execute(
                f"""
                SELECT
                    plan_ref,
                    decision,
                    descrptn,
                    reg_date::text AS registered_date,
                    dec_date::text AS decision_date,
                    ROUND(ST_Distance(
                        ST_Transform(geom, 2157),
                        {centroid_2157}
                    )::numeric, 0) AS distance_m
                FROM dlr_planning_polygons
                WHERE ST_DWithin(
                    ST_Transform(geom, 2157),
                    {centroid_2157},
                    %s
                )
                ORDER BY distance_m
                LIMIT 5
                """,
                (centroid_lng, centroid_lat, centroid_lng, centroid_lat, ENRICHMENT_RADIUS_M),
            )
            planning_rows = cur.fetchall()
            nearby_planning = [
                {
                    "plan_ref": r[0], "decision": r[1], "description": r[2],
                    "registered_date": r[3], "decision_date": r[4],
                    "distance_m": int(r[5]) if r[5] is not None else None,
                }
                for r in planning_rows
            ]

            # 4) Sold property stats within radius
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS cnt,
                    COALESCE(ROUND(AVG(sale_price)), 0) AS avg_sale,
                    COALESCE(ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sale_price)), 0) AS median_sale,
                    COALESCE(ROUND(AVG(CASE WHEN floor_area_m2 > 0 THEN sale_price / floor_area_m2 END)), 0) AS avg_price_sqm
                FROM sold_properties
                WHERE ST_DWithin(
                    ST_Transform(geom, 2157),
                    {centroid_2157},
                    %s
                )
                AND sale_price > 0 AND sale_price < 10000000
                """,
                (centroid_lng, centroid_lat, ENRICHMENT_RADIUS_M),
            )
            sales_agg = cur.fetchone()
            sales_count, avg_sale, median_sale, avg_psm = sales_agg

            # Top 5 nearest recent sales
            cur.execute(
                f"""
                SELECT
                    address, sale_price, sale_date::text, property_type,
                    ROUND(ST_Distance(
                        ST_Transform(geom, 2157),
                        {centroid_2157}
                    )::numeric, 0) AS distance_m
                FROM sold_properties
                WHERE ST_DWithin(
                    ST_Transform(geom, 2157),
                    {centroid_2157},
                    %s
                )
                AND sale_price > 0 AND sale_price < 10000000
                ORDER BY sale_date DESC NULLS LAST
                LIMIT 5
                """,
                (centroid_lng, centroid_lat, centroid_lng, centroid_lat, ENRICHMENT_RADIUS_M),
            )
            recent_sales = [
                {
                    "address": r[0], "sale_price": r[1], "sale_date": r[2],
                    "property_type": r[3], "distance_m": int(r[4]) if r[4] is not None else None,
                }
                for r in cur.fetchall()
            ]

            # 5) Census — small area containing this parcel centroid
            cur.execute(
                """
                SELECT
                    sa_pub2022,
                    total_population,
                    population_density,
                    owner_occupied_pct,
                    rented_pct,
                    vacancy_rate,
                    employment_rate,
                    third_level_pct,
                    avg_household_size
                FROM census_small_areas
                WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                AND total_population IS NOT NULL
                LIMIT 1
                """,
                (centroid_lng, centroid_lat),
            )
            census_row = cur.fetchone()
            census = None
            if census_row:
                census = {
                    "small_area_id": census_row[0],
                    "total_population": census_row[1],
                    "population_density": float(census_row[2]) if census_row[2] else None,
                    "owner_occupied_pct": float(census_row[3]) if census_row[3] else None,
                    "rented_pct": float(census_row[4]) if census_row[4] else None,
                    "vacancy_rate": float(census_row[5]) if census_row[5] else None,
                    "employment_rate": float(census_row[6]) if census_row[6] else None,
                    "third_level_pct": float(census_row[7]) if census_row[7] else None,
                    "avg_household_size": float(census_row[8]) if census_row[8] else None,
                }

    finally:
        put_conn(conn)

    return {
        "parcel": {
            "id": ogc_fid,
            "national_ref": national_ref,
            "inspire_id": gml_id,
            "area_sqm": area_sqm_val,
            "area_acres": area_acres,
            "type": parcel_type,
        },
        "centroid": {"lng": centroid_lng, "lat": centroid_lat},
        "rzlt_overlap": rzlt_overlap,
        "nearby_planning": nearby_planning,
        "nearby_sales": {
            "count": sales_count,
            "avg_sale_price": int(avg_sale),
            "median_sale_price": int(median_sale),
            "avg_price_per_sqm": int(avg_psm),
            "recent": recent_sales,
        },
        "census": census,
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


# ── Side-site / infill detection endpoint ─────────────────────────────────────

SIDE_SITE_SQL = """
WITH candidates AS (
    SELECT
        f.ogc_fid,
        f.nationalcadastralreference,
        f.area_sqm,
        f.geom,
        4 * PI() * ST_Area(ST_Transform(f.geom, 2157))
            / NULLIF(POWER(ST_Perimeter(ST_Transform(f.geom, 2157)), 2), 0)
            AS compactness,
        (SELECT COUNT(*) FROM cadastral_freehold n
         WHERE n.geom && ST_Expand(f.geom, 0.0001)
           AND ST_Touches(n.geom, f.geom)
           AND n.ogc_fid != f.ogc_fid) AS neighbor_count
    FROM cadastral_freehold f
    WHERE f.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
      AND f.area_sqm BETWEEN 80 AND 500
),
with_planning AS (
    SELECT c.*,
        EXISTS (
            SELECT 1 FROM dlr_planning_polygons p
            WHERE ST_Intersects(p.geom, c.geom)
        ) AS has_planning
    FROM candidates c
),
with_rzlt AS (
    SELECT wp.*,
        EXISTS (
            SELECT 1 FROM rzlt r
            WHERE ST_Intersects(r.geom, wp.geom)
        ) AS on_rzlt
    FROM with_planning wp
),
with_census AS (
    SELECT wr.*,
        cs.owner_occupied_pct,
        cs.total_population,
        cs.vacancy_rate
    FROM with_rzlt wr
    LEFT JOIN census_small_areas cs ON ST_Intersects(cs.geom, ST_Centroid(wr.geom))
),
scored AS (
    SELECT *,
        -- Size score: peaks at 150-350 sqm
        CASE
            WHEN area_sqm BETWEEN 150 AND 350 THEN 1.0
            WHEN area_sqm BETWEEN 80 AND 150 THEN (area_sqm - 80.0) / 70.0
            ELSE (500.0 - area_sqm) / 150.0
        END * 0.20
        -- Shape score: lower compactness = more elongated = higher score
        + CASE
            WHEN compactness < 0.3 THEN 1.0
            WHEN compactness < 0.5 THEN (0.5 - compactness) / 0.2
            ELSE 0.0
        END * 0.20
        -- Neighbor score
        + CASE
            WHEN neighbor_count >= 3 THEN 1.0
            WHEN neighbor_count = 2 THEN 0.7
            WHEN neighbor_count = 1 THEN 0.3
            ELSE 0.0
        END * 0.15
        -- No planning = likely undeveloped
        + CASE WHEN NOT has_planning THEN 1.0 ELSE 0.0 END * 0.15
        -- RZLT = motivated seller
        + CASE WHEN on_rzlt THEN 1.0 ELSE 0.0 END * 0.15
        -- Residential context
        + CASE WHEN COALESCE(owner_occupied_pct, 0) > 50 THEN 1.0 ELSE 0.3 END * 0.15
        AS score
    FROM with_census
)
SELECT
    ogc_fid AS id,
    nationalcadastralreference AS national_ref,
    ROUND(area_sqm::numeric, 1) AS area_sqm,
    ROUND(area_sqm::numeric / 4046.86, 3) AS area_acres,
    ROUND(compactness::numeric, 3) AS compactness,
    neighbor_count,
    has_planning,
    on_rzlt,
    ROUND(COALESCE(owner_occupied_pct, 0)::numeric, 1) AS owner_occupied_pct,
    ROUND(COALESCE(vacancy_rate, 0)::numeric, 1) AS vacancy_rate,
    ROUND(score::numeric, 3) AS score,
    ST_AsGeoJSON(geom)::json AS geometry,
    ST_X(ST_Centroid(geom)) AS lng,
    ST_Y(ST_Centroid(geom)) AS lat
FROM scored
WHERE score > 0.3
ORDER BY score DESC
LIMIT 50;
"""


@app.get("/api/side_sites")
def get_side_sites(
    bbox: str = Query(None, description="xmin,ymin,xmax,ymax"),
    lng: float = Query(None),
    lat: float = Query(None),
    radius: float = Query(500, description="Radius in metres (used with lng/lat)"),
):
    """Detect side-site / infill development candidates within a bounding box or radius."""
    if bbox:
        try:
            xmin, ymin, xmax, ymax = [float(v) for v in bbox.split(",")]
        except (ValueError, TypeError):
            raise HTTPException(400, "bbox must be xmin,ymin,xmax,ymax")
    elif lng is not None and lat is not None:
        # Convert point+radius to bbox (approximate)
        # 1 degree lat ≈ 111,320m; 1 degree lng ≈ 111,320 * cos(lat)
        import math
        dlat = radius / 111320.0
        dlng = radius / (111320.0 * math.cos(math.radians(lat)))
        xmin, ymin = lng - dlng, lat - dlat
        xmax, ymax = lng + dlng, lat + dlat
    else:
        raise HTTPException(400, "Provide either bbox or lng+lat parameters")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '30s'")
            cur.execute(SIDE_SITE_SQL, (xmin, ymin, xmax, ymax))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Side site query failed: {e}")
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        props = dict(zip(cols, row))
        geom = props.pop("geometry", None)
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
    }


# ── AI-powered analytics (Hypothesis-Driven Explore Pipeline) ────────────────

ALLOWED_TABLES = {
    "sold_properties", "cadastral_freehold", "cadastral_leasehold",
    "rzlt", "dlr_planning_polygons", "dlr_planning_points",
    "census_small_areas", "urban_areas",
}

SQL_BLOCKLIST = re.compile(
    r'\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|EXECUTE|DO)\b',
    re.IGNORECASE,
)

# ── Intent Router Prompt ─────────────────────────────────────────────────────

INTENT_ROUTER_PROMPT = """You are a query classifier for a Dublin property intelligence system.

Classify the user's latest message into exactly ONE intent:

- "site_search": User wants to find specific sites/properties/parcels matching criteria. Will show ranked results on a map. Examples: "Find RZLT sites over 1000sqm", "Where are the cheapest houses in D6?", "Show me development land near Dundrum"
- "area_comparison": User wants to compare 2+ areas/neighborhoods by statistics. Examples: "Compare Rathmines vs Ranelagh", "Which Dublin area has the highest vacancy rate?", "How does Blackrock compare to Stillorgan for prices?"
- "stat_question": User wants a specific statistic or factual answer, not a list of sites. Examples: "What's the average house price in Blackrock?", "How many RZLT sites are in Dublin?", "What percentage of homes in Dundrum are apartments?"
- "site_detail": User asks about a specific known site/parcel/property by ID, reference, or exact address. Examples: "Tell me about parcel DN-123456", "What's the planning history at 15 Main St Blackrock?"
- "clarification": Message is unclear, a greeting, off-topic, or needs more info before a query can run. Examples: "Hi", "What can you do?", "Show me the good ones", "Thanks"
- "follow_up": User is refining or filtering previous results. Examples: "Show cheaper ones", "Do the same for Blackrock", "Filter to apartments only", "Now show me the planning history for those"

RESPOND WITH VALID JSON ONLY:
{"intent": "site_search", "reasoning": "Brief explanation of classification"}
"""

# ── Clarification Handler Prompt ─────────────────────────────────────────────

CLARIFICATION_PROMPT = """You are LandOS AI, a Dublin property intelligence assistant for property developers.
The user's message needs clarification or is a general question. Respond conversationally.
Suggest 3 specific, actionable queries they could try.

RESPONSE FORMAT (valid JSON only):
{"message": "Your conversational response here", "suggestions": ["Find the largest RZLT sites in south Dublin", "Compare house prices in Rathmines vs Ranelagh", "What's the average price per sqm in Blackrock?"]}
"""

# ── Stat Question Handler Prompt ─────────────────────────────────────────────

STAT_QUESTION_PROMPT_TEMPLATE = """You are LandOS AI. The user wants a specific statistic or factual answer about Dublin property.

Write ONE PostGIS SQL query that answers their question. Return a numeric or textual result.

{db_schema}

CRITICAL SQL RULES:
1. LIMIT to 50 rows max.
2. Use NULLIF(x, 0) to prevent division by zero.
3. Filter sale_price > 0 on sold_properties.
4. For ST_DWithin with metre distances, cast to geography: ST_DWithin(a.geom::geography, b.geom::geography, 500)
5. Cadastral tables (2M+ rows): ALWAYS include a spatial filter.
6. Never use column aliases in WHERE/HAVING — repeat the expression.
7. You do NOT need geometry columns (no ST_AsGeoJSON, no lng/lat) — this is for stats, not map display.

RESPONSE FORMAT (valid JSON only):
{{"sql": "SELECT ... your query ...", "answer_template": "Description of what the result shows"}}
"""

# ── Area Comparison Handler Prompt ───────────────────────────────────────────

AREA_COMPARISON_PROMPT_TEMPLATE = """You are LandOS AI. The user wants to compare areas or neighborhoods.

Write 1-3 SQL queries that gather comparative statistics for the areas mentioned.
Each query should aggregate data (AVG, COUNT, etc.) and include an area/location grouping.

{db_schema}

CRITICAL SQL RULES:
1. LIMIT to 50 rows max per query.
2. Use NULLIF(x, 0) to prevent division by zero.
3. Filter sale_price > 0 on sold_properties.
4. For ST_DWithin with metre distances, cast to geography.
5. Cadastral tables: ALWAYS include a spatial filter.
6. Never use column aliases in WHERE/HAVING.
7. You do NOT need geometry columns — this is for comparative stats, not map display.
8. Group results by area/neighborhood for comparison.

RESPONSE FORMAT (valid JSON only):
{{"queries": [{{"description": "What this compares", "sql": "SELECT ..."}}]}}
"""

# ── Phase 1: Hypothesis Generation Prompt ────────────────────────────────────

DB_SCHEMA_PROMPT = """DATABASE SCHEMA (PostgreSQL 16 + PostGIS 3.4):

TABLE: sold_properties (residential sales — ~50k rows, geom is Point)
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

TABLE: cadastral_freehold (land ownership parcels — ~2M rows, LARGE, geom is Polygon)
  ogc_fid SERIAL PRIMARY KEY
  nationalcadastralreference TEXT
  gml_id TEXT
  area_sqm NUMERIC
  geom GEOMETRY(Polygon, 4326)
  -- SPATIAL INDEX on geom. ALWAYS use spatial filter (ST_MakeEnvelope or ST_DWithin) to avoid full table scans.

TABLE: cadastral_leasehold (leasehold parcels — ~200k rows, geom is Polygon)
  (same schema as cadastral_freehold)
  -- SPATIAL INDEX on geom. ALWAYS use spatial filter.

TABLE: rzlt (Residential Zoned Land Tax sites — ~4k rows, geom is Polygon)
  ogc_fid SERIAL PRIMARY KEY
  zone_desc TEXT              -- e.g. 'Residential', 'Mixed Use'
  zone_gzt TEXT
  gzt_desc TEXT
  site_area NUMERIC           -- area in sqm
  local_authority_name TEXT   -- e.g. 'Dublin City Council', 'Dún Laoghaire-Rathdown'
  geom GEOMETRY(Polygon, 4326)

TABLE: dlr_planning_polygons (planning applications in Dún Laoghaire-Rathdown — ~15k rows, geom is Polygon)
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

TABLE: census_small_areas (Census 2022 demographics by Small Area — ~4600 Dublin rows, geom is Polygon)
  ogc_fid SERIAL PRIMARY KEY
  sa_pub2022 TEXT              -- Small Area code (join key)
  sa_urban_area_name TEXT      -- Urban area name (e.g. 'Dublin City')
  county_english TEXT          -- County name
  total_population INTEGER     -- Total persons in the Small Area
  male_population INTEGER
  female_population INTEGER
  population_density DOUBLE PRECISION  -- persons per km²
  age_0_14 INTEGER, age_15_24 INTEGER, age_25_44 INTEGER, age_45_64 INTEGER, age_65_plus INTEGER
  total_households INTEGER
  avg_household_size DOUBLE PRECISION
  houses INTEGER               -- count of houses/bungalows
  apartments INTEGER           -- count of flats/apartments/bedsits
  apartment_pct DOUBLE PRECISION
  built_pre_1919 INTEGER, built_1919_1945 INTEGER, built_1946_1970 INTEGER
  built_1971_2000 INTEGER, built_2001_2015 INTEGER, built_2016_plus INTEGER
  owner_occupied INTEGER
  rented_total INTEGER
  owner_occupied_pct DOUBLE PRECISION  -- % owner-occupied (0-100)
  rented_pct DOUBLE PRECISION          -- % rented (0-100)
  avg_rooms DOUBLE PRECISION
  vacancy_rate DOUBLE PRECISION        -- % vacant dwellings (0-100)
  employed INTEGER, unemployed INTEGER
  employment_rate DOUBLE PRECISION     -- % employed of labour force (0-100)
  third_level_total INTEGER
  third_level_pct DOUBLE PRECISION     -- % with third-level education (0-100)
  work_from_home INTEGER, car_commuters INTEGER, public_transport_commuters INTEGER
  wfh_pct DOUBLE PRECISION             -- % working from home (0-100)
  health_very_good INTEGER, health_good INTEGER
  health_good_pct DOUBLE PRECISION     -- % in good/very good health (0-100)
  area_sqm DOUBLE PRECISION
  geom GEOMETRY(Polygon, 4326)
  -- SPATIAL INDEX on geom. Use spatial filters for efficient queries.
  -- KEY USE: Cross-reference with other tables to enrich site analysis with demographics.
  -- Example: Find RZLT sites in areas with high vacancy rates, or parcels in high-density young-professional areas.

TABLE: urban_areas (Urban area boundary polygons — ~11 Dublin rows, geom is Polygon)
  ogc_fid SERIAL PRIMARY KEY
  urban_area_name TEXT         -- e.g. 'Dublin City', 'Swords', 'Bray'
  urban_area_code TEXT
  county TEXT
  geom GEOMETRY(Polygon, 4326)

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
- ST_X(point), ST_Y(point) — extract coordinates from a POINT geometry
- ST_AsGeoJSON(geom)::json — geometry as GeoJSON for frontend
- ST_Buffer(geom::geography, distance_metres)::geometry — buffer around a geometry
- ST_Perimeter(ST_Transform(geom, 2157)) — perimeter in metres (use EPSG:2157 for accuracy)
- ST_Touches(a.geom, b.geom) — true if geometries share a boundary (adjacency detection)
- ST_NPoints(geom) — number of vertices in a geometry
- Compactness ratio: 4 * PI() * ST_Area(ST_Transform(geom, 2157)) / NULLIF(POWER(ST_Perimeter(ST_Transform(geom, 2157)), 2), 0) — 1.0 = circle, lower = elongated/irregular

SIDE SITE / INFILL DETECTION PATTERNS:
Side sites are small parcels (80-500 sqm) between existing houses — high-value development opportunities.
Key signals to combine:
- Shape: compactness ratio < 0.5 indicates elongated/irregular shape (typical of side gardens)
- Size: area_sqm BETWEEN 80 AND 500 (large enough to build, too small for existing house+garden)
- Adjacency: COUNT of neighboring parcels via ST_Touches >= 2 (flanked by developed plots)
- No planning: LEFT JOIN planning tables IS NULL (no recent applications = likely undeveloped)
- RZLT overlap: ST_Intersects with rzlt table (owner taxed 3%/year for not developing)
- Residential context: census owner_occupied_pct > 50% in containing small area
Example pattern:
  WITH candidates AS (
    SELECT f.ogc_fid, f.nationalcadastralreference, f.area_sqm, f.geom,
      4 * PI() * ST_Area(ST_Transform(f.geom, 2157))
        / NULLIF(POWER(ST_Perimeter(ST_Transform(f.geom, 2157)), 2), 0) AS compactness
    FROM cadastral_freehold f
    WHERE f.geom && ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326)
      AND f.area_sqm BETWEEN 80 AND 500
  )
  SELECT c.*, ST_AsGeoJSON(c.geom)::json AS geometry,
    ST_X(ST_Centroid(c.geom)) AS lng, ST_Y(ST_Centroid(c.geom)) AS lat
  FROM candidates c
  WHERE c.compactness < 0.5
  ORDER BY c.area_sqm DESC LIMIT 25;
NOTE: For neighbor_count, use a lateral join or subquery with ST_Touches — but always include a spatial filter on the outer table first to avoid full scans."""

HYPOTHESIS_PROMPT = f"""You are LandOS AI, an expert Dublin property & land development analyst.
The user is a property developer. They ask questions. You answer them by forming hypotheses and writing SQL to test them.

YOUR TASK: Given the user's question, form 3-5 distinct hypotheses about where opportunities might exist, and write PostGIS SQL to test each one.

{DB_SCHEMA_PROMPT}

CRITICAL SQL RULES (FOLLOW EXACTLY — violations cause runtime errors):

1. GEOMETRY COLUMNS: Every query MUST include these 3 columns:
   - ST_AsGeoJSON(tablename.geom)::json AS geometry
   - For POLYGON tables (cadastral_freehold, cadastral_leasehold, rzlt, dlr_planning_polygons):
       ST_X(ST_Centroid(tablename.geom)) AS lng, ST_Y(ST_Centroid(tablename.geom)) AS lat
   - For POINT tables (sold_properties, dlr_planning_points):
       ST_X(tablename.geom) AS lng, ST_Y(tablename.geom) AS lat
   NOTE: ST_X() and ST_Y() ONLY work on Point geometries. NEVER call ST_X(polygon.geom) — use ST_X(ST_Centroid(polygon.geom)) instead.

2. CADASTRAL TABLES (2M+ rows): ALWAYS include a spatial filter (ST_MakeEnvelope, ST_DWithin, or ST_Intersects with a smaller table). NEVER do a full scan.

3. LIMIT each query to 25 rows max.

4. ALWAYS use NULLIF(x, 0) to prevent division by zero: e.g. sale_price / NULLIF(floor_area_m2, 0)

5. ALWAYS filter: sale_price > 0 on sold_properties.

6. NEVER use column aliases in WHERE/HAVING — repeat the expression or use a CTE/subquery.

7. When using CTEs that join tables, always qualify ambiguous column names with the table alias.

8. For ST_DWithin with metre distances, cast to geography: ST_DWithin(a.geom::geography, b.geom::geography, 500)

9. NEVER use GROUP BY with geometry columns directly. Instead, use a subquery or CTE to aggregate first, then join back to get geometry.

10. For cross-table spatial queries, prefer ST_DWithin over ST_Intersects for point-to-polygon distance queries.

11. PRIMARY TABLE TAGGING: Every sql_queries entry MUST include a "primary_table" field set to the main table whose rows are returned.
    Must be one of: sold_properties, cadastral_freehold, cadastral_leasehold, rzlt, dlr_planning_polygons, dlr_planning_points, census_small_areas, urban_areas.
    For cross-table joins, use the table whose individual rows appear in the output.

HYPOTHESIS GUIDELINES:
- Each hypothesis should test a DIFFERENT angle on the user's question
- At least one hypothesis should cross-reference 2+ tables (e.g. RZLT sites near underpriced sales)
- At least one hypothesis should use aggregation/statistics (e.g. avg price per sqm by area)
- Hypotheses should be specific and testable, not vague
- If no location is specified, pick 2-3 promising Dublin areas or search city-wide
- For side site / infill / gap site queries, use the SIDE SITE DETECTION PATTERNS above — combine shape analysis (compactness), size filtering, adjacency, planning history, and RZLT overlap

QUERY PLAN OPTION (use for simple single-table queries):
For straightforward single-table queries with filters, you may use a structured "query_plan" instead of raw SQL.
Use raw SQL for complex cross-table joins, CTEs, window functions, or advanced spatial operations.
Use EITHER "sql" OR "query_plan" per query, not both.

Query plan format:
{{
  "query_plan": {{
    "table": "sold_properties",
    "select": ["id", "address", "sale_price", "floor_area_m2"],
    "filters": [
      {{"column": "sale_price", "op": ">", "value": 0}},
      {{"column": "floor_area_m2", "op": ">", "value": 0}}
    ],
    "spatial_filter": {{"type": "bbox", "bounds": {{"west": -6.3, "south": 53.3, "east": -6.2, "north": 53.35}}}},
    "order_by": "sale_price ASC",
    "limit": 25
  }}
}}
Spatial filter types: "bbox" (with bounds), "radius" (with center {{lng, lat}} and radius_m).
Filter ops: =, >, <, >=, <=, !=, LIKE, ILIKE, IS NOT NULL, BETWEEN (value is [min, max]).

RESPONSE FORMAT (valid JSON only, no markdown):
{{
  "hypotheses": [
    {{
      "name": "Short hypothesis name (5-8 words)",
      "rationale": "2-3 sentences explaining the developer logic.",
      "sql_queries": [
        {{
          "description": "What this specific query tests",
          "primary_table": "sold_properties",
          "sql": "SELECT ... full PostGIS SQL here ..."
        }}
      ]
    }}
  ]
}}
"""

# ── Phase 2: Evaluation Prompt (outputs flat ranked results) ──────────────────

EVALUATION_PROMPT_TEMPLATE = """You are LandOS AI, a Dublin property intelligence system. You just ran multiple analysis queries for a property developer.

ORIGINAL QUESTION: {user_query}

Here are the query results from different analytical angles:

{hypothesis_results}

YOUR TASK: Pick the BEST 8-15 sites across ALL queries and rank them. The developer just wants to see the top opportunities on a map — no theory, no hypotheses, just results.

RANKING CRITERIA (in order of importance):
1. Actionability — can a developer actually do something with this site?
2. Signal strength — does the data clearly show an opportunity (underpriced, large parcel, RZLT pressure, etc.)?
3. Cross-reference value — sites that appear in multiple queries or combine multiple signals rank higher.
4. Specificity — a specific site with an address beats an aggregated statistic.

RESPONSE FORMAT (valid JSON only, no markdown):
{{
  "type": "explore",
  "title": "Short punchy title (max 8 words)",
  "summary": "2-3 sentences. Lead with the best finding. Be specific: mention the area, price, size, or signal. This is what the developer reads first.",
  "sites": [
    {{
      "hypothesis_index": 0,
      "query_index": 0,
      "row_index": 0,
      "score": 85,
      "reason": "One sentence: why this site is an opportunity."
    }}
  ],
  "follow_ups": [
    {{
      "label": "Short label (max 6 words)",
      "prompt": "Full follow-up question to ask"
    }}
  ]
}}

RULES:
- "sites" must contain 8-15 entries, ranked best-first.
- hypothesis_index / query_index / row_index are 0-based indices into the input data.
- ONLY select rows that have actual site data (geometry, address, or parcel ref). Skip aggregate-only rows.
- Skip rows from queries that returned errors.
- "score" is 0-100 representing opportunity strength: 90+ = exceptional, 70-89 = strong, 50-69 = moderate, below 50 = weak. Score based on: size of opportunity, data confidence, actionability.
- "reason" should be developer-actionable: mention price, area, tax pressure, planning status etc.
- "follow_ups" should have exactly 3 entries.
- If no queries returned useful results, set sites to [] and explain in summary what the developer should try instead.

VISUALIZATION SELECTION:
After selecting sites, choose the best map visualization type for this data. Add these fields to your JSON:

"object_type": one of:
  - "markers" — ranked numbered pins (DEFAULT for most queries — specific sites, addresses, individual properties)
  - "polygon_highlights" — colored parcel/zone boundaries (use when primary_table is cadastral_freehold, cadastral_leasehold, rzlt, or dlr_planning_polygons AND geometry column is present in results — lets developer see actual parcel shapes)
  - "heatmap" — heat density overlay (use when results are 15+ point observations and the insight is WHERE concentration is highest, e.g. price hotspots, planning activity density)
  - "choropleth" — area polygons colored by metric (use when results are census_small_areas or urban_areas and a single normalized metric like vacancy_rate, apartment_pct, or employment_rate tells the story)

"available_views": array of view types valid for this dataset. Always include "markers" as a fallback (as long as lng/lat exist). Example: ["polygon_highlights", "markers"] or ["heatmap", "markers"] or ["choropleth", "markers"]

"choropleth_metric": string column name (e.g. "vacancy_rate", "apartment_pct") — ONLY set when object_type is "choropleth", otherwise null

"heatmap_weight_column": string column name (e.g. "sale_price", "_score", "site_area") — ONLY set when object_type is "heatmap", otherwise null

Add these 4 fields to your JSON response at the top level.
"""

# ── Agentic Loop: SQL Retry & Broaden Prompts ─────────────────────────────────

SQL_RETRY_PROMPT = """You are a PostGIS SQL expert fixing a broken query for a Dublin property intelligence system.

ORIGINAL QUERY:
{original_sql}

ERROR:
{error_message}

{db_schema}

SQL RULES:
- Always SELECT ST_AsGeoJSON(geometry) AS geometry for spatial columns
- Table/column names are lowercase
- Use ST_Transform(geometry, 2157) for area/distance calculations (Irish TM)
- Always include a geometry column in results
- LIMIT 25 max
- READ ONLY — no INSERT/UPDATE/DELETE

Return valid JSON only:
{{"corrected_sql": "SELECT ...", "explanation": "brief description of what you fixed"}}
"""

SQL_BROADEN_PROMPT = """You are a PostGIS SQL expert. A query returned 0 results and needs to be broadened.

ORIGINAL QUERY:
{original_sql}

QUERY INTENT: {description}

{db_schema}

The query returned no rows. Broaden it by:
1. Relaxing geographic constraints (larger area, remove neighborhood filter)
2. Relaxing numeric thresholds (lower minimums, higher maximums)
3. Removing the most restrictive WHERE clause
4. If searching a specific area, try Dublin-wide instead

Keep the same SELECT columns and geometry. LIMIT 25.

Return valid JSON only:
{{"corrected_sql": "SELECT ...", "explanation": "brief description of what you relaxed"}}
"""

FALLBACK_HYPOTHESIS_PROMPT = """You are LandOS AI. A property search query returned very few results. Generate ONE simple, broad PostGIS query to find relevant results.

USER QUERY: {user_query}

{db_schema}

SQL RULES:
- Always SELECT ST_AsGeoJSON(geometry) AS geometry
- Table/column names are lowercase
- Use ST_Transform(geometry, 2157) for area/distance
- LIMIT 25
- Keep it simple — one table, minimal WHERE clauses
- Focus on the most relevant table for the user's intent

Return valid JSON only:
{{"name": "Broad fallback search", "rationale": "Simplified search to find more results", "sql_queries": [{{"description": "...", "sql": "SELECT ..."}}]}}
"""


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class MapContext(BaseModel):
    viewport: dict | None = None      # {"sw": [lng, lat], "ne": [lng, lat]}
    zoom: float | None = None
    active_layers: list[str] = []
    selected_entity: dict | None = None  # {"table": str, "id": int}
    circle_analysis: dict | None = None  # {"center": [lng, lat], "radius_m": float}


class ConversationContext(BaseModel):
    last_query: str | None = None
    last_intent: str | None = None
    last_area: str | None = None
    last_table: str | None = None
    last_result_count: int | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    map_context: MapContext | None = None
    conversation_context: ConversationContext | None = None


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


POINT_TABLES = {"sold_properties", "dlr_planning_points"}


def compile_query_plan(plan: dict) -> str:
    """Compile a structured query plan dict into PostGIS SQL.

    Handles single-table queries with filters, spatial filters, ordering, and limits.
    Returns empty string if the plan is invalid.
    """
    table = plan.get("table", "")
    if table not in ALLOWED_TABLES:
        return ""

    select_cols = plan.get("select", [])
    filters = plan.get("filters", [])
    spatial = plan.get("spatial_filter", {})
    order_by = plan.get("order_by")
    limit = min(plan.get("limit", 25), 25)

    # Build SELECT columns
    if select_cols:
        cols = ", ".join(f"{table}.{c}" for c in select_cols)
    else:
        cols = f"{table}.*"

    # Always add geometry columns
    if table in POINT_TABLES:
        geo_cols = (
            f", ST_AsGeoJSON({table}.geom)::json AS geometry"
            f", ST_X({table}.geom) AS lng, ST_Y({table}.geom) AS lat"
        )
    else:
        geo_cols = (
            f", ST_AsGeoJSON({table}.geom)::json AS geometry"
            f", ST_X(ST_Centroid({table}.geom)) AS lng, ST_Y(ST_Centroid({table}.geom)) AS lat"
        )

    sql = f"SELECT {cols}{geo_cols} FROM {table}"

    # Build WHERE clauses
    where_parts = []

    # Spatial filter
    if spatial.get("type") == "bbox":
        b = spatial.get("bounds", {})
        where_parts.append(
            f"{table}.geom && ST_MakeEnvelope("
            f"{b.get('west', -6.5)}, {b.get('south', 53.2)}, "
            f"{b.get('east', -6.0)}, {b.get('north', 53.45)}, 4326)"
        )
    elif spatial.get("type") == "radius":
        center = spatial.get("center", {})
        radius = spatial.get("radius_m", 500)
        where_parts.append(
            f"ST_DWithin({table}.geom::geography, "
            f"ST_SetSRID(ST_MakePoint({center.get('lng', -6.26)}, {center.get('lat', 53.35)}), 4326)::geography, "
            f"{radius})"
        )

    # Column filters
    safe_ops = {"=", ">", "<", ">=", "<=", "!=", "LIKE", "ILIKE"}
    for f in filters:
        col = f.get("column", "")
        op = f.get("op", "=")
        val = f.get("value")
        if not col or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col):
            continue  # skip suspicious column names
        if op in safe_ops and val is not None:
            if isinstance(val, str):
                safe_val = val.replace("'", "''")
                where_parts.append(f"{table}.{col} {op} '{safe_val}'")
            elif isinstance(val, (int, float)):
                where_parts.append(f"{table}.{col} {op} {val}")
        elif op == "IS NOT NULL":
            where_parts.append(f"{table}.{col} IS NOT NULL")
        elif op == "BETWEEN" and isinstance(val, list) and len(val) == 2:
            where_parts.append(f"{table}.{col} BETWEEN {val[0]} AND {val[1]}")

    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)

    if order_by:
        # Only allow simple order_by expressions
        sql += f" ORDER BY {order_by}"

    sql += f" LIMIT {limit}"

    return sql


def execute_hypothesis_sql(sql: str) -> dict:
    """Execute a single SQL query safely. Returns {rows: [...], error: str|None, row_count: int}."""
    # Validate
    error = validate_sql(sql)
    if error:
        return {"rows": [], "error": error, "row_count": 0}

    # Strip trailing semicolons (common Gemini output that breaks subquery wrapping)
    clean_sql = sql.strip().rstrip(";")

    # Wrap with row limit
    wrapped_sql = f"SELECT * FROM ({clean_sql}) AS _hypothesis_result LIMIT 25"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '10s'")
            cur.execute("BEGIN READ ONLY")
            try:
                cur.execute(wrapped_sql)
                columns = [desc[0] for desc in cur.description]
                raw_rows = cur.fetchall()
            except Exception as e:
                cur.execute("ROLLBACK")
                cur.execute("RESET statement_timeout")
                # Try executing without wrapper (some CTEs don't wrap well)
                try:
                    cur.execute("BEGIN READ ONLY")
                    limited_sql = clean_sql
                    if "LIMIT" not in clean_sql.upper()[-30:]:
                        limited_sql = clean_sql + " LIMIT 25"
                    cur.execute(limited_sql)
                    columns = [desc[0] for desc in cur.description]
                    raw_rows = cur.fetchall()
                except Exception as e2:
                    cur.execute("ROLLBACK")
                    cur.execute("RESET statement_timeout")
                    put_conn(conn)
                    return {"rows": [], "error": str(e2)[:300], "row_count": 0}
            finally:
                try:
                    cur.execute("ROLLBACK")
                    cur.execute("RESET statement_timeout")
                except Exception:
                    pass
    except Exception as e:
        try:
            put_conn(conn)
        except Exception:
            pass
        return {"rows": [], "error": str(e)[:300], "row_count": 0}

    put_conn(conn)

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


def format_map_context(ctx: MapContext | None) -> str:
    """Format the user's current map state for injection into AI prompts."""
    if not ctx:
        return ""
    parts = ["\nMAP CONTEXT (user's current view):"]
    if ctx.viewport:
        sw = ctx.viewport.get("sw", [])
        ne = ctx.viewport.get("ne", [])
        if len(sw) == 2 and len(ne) == 2:
            parts.append(f"- Viewport: SW({sw[0]:.4f}, {sw[1]:.4f}) to NE({ne[0]:.4f}, {ne[1]:.4f})")
    if ctx.zoom is not None:
        parts.append(f"- Zoom level: {ctx.zoom}")
    if ctx.active_layers:
        parts.append(f"- Active layers: {', '.join(ctx.active_layers)}")
    if ctx.circle_analysis:
        c = ctx.circle_analysis
        center = c.get("center", [])
        if len(center) == 2:
            parts.append(f"- Circle analysis active: center ({center[0]:.4f}, {center[1]:.4f}), radius {c.get('radius_m', 0)}m")
    if ctx.selected_entity:
        parts.append(f"- Selected entity: {ctx.selected_entity.get('table')} id={ctx.selected_entity.get('id')}")
    parts.append("- Use viewport bounds as ST_MakeEnvelope spatial filter when the user's query is location-relative (e.g. 'around here', 'in this area', 'nearby', 'what I can see').")
    parts.append("- If the user specifies a named location (e.g. 'Rathmines', 'Blackrock'), use that instead of viewport bounds.")
    return "\n".join(parts)


DUBLIN_AREAS = [
    "Rathmines", "Ranelagh", "Blackrock", "Stillorgan", "Dundrum", "Sandyford",
    "Dun Laoghaire", "Dalkey", "Killiney", "Foxrock", "Leopardstown", "Cabinteely",
    "Shankill", "Bray", "Greystones", "Swords", "Malahide", "Howth", "Clontarf",
    "Drumcondra", "Phibsborough", "Stoneybatter", "Ringsend", "Ballsbridge",
    "Donnybrook", "Rathgar", "Terenure", "Crumlin", "Drimnagh", "Inchicore",
    "Lucan", "Clondalkin", "Tallaght", "Blanchardstown", "Castleknock",
    "Glasnevin", "Beaumont", "Raheny", "Sutton", "Portmarnock", "Deansgrange",
    "Monkstown", "Booterstown", "Sandymount", "Churchtown", "Goatstown",
]


def extract_area_from_query(query: str) -> str | None:
    """Extract the first Dublin area name found in a query string."""
    query_lower = query.lower()
    for area in DUBLIN_AREAS:
        if area.lower() in query_lower:
            return area
    return None


def format_conversation_context(ctx: ConversationContext | None) -> str:
    """Format previous conversation state for injection into AI prompts."""
    if not ctx or not ctx.last_query:
        return ""
    parts = ["\nCONVERSATION CONTEXT (previous interaction):"]
    if ctx.last_query:
        parts.append(f'- Last query: "{ctx.last_query}"')
    if ctx.last_intent:
        parts.append(f"- Last intent type: {ctx.last_intent}")
    if ctx.last_area:
        parts.append(f"- Last area focus: {ctx.last_area}")
    if ctx.last_table:
        parts.append(f"- Last primary data source: {ctx.last_table}")
    if ctx.last_result_count is not None:
        parts.append(f"- Last result count: {ctx.last_result_count}")
    parts.append('- Use this context to interpret follow-up queries like "show cheaper ones", "do the same for X", "filter to apartments".')
    return "\n".join(parts)


async def generate_hypotheses(messages: list[ChatMessage], map_context: MapContext | None = None, conv_context: ConversationContext | None = None) -> list[dict]:
    """Phase 1: Ask Gemini to form hypotheses and write SQL."""
    prompt = HYPOTHESIS_PROMPT
    context_text = format_map_context(map_context)
    conv_text = format_conversation_context(conv_context)
    if context_text:
        prompt = prompt + context_text
    if conv_text:
        prompt = prompt + conv_text
    result = await call_gemini_with_prompt(prompt, messages, max_tokens=4096)
    hypotheses = result.get("hypotheses", [])
    if not hypotheses:
        # Fallback: wrap the whole response as a single hypothesis
        hypotheses = [{
            "name": "General exploration",
            "rationale": "Broad search based on the user's query",
            "sql_queries": [],
        }]
    return hypotheses


# ── Agentic Loop: Retry, Broaden, Fallback ───────────────────────────────────

async def retry_failed_sql(original_sql: str, error_msg: str) -> dict:
    """Ask Gemini to fix a failed SQL query. Returns {corrected_sql, explanation}."""
    prompt = SQL_RETRY_PROMPT.format(
        original_sql=original_sql,
        error_message=error_msg,
        db_schema=DB_SCHEMA_PROMPT,
    )
    messages = [{"role": "user", "content": "Fix this SQL query."}]
    return await call_gemini_with_prompt(prompt, messages, max_tokens=1024)


async def broaden_empty_sql(original_sql: str, description: str) -> dict:
    """Ask Gemini to broaden a query that returned 0 results."""
    prompt = SQL_BROADEN_PROMPT.format(
        original_sql=original_sql,
        description=description,
        db_schema=DB_SCHEMA_PROMPT,
    )
    messages = [{"role": "user", "content": "Broaden this query to get results."}]
    return await call_gemini_with_prompt(prompt, messages, max_tokens=1024)


async def generate_fallback_hypothesis(user_query: str) -> dict | None:
    """Generate a single broad fallback hypothesis when results are too thin."""
    prompt = FALLBACK_HYPOTHESIS_PROMPT.format(
        user_query=user_query,
        db_schema=DB_SCHEMA_PROMPT,
    )
    messages = [{"role": "user", "content": "Generate a broad fallback query."}]
    result = await call_gemini_with_prompt(prompt, messages, max_tokens=1024)
    if result.get("sql_queries"):
        return result
    return None


# ── Intent Router & Handlers ─────────────────────────────────────────────────

async def route_intent(messages: list[ChatMessage]) -> dict:
    """Lightweight Gemini call to classify user intent."""
    result = await call_gemini_with_prompt(
        INTENT_ROUTER_PROMPT,
        messages,
        max_tokens=256,
    )
    intent = result.get("intent", "site_search")
    valid_intents = {"site_search", "area_comparison", "stat_question", "site_detail", "clarification", "follow_up"}
    if intent not in valid_intents:
        intent = "site_search"  # safe fallback
    return {"intent": intent, "reasoning": result.get("reasoning", "")}


async def handle_clarification(messages: list[ChatMessage]) -> dict:
    """Handle unclear/greeting messages with a conversational response."""
    result = await call_gemini_with_prompt(CLARIFICATION_PROMPT, messages, max_tokens=512)
    suggestions = result.get("suggestions", [])
    if not suggestions:
        suggestions = [
            "Find the largest RZLT sites in south Dublin",
            "What's the average house price in Blackrock?",
            "Compare Rathmines vs Ranelagh for property prices",
        ]
    return {
        "type": "clarify",
        "message": result.get("message", "I'm LandOS AI — I help property developers find and research sites across Dublin. What would you like to explore?"),
        "suggestions": suggestions,
    }


async def handle_stat_question(messages: list[ChatMessage], map_context: MapContext | None = None, conv_context: ConversationContext | None = None) -> dict:
    """Handle factual/statistical questions with a single query + conversational answer."""
    prompt = STAT_QUESTION_PROMPT_TEMPLATE.format(db_schema=DB_SCHEMA_PROMPT)
    context_text = format_map_context(map_context)
    conv_text = format_conversation_context(conv_context)
    if context_text:
        prompt += context_text
    if conv_text:
        prompt += conv_text

    result = await call_gemini_with_prompt(prompt, messages, max_tokens=1024)

    sql = result.get("sql", "")
    if not sql.strip():
        return {"type": "stat_answer", "message": "I couldn't form a query for that. Try rephrasing?", "stats": []}

    query_result = execute_hypothesis_sql(sql)
    if query_result.get("error"):
        return {"type": "stat_answer", "message": f"Query failed: {query_result['error'][:200]}. Try rephrasing your question.", "stats": []}

    rows = query_result.get("rows", [])
    if not rows:
        return {"type": "stat_answer", "message": "No data found for that query. Try a different area or broader criteria.", "stats": []}

    # Pass results back to Gemini for a natural language answer
    user_query = messages[-1].content if messages else ""
    answer_prompt = f"""The user asked: {user_query}

Query results: {json.dumps(rows[:15], default=str)[:3000]}

Write a concise, conversational answer using these results. Include specific numbers.
If there are key metrics, include them in the stats array.

RESPONSE FORMAT (valid JSON only):
{{"message": "Your conversational answer with specific numbers", "stats": [{{"label": "Metric name", "value": "Formatted value"}}]}}"""

    answer = await call_gemini_with_prompt(
        answer_prompt,
        [{"role": "user", "content": "Summarize these results."}],
        max_tokens=512,
    )

    return {
        "type": "stat_answer",
        "message": answer.get("message", json.dumps(rows[:5], default=str)),
        "stats": answer.get("stats", []),
        "query_stats": {"total": 1, "successful": 0 if query_result.get("error") else 1},
    }


async def handle_area_comparison(messages: list[ChatMessage], map_context: MapContext | None = None, conv_context: ConversationContext | None = None) -> dict:
    """Handle area-vs-area comparison queries."""
    prompt = AREA_COMPARISON_PROMPT_TEMPLATE.format(db_schema=DB_SCHEMA_PROMPT)
    context_text = format_map_context(map_context)
    conv_text = format_conversation_context(conv_context)
    if context_text:
        prompt += context_text
    if conv_text:
        prompt += conv_text

    result = await call_gemini_with_prompt(prompt, messages, max_tokens=2048)
    queries = result.get("queries", [])

    all_rows = []
    total = 0
    successful = 0
    for q in queries:
        sql = q.get("sql", "")
        if sql.strip():
            q["result"] = execute_hypothesis_sql(sql)
            total += 1
            if not q["result"].get("error"):
                successful += 1
                all_rows.extend(q["result"]["rows"])

    if not all_rows:
        return {
            "type": "area_comparison",
            "message": "Couldn't find enough data to compare those areas. Try being more specific about which areas to compare.",
            "comparison": [],
            "follow_ups": [],
        }

    # Synthesize comparison answer
    user_query = messages[-1].content if messages else ""
    comparison_prompt = f"""The user asked: {user_query}

Query results: {json.dumps(all_rows[:30], default=str)[:3000]}

Write a comparison summary. Highlight which area is stronger and why.
Structure the comparison data so each area has the same metrics.

RESPONSE FORMAT (valid JSON only):
{{"message": "2-3 sentence summary highlighting the key differences", "comparison": [{{"area": "Area Name", "metrics": {{"avg_price": "€450,000", "price_per_sqm": "€4,200", "num_sales": "142"}}}}], "follow_ups": [{{"label": "Short label", "prompt": "Full follow-up question"}}]}}"""

    answer = await call_gemini_with_prompt(
        comparison_prompt,
        [{"role": "user", "content": "Compare these areas."}],
        max_tokens=1024,
    )

    return {
        "type": "area_comparison",
        "message": answer.get("message", ""),
        "comparison": answer.get("comparison", []),
        "follow_ups": answer.get("follow_ups", []),
        "query_stats": {"total": total, "successful": successful},
    }


async def evaluate_hypotheses(user_query: str, hypotheses: list[dict]) -> dict:
    """Phase 3: Ask Gemini to rank the best sites across all hypotheses into a flat list."""
    # Build the hypothesis results summary for the evaluation prompt
    parts = []
    for i, h in enumerate(hypotheses):
        parts.append(f"## Analysis {i} (hypothesis_index={i}): {h['name']}")
        parts.append(f"Rationale: {h['rationale']}")
        for j, q in enumerate(h.get("sql_queries", [])):
            result = q.get("result", {})
            row_count = result.get("row_count", 0)
            error = result.get("error")
            parts.append(f"\nQuery {j} (query_index={j}): {q.get('description', 'unnamed')}")
            if error:
                parts.append(f"ERROR: {error}")
            elif row_count == 0:
                parts.append("No results returned.")
            else:
                rows = result.get("rows", [])
                summarized = []
                for row_idx, row in enumerate(rows):
                    summary_row = {k: v for k, v in row.items() if k != "geometry"}
                    summary_row["_row_index"] = row_idx
                    summarized.append(summary_row)
                parts.append(f"Results ({row_count} rows, row_index 0..{row_count-1}):")
                parts.append(json.dumps(summarized, indent=2, default=str)[:3000])
        parts.append("")

    hypothesis_results_text = "\n".join(parts)

    eval_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        user_query=user_query,
        hypothesis_results=hypothesis_results_text,
    )

    eval_messages = [{"role": "user", "content": "Rank the best sites from these results."}]
    result = await call_gemini_with_prompt(eval_prompt, eval_messages, max_tokens=4096)

    return result


def infer_table(row: dict) -> str:
    """Infer the source table from row columns."""
    if "address" in row and "sale_price" in row:
        return "sold_properties"
    elif "zone_desc" in row or "site_area" in row:
        return "rzlt"
    elif "plan_ref" in row or "decision" in row:
        return "dlr_planning_polygons"
    elif "nationalcadastralreference" in row or ("area_sqm" in row and "address" not in row):
        return "cadastral_freehold"
    return "unknown"


def extract_coords_from_geometry(row: dict):
    """If row has geometry but no lng/lat, extract coordinates from the GeoJSON geometry."""
    if row.get("lng") and row.get("lat"):
        return  # already has coords
    geom = row.get("geometry")
    if not geom or not isinstance(geom, dict):
        return
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates")
    if not coords:
        return
    if geom_type == "Point":
        row["lng"] = coords[0]
        row["lat"] = coords[1]
    elif geom_type in ("Polygon", "MultiPolygon"):
        # Use centroid approximation: average of first ring
        ring = coords[0] if geom_type == "Polygon" else coords[0][0]
        if ring:
            row["lng"] = sum(c[0] for c in ring) / len(ring)
            row["lat"] = sum(c[1] for c in ring) / len(ring)


def build_flat_results(hypotheses: list[dict], evaluation: dict) -> list[dict]:
    """Build a flat ranked list of sites from the evaluation's site picks."""
    site_picks = evaluation.get("sites", [])
    results = []

    for rank, pick in enumerate(site_picks):
        h_idx = pick.get("hypothesis_index", 0)
        q_idx = pick.get("query_index", 0)
        r_idx = pick.get("row_index", 0)
        reason = pick.get("reason", "")
        score = pick.get("score", 0)

        try:
            query = hypotheses[h_idx]["sql_queries"][q_idx]
            all_rows = query.get("result", {}).get("rows", [])
            if r_idx >= len(all_rows):
                continue
            row = dict(all_rows[r_idx])
        except (IndexError, KeyError):
            continue

        # Extract lng/lat from geometry if not present as columns
        extract_coords_from_geometry(row)

        # Skip rows without any spatial data
        if not row.get("lng") and not row.get("lat"):
            continue

        row["opportunity_reason"] = reason
        row["_score"] = score
        # Use tagged primary_table from Phase 1, fall back to inference
        try:
            tagged_table = hypotheses[h_idx]["sql_queries"][q_idx].get("primary_table")
        except (IndexError, KeyError):
            tagged_table = None
        row["_table"] = tagged_table if tagged_table in ALLOWED_TABLES else infer_table(row)
        row["_rank"] = rank
        results.append(row)

    # Fallback: if evaluation didn't pick sites, gather the best from each hypothesis
    if not results:
        for h in hypotheses:
            for q in h.get("sql_queries", []):
                rows = q.get("result", {}).get("rows", [])
                for r_idx, row in enumerate(rows[:5]):
                    row = dict(row)
                    extract_coords_from_geometry(row)
                    if not row.get("lng") and not row.get("lat"):
                        continue
                    row["_table"] = q.get("primary_table") if q.get("primary_table") in ALLOWED_TABLES else infer_table(row)
                    row["_rank"] = len(results)
                    row["_score"] = 50  # default for fallback
                    results.append(row)
                    if len(results) >= 15:
                        break
                if len(results) >= 15:
                    break
            if len(results) >= 15:
                break

    return results


def determine_object_type(evaluation: dict, results: list[dict]) -> tuple[str, list[str], str | None, str | None]:
    """Validate and finalize the object_type from Gemini's evaluation.

    Returns (object_type, available_views, choropleth_metric, heatmap_weight_column).
    Falls back to 'markers' if the selected type lacks required data.
    """
    valid_types = {"markers", "polygon_highlights", "heatmap", "choropleth"}
    obj_type = evaluation.get("object_type", "markers")
    if obj_type not in valid_types:
        obj_type = "markers"

    choropleth_metric = evaluation.get("choropleth_metric")
    heatmap_weight_column = evaluation.get("heatmap_weight_column")

    # Safety: polygon_highlights requires geometry on results
    if obj_type == "polygon_highlights":
        has_geometry = any(isinstance(r.get("geometry"), dict) for r in results)
        if not has_geometry:
            obj_type = "markers"

    # Safety: choropleth requires polygon geometry
    if obj_type == "choropleth":
        has_poly = any(
            isinstance(r.get("geometry"), dict)
            and r["geometry"].get("type") in ("Polygon", "MultiPolygon")
            for r in results
        )
        if not has_poly:
            obj_type = "markers"
        if obj_type == "choropleth" and choropleth_metric:
            # Verify the metric column actually exists in results
            if not any(choropleth_metric in r for r in results):
                obj_type = "markers"

    # Safety: heatmap requires a weight column
    if obj_type == "heatmap" and heatmap_weight_column:
        if not any(heatmap_weight_column in r for r in results):
            obj_type = "markers"
    elif obj_type == "heatmap" and not heatmap_weight_column:
        heatmap_weight_column = "_score"  # fallback weight

    # Build available_views: primary type + markers fallback
    available_views = evaluation.get("available_views", [])
    if not isinstance(available_views, list):
        available_views = []
    # Always include markers if lng/lat available
    if results and results[0].get("lng"):
        if "markers" not in available_views:
            available_views.append("markers")
    # Ensure primary type is first
    if obj_type != "markers" and obj_type not in available_views:
        available_views.insert(0, obj_type)
    elif obj_type in available_views and available_views[0] != obj_type:
        available_views.remove(obj_type)
        available_views.insert(0, obj_type)

    # Clear metric/weight if not relevant
    if obj_type != "choropleth":
        choropleth_metric = None
    if obj_type != "heatmap":
        heatmap_weight_column = None

    return obj_type, available_views, choropleth_metric, heatmap_weight_column


@app.post("/api/ai/chat")
async def ai_chat(req: ChatRequest):
    """AI-powered property analytics chat with intent routing.

    Routes queries to specialized handlers based on intent classification:
    - site_search/follow_up/site_detail → 3-phase hypothesis pipeline
    - stat_question → single query + conversational answer
    - area_comparison → aggregation queries + comparison table
    - clarification → conversational response + suggestions
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    # Get the user's latest question for evaluation context
    user_query = ""
    for msg in reversed(req.messages):
        if msg.role == "user":
            user_query = msg.content
            break

    # Step 1: Route intent
    routing = await route_intent(req.messages)
    intent = routing["intent"]

    conv_ctx = req.conversation_context

    # Helper to build conversation_context for the response
    def build_response_context(result_count=0, table=None):
        return {
            "last_query": user_query,
            "last_intent": intent,
            "last_area": extract_area_from_query(user_query),
            "last_table": table,
            "last_result_count": result_count,
        }

    # Step 2: Dispatch to handler based on intent
    if intent == "clarification":
        resp = await handle_clarification(req.messages)
        resp["conversation_context"] = build_response_context()
        return resp

    if intent == "stat_question":
        resp = await handle_stat_question(req.messages, req.map_context, conv_ctx)
        resp["conversation_context"] = build_response_context()
        return resp

    if intent == "area_comparison":
        resp = await handle_area_comparison(req.messages, req.map_context, conv_ctx)
        resp["conversation_context"] = build_response_context(
            result_count=len(resp.get("comparison", [])),
        )
        return resp

    # site_search, follow_up, site_detail → full 3-phase hypothesis pipeline
    hypotheses = await generate_hypotheses(req.messages, req.map_context, conv_ctx)

    # Phase 2: Execute all SQL queries safely (supports both raw SQL and query plans)
    total_queries = 0
    successful_queries = 0
    for hypothesis in hypotheses:
        for query in hypothesis.get("sql_queries", []):
            sql = query.get("sql", "")
            query_plan = query.get("query_plan")

            # Compile query plan to SQL if no raw SQL provided
            if query_plan and not sql.strip():
                sql = compile_query_plan(query_plan)
                query["sql"] = sql  # store compiled SQL for debugging/evaluation

            if sql.strip():
                query["result"] = execute_hypothesis_sql(sql)
                total_queries += 1
                if not query["result"].get("error"):
                    successful_queries += 1

    # Phase 3: Evaluate results and rank best sites
    evaluation = await evaluate_hypotheses(user_query, hypotheses)

    # Build the flat results array with geometry for the frontend map
    results = build_flat_results(hypotheses, evaluation)
    obj_type, available_views, choropleth_metric, heatmap_weight_col = determine_object_type(evaluation, results)

    # Return clean response
    return {
        "type": "map_realization",
        "object_type": obj_type,
        "available_views": available_views,
        "choropleth_metric": choropleth_metric,
        "heatmap_weight_column": heatmap_weight_col,
        "title": evaluation.get("title", "Analysis Results"),
        "summary": evaluation.get("summary", "Analysis complete."),
        "results": results,
        "follow_ups": evaluation.get("follow_ups", []),
        "query_stats": {
            "total": total_queries,
            "successful": successful_queries,
        },
        "intent": intent,
        "conversation_context": build_response_context(
            result_count=len(results),
            table=results[0].get("_table") if results else None,
        ),
    }


@app.post("/api/ai/chat/stream")
async def ai_chat_stream(req: ChatRequest):
    """SSE streaming version of the AI chat endpoint.

    Sends real-time progress events as the pipeline executes:
    - status: phase updates (routing, hypotheses, executing, ranking)
    - intent: classification result
    - hypotheses: count and names of generated hypotheses
    - query_complete: per-query progress
    - result: final response payload
    - done: stream complete
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    async def event_stream():
        def sse(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

        user_query = ""
        for msg in reversed(req.messages):
            if msg.role == "user":
                user_query = msg.content
                break

        conv_ctx = req.conversation_context

        def build_response_context(result_count=0, table=None):
            return {
                "last_query": user_query,
                "last_intent": None,
                "last_area": extract_area_from_query(user_query),
                "last_table": table,
                "last_result_count": result_count,
            }

        # Step 1: Route intent
        yield sse("status", {"phase": "routing", "message": "Understanding your query..."})
        try:
            routing = await route_intent(req.messages)
        except Exception:
            routing = {"intent": "site_search", "reasoning": "fallback"}
        intent = routing["intent"]
        yield sse("intent", {"intent": intent, "reasoning": routing.get("reasoning", "")})

        # Update context builder with intent
        def build_response_context_with_intent(result_count=0, table=None):
            return {
                "last_query": user_query,
                "last_intent": intent,
                "last_area": extract_area_from_query(user_query),
                "last_table": table,
                "last_result_count": result_count,
            }

        # Handle non-explore intents quickly
        if intent == "clarification":
            yield sse("status", {"phase": "responding", "message": "Thinking..."})
            resp = await handle_clarification(req.messages)
            resp["conversation_context"] = build_response_context_with_intent()
            yield sse("result", resp)
            yield sse("done", {})
            return

        if intent == "stat_question":
            yield sse("status", {"phase": "querying", "message": "Running query..."})
            resp = await handle_stat_question(req.messages, req.map_context, conv_ctx)
            resp["conversation_context"] = build_response_context_with_intent()
            yield sse("result", resp)
            yield sse("done", {})
            return

        if intent == "area_comparison":
            yield sse("status", {"phase": "querying", "message": "Comparing areas..."})
            resp = await handle_area_comparison(req.messages, req.map_context, conv_ctx)
            resp["conversation_context"] = build_response_context_with_intent(
                result_count=len(resp.get("comparison", [])),
            )
            yield sse("result", resp)
            yield sse("done", {})
            return

        # Explore pipeline
        yield sse("status", {"phase": "hypotheses", "message": "Forming spatial hypotheses..."})
        try:
            hypotheses = await generate_hypotheses(req.messages, req.map_context, conv_ctx)
        except Exception as e:
            yield sse("error", {"message": f"Failed to generate hypotheses: {e}"})
            yield sse("done", {})
            return
        yield sse("hypotheses", {
            "count": len(hypotheses),
            "names": [h.get("name", "") for h in hypotheses],
        })

        # Phase 2: Execute SQL with agentic retry loop
        yield sse("status", {"phase": "executing", "message": "Testing hypotheses against the database..."})
        total_queries = 0
        successful_queries = 0
        MAX_SQL_RETRIES = 2

        for h_idx, hypothesis in enumerate(hypotheses):
            for q_idx, query in enumerate(hypothesis.get("sql_queries", [])):
                sql = query.get("sql", "")
                query_plan = query.get("query_plan")
                if query_plan and not sql.strip():
                    sql = compile_query_plan(query_plan)
                    query["sql"] = sql
                if not sql.strip():
                    continue

                # Agentic retry loop
                result = None
                for attempt in range(MAX_SQL_RETRIES + 1):
                    result = execute_hypothesis_sql(sql)
                    total_queries += 1

                    # Case 1: SQL error — ask Gemini to fix it
                    if result.get("error") and attempt < MAX_SQL_RETRIES:
                        yield sse("tool_action", {
                            "action": "sql_retry",
                            "attempt": attempt + 1,
                            "error": result["error"][:200],
                            "hypothesis": hypothesis.get("name", ""),
                        })
                        try:
                            fix = await retry_failed_sql(sql, result["error"])
                            new_sql = fix.get("corrected_sql", "")
                            if new_sql.strip():
                                sql = new_sql
                                continue  # retry with corrected SQL
                        except Exception:
                            pass
                        break  # couldn't get a fix from Gemini

                    # Case 2: Empty results — ask Gemini to broaden
                    elif result["row_count"] == 0 and not result.get("error") and attempt == 0:
                        yield sse("tool_action", {
                            "action": "sql_broaden",
                            "hypothesis": hypothesis.get("name", ""),
                            "description": query.get("description", ""),
                        })
                        try:
                            broader = await broaden_empty_sql(sql, query.get("description", ""))
                            new_sql = broader.get("corrected_sql", "")
                            if new_sql.strip():
                                sql = new_sql
                                continue  # retry with broadened SQL
                        except Exception:
                            pass
                        break  # couldn't broaden

                    # Case 3: Success or exhausted retries
                    else:
                        break

                query["result"] = result
                if result and not result.get("error"):
                    successful_queries += 1
                    yield sse("query_complete", {
                        "hypothesis_index": h_idx,
                        "query_index": q_idx,
                        "hypothesis_total": len(hypotheses),
                        "row_count": result["row_count"],
                        "description": query.get("description", ""),
                    })

        # Quality check: if too few results, try a fallback hypothesis
        total_rows = sum(
            q.get("result", {}).get("row_count", 0)
            for h in hypotheses for q in h.get("sql_queries", [])
            if not q.get("result", {}).get("error")
        )

        if total_rows == 0:
            yield sse("tool_action", {
                "action": "quality_check",
                "message": "No results found. Trying a broader approach...",
            })
            try:
                fallback = await generate_fallback_hypothesis(user_query)
                if fallback:
                    for q in fallback.get("sql_queries", []):
                        fb_sql = q.get("sql", "")
                        if fb_sql.strip():
                            q["result"] = execute_hypothesis_sql(fb_sql)
                            total_queries += 1
                            if not q["result"].get("error"):
                                successful_queries += 1
                    hypotheses.append(fallback)
            except Exception:
                pass
        elif total_rows < 3:
            yield sse("tool_action", {
                "action": "quality_check",
                "message": f"Only {total_rows} result{'s' if total_rows != 1 else ''} found. Trying a broader approach...",
            })
            try:
                fallback = await generate_fallback_hypothesis(user_query)
                if fallback:
                    for q in fallback.get("sql_queries", []):
                        fb_sql = q.get("sql", "")
                        if fb_sql.strip():
                            q["result"] = execute_hypothesis_sql(fb_sql)
                            total_queries += 1
                            if not q["result"].get("error"):
                                successful_queries += 1
                    hypotheses.append(fallback)
            except Exception:
                pass

        # Phase 3: Rank
        yield sse("status", {"phase": "ranking", "message": "Ranking and visualizing results..."})
        try:
            evaluation = await evaluate_hypotheses(user_query, hypotheses)
        except Exception as e:
            yield sse("error", {"message": f"Failed to rank results: {e}"})
            yield sse("done", {})
            return
        results = build_flat_results(hypotheses, evaluation)
        obj_type, available_views, choropleth_metric, heatmap_weight_col = determine_object_type(evaluation, results)

        yield sse("result", {
            "type": "map_realization",
            "object_type": obj_type,
            "available_views": available_views,
            "choropleth_metric": choropleth_metric,
            "heatmap_weight_column": heatmap_weight_col,
            "title": evaluation.get("title", "Analysis Results"),
            "summary": evaluation.get("summary", "Analysis complete."),
            "results": results,
            "follow_ups": evaluation.get("follow_ups", []),
            "query_stats": {"total": total_queries, "successful": successful_queries},
            "intent": intent,
            "conversation_context": build_response_context_with_intent(
                result_count=len(results),
                table=results[0].get("_table") if results else None,
            ),
        })
        yield sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
