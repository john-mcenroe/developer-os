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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
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


@app.get("/api/osm_buildings")
def get_osm_buildings(bbox: str = Query(..., description="west,south,east,north")):
    """Return OSM building footprints as GeoJSON within a bounding box."""
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
                    osm_id AS id,
                    building,
                    name,
                    addr_housenumber,
                    addr_street,
                    addr_city,
                    building_levels,
                    amenity,
                    area_sqm,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM osm_buildings
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 3000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        (
            osm_id, building, name, addr_housenumber, addr_street,
            addr_city, building_levels, amenity, area_sqm, geometry,
        ) = row
        features.append(
            {
                "type": "Feature",
                "id": osm_id,
                "geometry": geometry,
                "properties": {
                    "id": osm_id,
                    "building": building,
                    "name": name,
                    "addr_housenumber": addr_housenumber,
                    "addr_street": addr_street,
                    "addr_city": addr_city,
                    "building_levels": building_levels,
                    "amenity": amenity,
                    "area_sqm": round(area_sqm, 1) if area_sqm else None,
                },
            }
        )

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/osm_amenities")
def get_osm_amenities(bbox: str = Query(..., description="west,south,east,north")):
    """Return OSM amenities as GeoJSON within a bounding box."""
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
                    osm_id, amenity, name, addr_street, addr_housenumber,
                    addr_city, cuisine, healthcare, operator, brand,
                    opening_hours,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM osm_amenities
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                  AND amenity NOT IN ('parking_space', 'bench', 'waste_basket', 'bicycle_parking')
                LIMIT 2000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        (osm_id, amenity, name, addr_street, addr_housenumber,
         addr_city, cuisine, healthcare, operator, brand,
         opening_hours, geometry) = row
        features.append({
            "type": "Feature",
            "id": osm_id,
            "geometry": geometry,
            "properties": {
                "id": osm_id,
                "amenity": amenity,
                "name": name or amenity,
                "addr_street": addr_street,
                "addr_housenumber": addr_housenumber,
                "addr_city": addr_city,
                "cuisine": cuisine,
                "healthcare": healthcare,
                "operator": operator,
                "brand": brand,
                "opening_hours": opening_hours,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/osm_transport")
def get_osm_transport(bbox: str = Query(..., description="west,south,east,north")):
    """Return OSM transport stops as GeoJSON within a bounding box."""
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
                    osm_id, transport_type, name, network, operator,
                    route_ref, railway, highway,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM osm_transport
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
        (osm_id, transport_type, name, network, operator,
         route_ref, railway, highway, geometry) = row
        # Friendly label
        label = name or transport_type or "Stop"
        features.append({
            "type": "Feature",
            "id": osm_id,
            "geometry": geometry,
            "properties": {
                "id": osm_id,
                "transport_type": transport_type,
                "name": label,
                "network": network,
                "operator": operator,
                "route_ref": route_ref,
                "railway": railway,
                "highway": highway,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/flood_zones")
def get_flood_zones(bbox: str = Query(..., description="west,south,east,north")):
    """Return OPW flood zone polygons as GeoJSON within a bounding box."""
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
                    id, flood_zone, flood_type, source, aep,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM flood_zones
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 3000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        fid, flood_zone, flood_type, source, aep, geometry = row
        features.append({
            "type": "Feature",
            "id": fid,
            "geometry": geometry,
            "properties": {
                "id": fid,
                "flood_zone": flood_zone,
                "flood_type": flood_type,
                "source": source,
                "aep": aep,
                "label": f"Flood Zone {flood_zone} ({flood_type})",
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/niah_buildings")
def get_niah_buildings(bbox: str = Query(..., description="west,south,east,north")):
    """Return NIAH protected structures as GeoJSON within a bounding box."""
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
                    ogc_fid, reg_no, name, number, street1, town, county,
                    original_type, in_use_as_type, rating,
                    datefrom, dateto, description, image_link, website_link,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM niah_buildings
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
        (fid, reg_no, name, number, street1, town, county,
         original_type, in_use_as_type, rating,
         datefrom, dateto, description, image_link, website_link, geometry) = row
        label = name or f"{number or ''} {street1 or ''}".strip() or f"NIAH {reg_no}"
        features.append({
            "type": "Feature",
            "id": fid,
            "geometry": geometry,
            "properties": {
                "id": fid,
                "reg_no": reg_no,
                "name": label,
                "number": number,
                "street": street1,
                "town": town,
                "county": county,
                "original_type": original_type,
                "in_use_as": in_use_as_type,
                "rating": rating,
                "date_from": datefrom,
                "date_to": dateto,
                "description": (description[:300] + "...") if description and len(description) > 300 else description,
                "image_link": image_link,
                "website_link": website_link,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/zoning")
def get_zoning(bbox: str = Query(..., description="west,south,east,north")):
    """Return zoning designation polygons as GeoJSON within a bounding box."""
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
                    id, zone_code, zone_description, gzt_code, gzt_category,
                    local_authority, hectares,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM zoning
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 3000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        (fid, zone_code, zone_desc, gzt_code, gzt_cat,
         la, hectares, geometry) = row
        features.append({
            "type": "Feature",
            "id": fid,
            "geometry": geometry,
            "properties": {
                "id": fid,
                "zone_code": zone_code,
                "zone_description": zone_desc,
                "gzt_code": gzt_code,
                "gzt_category": gzt_cat,
                "local_authority": la,
                "hectares": float(hectares) if hectares else None,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/commercial_valuations")
def get_commercial_valuations(bbox: str = Query(..., description="west,south,east,north")):
    """Return commercial property valuations as GeoJSON within a bounding box."""
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
                    property_number, category, uses, valuation, address, eircode,
                    local_authority, car_park, total_floor_area,
                    publication_date, valuation_date, floor_details,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM commercial_valuations
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
        (pn, cat, uses, val, addr, eircode, la, car_park, floor_area,
         pub_date, val_date, floor_details, geometry) = row
        # Parse floor details JSON
        import json as _json
        floors = None
        if floor_details:
            try:
                floors = _json.loads(floor_details) if isinstance(floor_details, str) else floor_details
            except Exception:
                floors = None
        features.append({
            "type": "Feature",
            "id": pn,
            "geometry": geometry,
            "properties": {
                "id": pn,
                "property_number": pn,
                "category": cat,
                "uses": uses,
                "valuation": val,
                "address": addr,
                "eircode": eircode,
                "local_authority": la,
                "car_park": car_park,
                "total_floor_area": float(floor_area) if floor_area else None,
                "publication_date": pub_date,
                "valuation_date": val_date,
                "floor_details": floors,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/schools")
def get_schools(bbox: str = Query(..., description="west,south,east,north")):
    """Return schools as GeoJSON within a bounding box."""
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
                    id, roll_number, name, address, county, eircode,
                    school_type, school_level, deis, ethos, patron,
                    enrolment, female, male,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM schools
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
        (fid, roll, name, address, county, eircode,
         stype, level, deis, ethos, patron,
         enrolment, female, male, geometry) = row
        features.append({
            "type": "Feature",
            "id": fid,
            "geometry": geometry,
            "properties": {
                "id": fid,
                "roll_number": roll,
                "name": name,
                "address": address,
                "county": county,
                "eircode": eircode,
                "school_type": stype,
                "school_level": level,
                "deis": deis,
                "ethos": ethos,
                "patron": patron,
                "enrolment": enrolment,
                "female": female,
                "male": male,
            },
        })

    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/landuse")
def get_landuse(bbox: str = Query(..., description="west,south,east,north")):
    """Return OSM land use polygons as GeoJSON within a bounding box."""
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
                    ogc_fid, osm_id, fclass, name,
                    ST_AsGeoJSON(geom)::json AS geometry
                FROM landuse
                WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                LIMIT 3000
                """,
                (west, south, east, north),
            )
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    features = []
    for row in rows:
        fid, osm_id, fclass, name, geometry = row
        features.append({
            "type": "Feature",
            "id": fid,
            "geometry": geometry,
            "properties": {
                "id": fid,
                "osm_id": osm_id,
                "landuse": fclass,
                "name": name or fclass,
            },
        })

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


def query_national_planning_bbox(table: str, west, south, east, north):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    ogc_fid AS id,
                    planningauthority,
                    applicationnumber,
                    developmentdescription,
                    developmentaddress,
                    applicationstatus,
                    applicationtype,
                    decision,
                    numresidentialunits,
                    floorarea,
                    areaofsite,
                    linkappdetails,
                    to_char(to_timestamp(receiveddate/1000), 'YYYY-MM-DD') AS received_date,
                    to_char(to_timestamp(decisiondate/1000), 'YYYY-MM-DD') AS decision_date,
                    to_char(to_timestamp(grantdate/1000), 'YYYY-MM-DD') AS grant_date,
                    to_char(to_timestamp(expirydate/1000), 'YYYY-MM-DD') AS expiry_date,
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
            fid, planningauthority, applicationnumber, developmentdescription,
            developmentaddress, applicationstatus, applicationtype, decision,
            numresidentialunits, floorarea, areaofsite, linkappdetails,
            received_date, decision_date, grant_date, expiry_date, geometry,
        ) = row
        features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": geometry,
                "properties": {
                    "id": fid,
                    "planningauthority": planningauthority,
                    "applicationnumber": applicationnumber,
                    "developmentdescription": developmentdescription,
                    "developmentaddress": developmentaddress,
                    "applicationstatus": applicationstatus,
                    "applicationtype": applicationtype,
                    "decision": decision,
                    "numresidentialunits": numresidentialunits,
                    "floorarea": floorarea,
                    "areaofsite": areaofsite,
                    "linkappdetails": linkappdetails,
                    "received_date": received_date,
                    "decision_date": decision_date,
                    "grant_date": grant_date,
                    "expiry_date": expiry_date,
                },
            }
        )
    return features


@app.get("/api/national_planning_points")
def get_national_planning_points(bbox: str = Query(..., description="west,south,east,north")):
    """Return national planning application points within the bounding box as GeoJSON."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")
    features = query_national_planning_bbox("national_planning_points", west, south, east, north)
    return JSONResponse({"type": "FeatureCollection", "features": features})


@app.get("/api/national_planning_polygons")
def get_national_planning_polygons(bbox: str = Query(..., description="west,south,east,north")):
    """Return national planning application polygons within the bounding box as GeoJSON."""
    try:
        west, south, east, north = parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")
    features = query_national_planning_bbox("national_planning_polygons", west, south, east, north)
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

            # 5) Census — small area containing this parcel centroid + county benchmarks
            cur.execute(
                """
                SELECT
                    sa_pub2022,
                    county_english,
                    total_population,
                    population_density,
                    total_households,
                    avg_household_size,
                    apartment_pct,
                    owner_occupied_pct,
                    rented_pct,
                    vacancy_rate,
                    employment_rate,
                    third_level_pct,
                    wfh_pct,
                    avg_rooms,
                    health_good_pct,
                    age_0_14,
                    age_15_24,
                    age_25_44,
                    age_45_64,
                    age_65_plus,
                    built_pre_1919,
                    built_1919_1945,
                    built_1946_1970,
                    built_1971_2000,
                    built_2001_2015,
                    built_2016_plus
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
                _f = lambda v: float(v) if v is not None else None
                _i = lambda v: int(v) if v is not None else None
                county_name = census_row[1]
                census = {
                    "small_area_id": census_row[0],
                    "county": county_name,
                    "total_population": _i(census_row[2]),
                    "population_density": _f(census_row[3]),
                    "total_households": _i(census_row[4]),
                    "avg_household_size": _f(census_row[5]),
                    "apartment_pct": _f(census_row[6]),
                    "owner_occupied_pct": _f(census_row[7]),
                    "rented_pct": _f(census_row[8]),
                    "vacancy_rate": _f(census_row[9]),
                    "employment_rate": _f(census_row[10]),
                    "third_level_pct": _f(census_row[11]),
                    "wfh_pct": _f(census_row[12]),
                    "avg_rooms": _f(census_row[13]),
                    "health_good_pct": _f(census_row[14]),
                    "age_0_14": _i(census_row[15]),
                    "age_15_24": _i(census_row[16]),
                    "age_25_44": _i(census_row[17]),
                    "age_45_64": _i(census_row[18]),
                    "age_65_plus": _i(census_row[19]),
                    "built_pre_1919": _i(census_row[20]),
                    "built_1919_1945": _i(census_row[21]),
                    "built_1946_1970": _i(census_row[22]),
                    "built_1971_2000": _i(census_row[23]),
                    "built_2001_2015": _i(census_row[24]),
                    "built_2016_plus": _i(census_row[25]),
                }

                # County-level benchmarks for comparison
                if county_name:
                    cur.execute(
                        """
                        SELECT
                            ROUND(AVG(population_density)::numeric, 0),
                            ROUND(AVG(apartment_pct)::numeric, 1),
                            ROUND(AVG(owner_occupied_pct)::numeric, 1),
                            ROUND(AVG(rented_pct)::numeric, 1),
                            ROUND(AVG(vacancy_rate)::numeric, 1),
                            ROUND(AVG(employment_rate)::numeric, 1),
                            ROUND(AVG(third_level_pct)::numeric, 1),
                            ROUND(AVG(wfh_pct)::numeric, 1),
                            ROUND(AVG(avg_household_size)::numeric, 2),
                            ROUND(AVG(avg_rooms)::numeric, 1),
                            ROUND(AVG(health_good_pct)::numeric, 1)
                        FROM census_small_areas
                        WHERE county_english = %s
                          AND total_population IS NOT NULL
                          AND total_population > 0
                        """,
                        (county_name,),
                    )
                    bench_row = cur.fetchone()
                    if bench_row:
                        census["county_benchmarks"] = {
                            "population_density": _f(bench_row[0]),
                            "apartment_pct": _f(bench_row[1]),
                            "owner_occupied_pct": _f(bench_row[2]),
                            "rented_pct": _f(bench_row[3]),
                            "vacancy_rate": _f(bench_row[4]),
                            "employment_rate": _f(bench_row[5]),
                            "third_level_pct": _f(bench_row[6]),
                            "wfh_pct": _f(bench_row[7]),
                            "avg_household_size": _f(bench_row[8]),
                            "avg_rooms": _f(bench_row[9]),
                            "health_good_pct": _f(bench_row[10]),
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


@app.get("/api/site/enrich")
def get_site_enrichment(
    lng: float = Query(..., description="Longitude"),
    lat: float = Query(..., description="Latitude"),
    radius: int = Query(500, ge=100, le=2000, description="Search radius in metres"),
):
    """Universal site enrichment: nearby planning, sales, zoning, census, commercial context for any point."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            centroid_2157 = "ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 2157)"
            # Pre-compute a bbox in 4326 for spatial index hits (~0.006° ≈ 500m at Dublin latitude)
            deg_buf = radius / 111000.0 * 1.2  # rough metres-to-degrees with safety margin
            bbox_filter = f"geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)"
            bbox_params = (lng - deg_buf, lat - deg_buf, lng + deg_buf, lat + deg_buf)

            # 1) RZLT overlap — bbox pre-filter then exact distance
            cur.execute(
                f"""
                SELECT zone_desc, site_area, local_authority_name, zone_gzt
                FROM rzlt
                WHERE {bbox_filter}
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
                LIMIT 5
                """,
                (*bbox_params, lng, lat, radius),
            )
            rzlt_overlap = [
                {"zone_desc": r[0], "site_area": r[1], "local_authority_name": r[2], "zone_gzt": r[3]}
                for r in cur.fetchall()
            ]

            # 2) Nearby planning — merge DLR + national, sorted by distance
            planning_queries = []
            # DLR planning
            cur.execute(
                f"""
                SELECT
                    plan_ref AS ref, decision, descrptn AS description,
                    reg_date::text AS date, NULL AS dev_description,
                    ROUND(ST_Distance(ST_Transform(geom, 2157), {centroid_2157})::numeric, 0) AS distance_m,
                    'DLR' AS source
                FROM dlr_planning_polygons
                WHERE ST_DWithin(ST_Transform(geom, 2157), {centroid_2157}, %s)
                ORDER BY distance_m
                LIMIT 5
                """,
                (lng, lat, lng, lat, radius),
            )
            planning_queries.extend(cur.fetchall())
            # National planning — bbox pre-filter for index hit on 483k row table
            cur.execute(
                f"""
                SELECT
                    applicationnumber AS ref, decision, NULL AS description,
                    to_timestamp(receiveddate/1000)::date::text AS date,
                    developmentdescription AS dev_description,
                    ROUND(ST_Distance(ST_Transform(geom, 2157), {centroid_2157})::numeric, 0) AS distance_m,
                    planningauthority AS source
                FROM national_planning_polygons
                WHERE {bbox_filter}
                  AND ST_DWithin(ST_Transform(geom, 2157), {centroid_2157}, %s)
                ORDER BY distance_m
                LIMIT 5
                """,
                (*bbox_params, lng, lat, lng, lat, radius),
            )
            planning_queries.extend(cur.fetchall())
            # Combine and sort by distance, take top 8
            planning_queries.sort(key=lambda r: r[5] if r[5] is not None else 99999)
            nearby_planning = [
                {
                    "ref": r[0], "decision": r[1], "description": r[2] or r[4],
                    "date": r[3], "distance_m": int(r[5]) if r[5] is not None else None,
                    "source": r[6],
                }
                for r in planning_queries[:8]
            ]

            # 3) Sales stats within radius
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS cnt,
                    COALESCE(ROUND(AVG(sale_price)), 0) AS avg_sale,
                    COALESCE(ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sale_price)), 0) AS median_sale,
                    COALESCE(ROUND(AVG(CASE WHEN floor_area_m2 > 0 THEN sale_price / floor_area_m2 END)), 0) AS avg_price_sqm
                FROM sold_properties
                WHERE ST_DWithin(ST_Transform(geom, 2157), {centroid_2157}, %s)
                AND sale_price > 0 AND sale_price < 10000000
                """,
                (lng, lat, radius),
            )
            sales_agg = cur.fetchone()
            sales_count, avg_sale, median_sale, avg_psm = sales_agg

            # Top 5 nearest recent sales
            cur.execute(
                f"""
                SELECT
                    address, sale_price, sale_date::text, property_type,
                    ROUND(ST_Distance(ST_Transform(geom, 2157), {centroid_2157})::numeric, 0) AS distance_m
                FROM sold_properties
                WHERE ST_DWithin(ST_Transform(geom, 2157), {centroid_2157}, %s)
                AND sale_price > 0 AND sale_price < 10000000
                ORDER BY sale_date DESC NULLS LAST
                LIMIT 5
                """,
                (lng, lat, lng, lat, radius),
            )
            recent_sales = [
                {
                    "address": r[0], "sale_price": r[1], "sale_date": r[2],
                    "property_type": r[3], "distance_m": int(r[4]) if r[4] is not None else None,
                }
                for r in cur.fetchall()
            ]

            # 4) Zoning
            cur.execute(
                """
                SELECT zone_code, zone_description, local_authority
                FROM zoning
                WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                LIMIT 3
                """,
                (lng, lat),
            )
            zoning_rows = cur.fetchall()
            zoning = [
                {"zone_code": r[0], "zone_description": r[1], "local_authority": r[2]}
                for r in zoning_rows
            ]

            # 5) Census
            cur.execute(
                """
                SELECT
                    total_population, population_density,
                    apartment_pct, owner_occupied_pct, rented_pct,
                    vacancy_rate, employment_rate, third_level_pct,
                    wfh_pct, avg_rooms, health_good_pct,
                    avg_household_size
                FROM census_small_areas
                WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                AND total_population IS NOT NULL
                LIMIT 1
                """,
                (lng, lat),
            )
            census_row = cur.fetchone()
            census = None
            if census_row:
                _f = lambda v: float(v) if v is not None else None
                _i = lambda v: int(v) if v is not None else None
                census = {
                    "total_population": _i(census_row[0]),
                    "population_density": _f(census_row[1]),
                    "apartment_pct": _f(census_row[2]),
                    "owner_occupied_pct": _f(census_row[3]),
                    "rented_pct": _f(census_row[4]),
                    "vacancy_rate": _f(census_row[5]),
                    "employment_rate": _f(census_row[6]),
                    "third_level_pct": _f(census_row[7]),
                    "wfh_pct": _f(census_row[8]),
                    "avg_rooms": _f(census_row[9]),
                    "health_good_pct": _f(census_row[10]),
                    "avg_household_size": _f(census_row[11]),
                }

            # 6) Commercial context — bbox pre-filter for index hit
            cur.execute(
                f"""
                SELECT COUNT(*), STRING_AGG(DISTINCT category, ', '),
                       COALESCE(ROUND(AVG(valuation)), 0)
                FROM commercial_valuations
                WHERE {bbox_filter}
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
                """,
                (*bbox_params, lng, lat, radius),
            )
            comm_row = cur.fetchone()
            commercial = None
            if comm_row and comm_row[0] > 0:
                commercial = {
                    "count": comm_row[0],
                    "categories": comm_row[1],
                    "avg_valuation": int(comm_row[2]),
                }

            # 7) Recent planning grants (last 2 years) — the strongest development signal
            cur.execute(
                f"""
                SELECT
                    applicationnumber,
                    decision,
                    LEFT(developmentdescription, 120) AS description,
                    to_timestamp(decisiondate/1000)::date::text AS decision_date,
                    numresidentialunits,
                    floorarea,
                    applicationtype,
                    ROUND(ST_Distance(ST_Transform(geom, 2157), {centroid_2157})::numeric, 0) AS distance_m
                FROM national_planning_polygons
                WHERE {bbox_filter}
                  AND ST_DWithin(ST_Transform(geom, 2157), {centroid_2157}, %s)
                  AND (UPPER(decision) LIKE '%%GRANT%%' OR UPPER(decision) LIKE '%%CONDITIONAL%%')
                  AND to_timestamp(decisiondate/1000) > NOW() - INTERVAL '2 years'
                ORDER BY
                    COALESCE(numresidentialunits, 0) DESC,
                    distance_m ASC
                LIMIT 8
                """,
                (*bbox_params, lng, lat, lng, lat, radius),
            )
            recent_grants = [
                {
                    "ref": r[0], "decision": r[1], "description": r[2],
                    "decision_date": r[3], "residential_units": r[4],
                    "floor_area": float(r[5]) if r[5] else None,
                    "application_type": r[6],
                    "distance_m": int(r[7]) if r[7] is not None else None,
                }
                for r in cur.fetchall()
            ]

            # Summary stats for grants
            cur.execute(
                f"""
                SELECT
                    COUNT(*),
                    SUM(COALESCE(numresidentialunits, 0)),
                    COUNT(*) FILTER (WHERE numresidentialunits >= 5)
                FROM national_planning_polygons
                WHERE {bbox_filter}
                  AND ST_DWithin(ST_Transform(geom, 2157), {centroid_2157}, %s)
                  AND (UPPER(decision) LIKE '%%GRANT%%' OR UPPER(decision) LIKE '%%CONDITIONAL%%')
                  AND to_timestamp(decisiondate/1000) > NOW() - INTERVAL '2 years'
                """,
                (*bbox_params, lng, lat, radius),
            )
            grant_stats = cur.fetchone()
            grants_summary = None
            if grant_stats and grant_stats[0] > 0:
                grants_summary = {
                    "total_grants": grant_stats[0],
                    "total_units_approved": int(grant_stats[1]),
                    "significant_schemes": grant_stats[2],  # 5+ units
                }

    finally:
        put_conn(conn)

    return {
        "rzlt_overlap": rzlt_overlap,
        "nearby_planning": nearby_planning,
        "recent_grants": recent_grants,
        "grants_summary": grants_summary,
        "nearby_sales": {
            "count": sales_count,
            "avg_sale_price": int(avg_sale),
            "median_sale_price": int(median_sale),
            "avg_price_per_sqm": int(avg_psm),
            "recent": recent_sales,
        },
        "zoning": zoning,
        "census": census,
        "commercial": commercial,
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


# ── Planning visualization (Gemini 2.5 Flash — Nano Banana) ───────────────────

VISUALIZE_MODEL = "gemini-2.5-flash-image"
VISUALIZE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{VISUALIZE_MODEL}:generateContent"


class VisualizeRequest(BaseModel):
    description: str
    location: str = ""
    decision: str = ""
    plan_ref: str = ""


@app.post("/api/planning/visualize")
async def visualize_planning(req: VisualizeRequest):
    """Generate an architectural visualization of a planning application using Gemini 2.5 Flash."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")

    location_ctx = f" at {req.location}" if req.location else " in Dublin, Ireland"
    decision_ctx = f" (planning {req.decision.lower()})" if req.decision else ""

    prompt = (
        f"Create an architectural before-and-after visualization{location_ctx}. "
        f"The planning application{decision_ctx} describes: {req.description}. "
        f"\n\nIMPORTANT: The NEW elements being added by this planning permission must be clearly highlighted and visually distinct. "
        f"Render the NEW construction/additions in full vivid color with a subtle bright outline or glow effect, "
        f"while showing the EXISTING surrounding buildings and streetscape in slightly muted/desaturated tones. "
        f"This contrast should make it immediately obvious to the viewer exactly what is being built or changed. "
        f"\n\nShow it from a clear street-level perspective during daytime. "
        f"Professional architectural visualization style, realistic materials, natural lighting. "
        f"Do NOT include any text, labels, watermarks, arrows, or written annotations in the image."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{VISUALIZE_URL}?key={GEMINI_API_KEY}",
                json=payload,
            )
            if resp.status_code != 200:
                detail = resp.text[:500]
                raise HTTPException(status_code=resp.status_code, detail=f"Gemini API error: {detail}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise HTTPException(status_code=500, detail="No response from Gemini")

            # Find the image part in the response
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    inline = part["inlineData"]
                    return {
                        "image": inline.get("data", ""),
                        "mime_type": inline.get("mimeType", "image/png"),
                        "prompt": prompt,
                        "plan_ref": req.plan_ref,
                    }

            raise HTTPException(status_code=500, detail="No image in Gemini response")

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Image generation timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


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
    "census_small_areas", "urban_areas", "osm_buildings",
    "national_planning_points", "national_planning_polygons",
    "osm_amenities", "osm_transport",
    "flood_zones", "niah_buildings",
    "schools", "landuse", "zoning", "commercial_valuations",
}

SQL_BLOCKLIST = re.compile(
    r'(?<![A-Za-z_])(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REVOKE|COPY|EXECUTE)(?![A-Za-z_])',
    re.IGNORECASE,
)
# Note: GRANT is NOT in the blocklist because it appears legitimately in
# planning decision filters like UPPER(decision) LIKE '%GRANT%'

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

TABLE: rzlt (Residential Zoned Land Tax sites — ~260k rows nationwide, geom is Polygon)
  ogc_fid SERIAL PRIMARY KEY
  zone_desc TEXT              -- zoning objective from local authority development plan (e.g. 'To provide for residential development...', 'To protect and improve residential amenity')
  zone_gzt TEXT
  gzt_desc TEXT
  site_area NUMERIC           -- area in HECTARES (NOT sqm). Average 0.16ha, max 36ha. 1ha = 10,000sqm.
  local_authority_name TEXT   -- e.g. 'Dublin City Council', 'Dún Laoghaire-Rathdown County Council', 'South Dublin County Council'
  geom GEOMETRY(Polygon, 4326)
  -- RZLT = 3% annual tax on zoned, serviced, undeveloped residential land. Strong motivated seller signal.
  -- Most useful sites for developers: site_area > 0.5 (i.e. >5,000sqm / >0.5ha). Skip tiny garden plots (<0.1ha).

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

TABLE: osm_buildings (OpenStreetMap building footprints for Dublin — ~472k rows, geom is Polygon)
  osm_id BIGINT PRIMARY KEY
  building TEXT               -- building type: 'house', 'apartments', 'residential', 'yes', 'commercial', 'retail', 'industrial', etc.
  name TEXT                   -- building name (often NULL)
  addr_housenumber TEXT       -- house number
  addr_street TEXT            -- street name
  addr_city TEXT              -- city name
  building_levels TEXT        -- number of storeys (as text)
  amenity TEXT                -- amenity type if applicable (e.g. 'school', 'hospital')
  area_sqm NUMERIC           -- building footprint area in sqm
  geom GEOMETRY(Polygon, 4326)

TABLE: osm_amenities (OpenStreetMap points of interest for all of Ireland — ~415k rows, geom is Point)
  osm_id BIGINT PRIMARY KEY
  amenity TEXT                -- amenity type: 'school', 'pub', 'restaurant', 'cafe', 'pharmacy', 'fuel', 'hospital', 'parking', 'place_of_worship', 'fast_food', 'post_box', 'community_centre', 'recycling', 'shelter', 'toilets', etc.
  name TEXT                   -- amenity name
  addr_street TEXT            -- street name
  addr_housenumber TEXT       -- house number
  addr_city TEXT              -- city
  cuisine TEXT                -- for restaurants/cafes (e.g. 'italian', 'chinese')
  healthcare TEXT             -- healthcare speciality
  operator TEXT               -- operating company/org
  brand TEXT                  -- brand name
  opening_hours TEXT          -- opening hours
  geom GEOMETRY(Point, 4326)

TABLE: osm_transport (OpenStreetMap public transport stops for all of Ireland — ~14k rows, geom is Point)
  osm_id BIGINT PRIMARY KEY
  transport_type TEXT         -- 'bus_stop', 'station', 'tram_stop', 'halt', 'bus_station', 'ferry_terminal', 'stop_position', 'platform'
  name TEXT                   -- stop/station name
  network TEXT                -- transport network (e.g. 'Bus Éireann', 'Dublin Bus', 'Iarnród Éireann')
  operator TEXT               -- operator
  route_ref TEXT              -- route reference numbers
  railway TEXT                -- railway type if applicable
  highway TEXT                -- highway type if applicable
  geom GEOMETRY(Point, 4326)

TABLE: flood_zones (OPW flood risk zones for Ireland — ~132k polygons, geom is MultiPolygon)
  id SERIAL PRIMARY KEY
  flood_zone TEXT              -- 'A' (high risk: 1% river / 0.5% coastal) or 'B' (moderate risk: 0.1% AEP)
  flood_type TEXT              -- 'river' or 'coastal'
  source TEXT                  -- 'CFRAM' (detailed, major towns) or 'NIFM' (nationwide indicative)
  aep TEXT                     -- Annual Exceedance Probability: '1%', '0.5%', '0.1%'
  geom GEOMETRY(MultiPolygon, 4326)
  -- Flood Zone A = high probability flooding (>=1% river, >=0.5% coastal). Most restrictive for development.
  -- Flood Zone B = moderate probability (0.1% to 1% river). Some development restrictions.
  -- Flood Zone C (not in table) = low probability (<0.1%). Generally suitable for development.
  -- Use ST_Intersects to check if a parcel/site overlaps a flood zone.

TABLE: niah_buildings (NIAH protected structures — 48,327 buildings across Ireland, geom is Point)
  ogc_fid SERIAL PRIMARY KEY
  reg_no INTEGER               -- NIAH registration number
  name TEXT                    -- building name
  number TEXT                  -- street number
  street1 TEXT                 -- street name
  town TEXT                    -- town
  county TEXT                  -- county
  original_type TEXT           -- original use (e.g. 'house', 'church', 'school', 'bridge')
  in_use_as_type TEXT          -- current use
  rating TEXT                  -- heritage rating: 'Regional', 'National', 'International'
  datefrom INTEGER             -- construction start year
  dateto INTEGER               -- construction end year
  description TEXT             -- physical description of building
  geom GEOMETRY(Point, 4326)
  -- Protected structures have legal restrictions on alterations/demolition.
  -- Use ST_DWithin to find protected structures near a development site.

TABLE: schools (Department of Education schools — 3,949 schools across Ireland, geom is Point)
  id SERIAL PRIMARY KEY
  roll_number TEXT             -- school roll number (unique identifier)
  name TEXT                    -- school name
  address TEXT                 -- full address
  county TEXT                  -- county
  eircode TEXT                 -- Eircode
  school_type TEXT             -- e.g. 'Ordinary', 'Special', 'Community', 'Secondary'
  school_level TEXT            -- 'Primary', 'Post-Primary', 'Special', 'All Through', 'Senior', 'Junior'
  deis TEXT                    -- DEIS (disadvantaged) status Y/N
  ethos TEXT                   -- e.g. 'Catholic', 'Church of Ireland', 'Multi-denominational'
  patron TEXT                  -- school patron
  enrolment INTEGER            -- total student enrolment
  female INTEGER               -- female students
  male INTEGER                 -- male students
  geom GEOMETRY(Point, 4326)
  -- Use ST_DWithin to find schools near a site. Key amenity for residential development value.

TABLE: zoning (Development plan zoning designations — 8,115 polygons for Dublin region, geom is MultiPolygon)
  id SERIAL PRIMARY KEY
  zone_code TEXT               -- e.g. 'Objective A', 'RS', 'Z1', 'GE', 'OS', 'GB'
  zone_description TEXT        -- full description of zoning objective
  gzt_code TEXT                -- GZT standardised code (e.g. 'R2.6') — DLR only
  gzt_category TEXT            -- GZT category description — DLR only
  local_authority TEXT         -- 'DLR', 'Fingal', 'Dublin City'
  hectares NUMERIC             -- area in hectares (DLR only)
  geom GEOMETRY(MultiPolygon, 4326)
  -- Key zoning codes: Residential (Objective A, RS, RA, Z1, Z2), Commercial (Z4, Z5, TC), Industrial (GE, Z6),
  -- Open Space (Objective F, OS, Z7, Z9), Green Belt (GB), Community (CI, Z15)
  -- Use ST_Intersects to find what zone a site is in. Critical for development feasibility.

TABLE: commercial_valuations (38,127 commercial properties with occupier details, Dublin region, geom is Point)
  property_number INTEGER PRIMARY KEY
  category TEXT               -- OFFICE, RETAIL (SHOPS), INDUSTRIAL USES, HOSPITALITY, LEISURE, HEALTH, etc.
  uses TEXT                   -- specific use: 'SHOP', 'OFFICE (4th GENERATION)', 'WAREHOUSE', 'RESTAURANT', 'PUB', etc.
  valuation INTEGER           -- rateable valuation in EUR (proxy for annual rental value)
  address TEXT                -- full address
  eircode TEXT                -- Irish postcode
  local_authority TEXT        -- DUBLIN CITY COUNCIL, DUN LAOGHAIRE-RATHDOWN, FINGAL, SOUTH DUBLIN
  car_park INTEGER            -- number of car park spaces
  total_floor_area NUMERIC    -- total floor area in sq meters
  floor_details JSONB         -- per-floor breakdown: level, floor_use, area, nav_per_m2, nav
  geom GEOMETRY(Point, 4326)
  -- Source: Tailte Éireann Valuation Office. Shows which businesses occupy which sites.
  -- Use ST_DWithin to find commercial tenants near a site. Join with parcels to identify occupied vs vacant land.

TABLE: landuse (OpenStreetMap land use polygons — 577,853 polygons for Ireland, LARGE, geom is MultiPolygon)
  ogc_fid SERIAL PRIMARY KEY
  osm_id TEXT                  -- OpenStreetMap ID
  fclass TEXT                  -- land use class: 'residential', 'industrial', 'commercial', 'farmland', 'forest', 'meadow', 'grass', 'farmyard', 'retail', 'park', 'quarry', 'cemetery', 'recreation_ground', 'scrub', 'heath'
  name TEXT                    -- area name (often NULL)
  geom GEOMETRY(MultiPolygon, 4326)
  -- Use ST_Intersects to find what land use a site is currently in. Farmland/meadow near urban areas = conversion opportunity.

TABLE: national_planning_polygons (national planning applications — ~483k rows, LARGE, geom is MultiPolygon)
  ogc_fid SERIAL PRIMARY KEY
  planningauthority TEXT      -- e.g. 'Dublin City Council', 'Cork County Council'
  applicationnumber TEXT      -- planning application reference
  developmentdescription TEXT -- description of proposed development
  developmentaddress TEXT     -- site address
  developmentpostcode TEXT
  applicationstatus TEXT      -- e.g. 'Decision Made', 'Application Received'
  applicationtype TEXT        -- e.g. 'Permission', 'Retention', 'Outline Permission'
  decision TEXT               -- e.g. 'Conditional', 'Refused', 'Grant Permission'
  landusecode TEXT
  areaofsite NUMERIC          -- site area
  numresidentialunits INTEGER -- number of residential units proposed
  oneoffhouse TEXT
  floorarea NUMERIC           -- proposed floor area
  -- DATE COLUMNS: stored as epoch MILLISECONDS (bigint). Convert with to_timestamp(col/1000)::date
  receiveddate BIGINT         -- application received date (epoch ms)
  decisiondate BIGINT         -- decision date (epoch ms)
  grantdate BIGINT            -- grant date (epoch ms)
  expirydate BIGINT           -- permission expiry date (epoch ms)
  appealstatus TEXT
  appealdecision TEXT
  linkappdetails TEXT          -- URL to application details
  geom GEOMETRY(MultiPolygon, 4326)
  -- SPATIAL INDEX on geom. ALWAYS use spatial filter (ST_MakeEnvelope or ST_DWithin) to avoid full table scans.

TABLE: national_planning_points (same columns as national_planning_polygons but geom is Point — ~362k rows, LARGE)
  -- SPATIAL INDEX on geom. ALWAYS use spatial filter to avoid full table scans.
  -- DATE COLUMNS: stored as epoch MILLISECONDS (bigint). Convert with to_timestamp(col/1000)::date
  -- SPATIAL INDEX on geom. ALWAYS use spatial filter (ST_MakeEnvelope or ST_DWithin) to avoid full table scans on this large table.
  -- KEY USE: Cross-reference with cadastral parcels to find vacant/undeveloped land (parcels with no building footprint),
  --   identify building density, detect building types in an area, or find large commercial buildings.
  -- Common building values: 'yes' (unclassified), 'house', 'apartments', 'residential', 'commercial', 'retail', 'industrial', 'garage', 'shed'

DATA COVERAGE:
- cadastral_freehold, cadastral_leasehold, osm_buildings: Dublin region only (roughly -6.5 to -6.0 lng, 53.2 to 53.5 lat). Areas outside Dublin (e.g. Wicklow, Kildare towns, Meath) will have ZERO cadastral/building data.
- rzlt: Nationwide but concentrated in urban areas. Some rural areas have 0 RZLT sites.
- sold_properties: Dublin region + some national coverage.
- national_planning_polygons/points: Nationwide coverage.
- commercial_valuations: Dublin region only.
- census_small_areas: Dublin region only.
- zoning: Dublin region only (DLR, Fingal, Dublin City).
- IMPORTANT: If the user asks about a location OUTSIDE Dublin (e.g. Greystones, Delgany, Wicklow, Navan, Drogheda, Galway), many tables will return 0 rows. In this case:
  * Focus queries on tables with national coverage: national_planning_polygons, national_planning_points, rzlt, sold_properties
  * Do NOT query cadastral_freehold, osm_buildings, commercial_valuations, census_small_areas, or zoning — they will return nothing
  * Tell the user in the summary that some data layers are not available outside Dublin

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

HYPOTHESIS_PROMPT = f"""You are LandOS AI, an expert Irish property & land development analyst.
The user is a property developer. They ask questions. You answer them by forming hypotheses and writing SQL to test them.

YOUR TASK: Given the user's question, form 3-5 distinct hypotheses about where opportunities might exist, and write PostGIS SQL to test each one.

CRITICAL — GETTING RESULTS IS THE #1 PRIORITY:
- It is MUCH better to return results with loose filters than to return 0 results with perfect filters.
- Start with simple, broad queries. Only add restrictive WHERE clauses if the user specifically asks for constraints.
- NEVER add filters the user didn't ask for. If they say "find apartments", don't also filter by price, size, or date unless they said to.
- If a query might return 0 results, make it BROADER rather than more specific. Remove one WHERE clause at a time.
- If the user asks about an area OUTSIDE Dublin (e.g. Maynooth, Greystones, Wicklow, Navan, Cork, Galway, any non-Dublin Irish location), ONLY use nationally-available tables: rzlt, national_planning_polygons, national_planning_points, sold_properties, osm_amenities, osm_transport, flood_zones, niah_buildings, schools, landuse. Do NOT use cadastral_freehold, cadastral_leasehold, osm_buildings, commercial_valuations, census_small_areas, or zoning — they only have Dublin data.
- For RZLT queries: site_area is in HECTARES. For "mid-sized" residential, use site_area BETWEEN 0.05 AND 5 (500sqm to 5ha). Do NOT use sqm-scale filters like area > 150.
- If no specific location is mentioned, default to Dublin-wide (bbox roughly -6.45 to -6.05, 53.25 to 53.45).

{DB_SCHEMA_PROMPT}

CRITICAL SQL RULES (FOLLOW EXACTLY — violations cause runtime errors):

1. GEOMETRY COLUMNS: Every query MUST include these 3 columns:
   - ST_AsGeoJSON(tablename.geom)::json AS geometry
   - For POLYGON tables (cadastral_freehold, cadastral_leasehold, rzlt, dlr_planning_polygons, osm_buildings, census_small_areas, urban_areas, national_planning_polygons):
       ST_X(ST_Centroid(tablename.geom)) AS lng, ST_Y(ST_Centroid(tablename.geom)) AS lat
   - For POINT tables (sold_properties, dlr_planning_points, national_planning_points):
       ST_X(tablename.geom) AS lng, ST_Y(tablename.geom) AS lat
   NOTE: ST_X() and ST_Y() ONLY work on Point geometries. NEVER call ST_X(polygon.geom) — use ST_X(ST_Centroid(polygon.geom)) instead.

2. LARGE TABLES — ALWAYS bbox-filter FIRST:
   - national_planning_polygons (483k rows), national_planning_points (362k rows): ALWAYS use `geom && ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326)` as the FIRST filter. ST_DWithin alone on these tables WILL timeout.
   - cadastral_freehold (274k rows), osm_buildings (472k rows), rzlt (260k rows): Use ST_Intersects with ST_MakeEnvelope.
   - When joining large tables (e.g. sites + planning), ALWAYS pre-filter the large table to a bbox in a CTE first, THEN do ST_DWithin on the smaller result set.
   - NEVER do `ST_DWithin(big_table.geom::geography, point::geography, 500)` without a bbox pre-filter — this forces a full table scan.

3. LIMIT each query to 25 rows max.

4. ALWAYS use NULLIF(x, 0) to prevent division by zero: e.g. sale_price / NULLIF(floor_area_m2, 0)

5. ALWAYS filter: sale_price > 0 on sold_properties.

6. NEVER use column aliases in WHERE/HAVING — repeat the expression or use a CTE/subquery.

7. When using CTEs that join tables, always qualify ambiguous column names with the table alias.

8. For ST_DWithin with metre distances, cast to geography: ST_DWithin(a.geom::geography, b.geom::geography, 500)

9. NEVER use GROUP BY with geometry columns directly. Instead, use a subquery or CTE to aggregate first, then join back to get geometry.

10. For cross-table spatial queries, prefer ST_DWithin over ST_Intersects for point-to-polygon distance queries.

11. PRIMARY TABLE TAGGING: Every sql_queries entry MUST include a "primary_table" field set to the main table whose rows are returned.
    Must be one of: sold_properties, cadastral_freehold, cadastral_leasehold, rzlt, dlr_planning_polygons, dlr_planning_points, census_small_areas, urban_areas, osm_buildings, national_planning_points, national_planning_polygons, commercial_valuations.
    For cross-table joins, use the table whose individual rows appear in the output.

HYPOTHESIS GUIDELINES:
- Each hypothesis should test a DIFFERENT angle on the user's question
- At least one hypothesis should cross-reference 2+ tables (e.g. RZLT sites near underpriced sales)
- At least one hypothesis should use aggregation/statistics (e.g. avg price per sqm by area)
- Hypotheses should be specific and testable, not vague
- If no location is specified, pick 2-3 promising Dublin areas or search city-wide
- For side site / infill / gap site queries, use the SIDE SITE DETECTION PATTERNS above — combine shape analysis (compactness), size filtering, adjacency, planning history, and RZLT overlap
- COMMERCIAL OPPORTUNITIES: For any site/development query, ALWAYS include at least one hypothesis querying commercial_valuations. Commercial properties (offices, retail, warehouses, restaurants) are HIGH VALUE change-of-use targets. Look for:
  * Small commercial sites (100-500sqm) in residential areas = change-of-use to housing
  * Undervalued commercial (low valuation relative to floor area) = redevelopment potential
  * Multiple commercial uses on one site (e.g. office + restaurant) = complex site with conversion potential
  * Commercial sites near recent residential planning grants = proven change-of-use precedent
- PLANNING PRECEDENT — CRITICAL FOR EVERY SEARCH:
  At least ONE hypothesis MUST cross-reference sites with nearby planning grants. This is how a developer knows if a site is viable.

  PREFERRED PATTERN — sites enriched with nearby planning count:
  CRITICAL PERFORMANCE RULE: national_planning_polygons has 483k rows. NEVER use ST_DWithin on it without a bbox pre-filter.
  Always add a bbox filter FIRST, then refine with ST_DWithin on the bbox-filtered subset:
  ```sql
  WITH target_sites AS (
    -- Your main site query (RZLT, cadastral, commercial, etc.)
    SELECT r.*, r.geom
    FROM rzlt r
    WHERE ST_Intersects(r.geom, ST_MakeEnvelope({{xmin}}, {{ymin}}, {{xmax}}, {{ymax}}, 4326))
    AND r.site_area > 0.05
    LIMIT 25
  ),
  area_planning AS (
    -- FIRST filter planning to bbox area (fast index scan), THEN spatial join
    SELECT np.*
    FROM national_planning_polygons np
    WHERE np.geom && ST_Expand(ST_MakeEnvelope({{xmin}}, {{ymin}}, {{xmax}}, {{ymax}}, 4326), 0.01)
      AND (UPPER(np.decision) LIKE '%%GRANT%%' OR UPPER(np.decision) LIKE '%%CONDITIONAL%%')
      AND to_timestamp(np.decisiondate/1000) > NOW() - INTERVAL '3 years'
  ),
  nearby_planning AS (
    SELECT ts.ogc_fid AS site_id,
           COUNT(*) AS nearby_grants,
           MAX(ap.numresidentialunits) AS max_residential_units,
           STRING_AGG(DISTINCT ap.applicationnumber, ', ' ORDER BY ap.applicationnumber) AS grant_refs
    FROM target_sites ts
    JOIN area_planning ap
      ON ST_DWithin(ts.geom::geography, ap.geom::geography, 500)
    GROUP BY ts.ogc_fid
  )
  SELECT ts.*,
         COALESCE(npl.nearby_grants, 0) AS nearby_grants,
         npl.max_residential_units,
         npl.grant_refs,
         ST_AsGeoJSON(ts.geom)::json AS geometry,
         ST_X(ST_Centroid(ts.geom)) AS lng, ST_Y(ST_Centroid(ts.geom)) AS lat
  FROM target_sites ts
  LEFT JOIN nearby_planning npl ON ts.ogc_fid = npl.site_id
  ORDER BY COALESCE(npl.nearby_grants, 0) DESC, ts.site_area DESC
  LIMIT 25
  ```
  The key optimization: `area_planning` CTE uses `&&` bbox operator to pre-filter planning to a small area BEFORE the expensive ST_DWithin geography cast. This is 100x faster.

  SIMPLE FALLBACK — if the CTE pattern is too complex, just query planning grants directly:
  * Query national_planning_polygons with bbox filter: geom && ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326)
  * Decision filter: UPPER(decision) LIKE '%%GRANT%%' OR UPPER(decision) LIKE '%%CONDITIONAL%%'
  * Date filter: to_timestamp(decisiondate/1000) > NOW() - INTERVAL '3 years'
  * ALWAYS use && bbox spatial filter on national_planning_polygons (483k rows — ST_DWithin alone is TOO SLOW)

RESULT QUALITY FILTERS (apply ONLY to cadastral queries in Dublin — do NOT over-filter):
- For cadastral queries: area_sqm >= 100 to skip road slivers (ONLY when querying cadastral_freehold/leasehold)
- Compactness filter is OPTIONAL — only add if the user specifically asks for buildable/regular shaped plots
- For commercial_valuations queries: always SELECT floor_details, valuation, uses, category, total_floor_area
- IMPORTANT: Do NOT add quality filters to RZLT, national_planning, or sold_properties queries — these tables have clean data and filters cause 0 results
- For RZLT: site_area is in HECTARES. Use site_area > 0.05 at most (500sqm minimum). Do NOT filter by compactness.

COLUMN NAMING — CRITICAL (different tables use different column names for similar concepts):
- "name" column: ONLY exists on osm_buildings, osm_amenities, osm_transport, schools, niah_buildings, landuse. Most tables do NOT have a "name" column.
- Address/location identifiers by table:
  * sold_properties → address
  * cadastral_freehold/leasehold → nationalcadastralreference (no address or name)
  * rzlt → zone_desc, local_authority_name (no address or name)
  * national_planning_* → developmentaddress, applicationnumber
  * dlr_planning_* → location, plan_ref
  * commercial_valuations → address
  * census_small_areas → sa_urban_area_name, county_english (no address or name)
- Area/size by table:
  * cadastral_freehold/leasehold → area_sqm (square meters)
  * rzlt → site_area (HECTARES, not sqm)
  * commercial_valuations → total_floor_area (square meters)
  * sold_properties → floor_area_m2 (square meters)
  * national_planning_* → areaofsite, floorarea
- NEVER SELECT a column that doesn't exist on the table. Check the schema above.

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
1. Planning precedent — THE MOST IMPORTANT SIGNAL. Look for these columns in the data:
   - "nearby_grants": count of granted planning permissions within 500m (higher = better, 3+ is excellent)
   - "max_residential_units": largest residential scheme nearby (indicates scale of development the area supports)
   - "grant_refs": actual planning reference numbers (cite these in your reason!)
   - Sites with nearby_grants >= 3 score 80+. Sites with nearby_grants = 0 lose 15-20 points.
   - If planning data isn't in the results, don't penalize — but sites WITH planning data should always rank above those without.
2. Actionability — can a developer actually do something with this site? RZLT sites (motivated seller due to 3% annual tax), vacant land, and underused commercial properties are most actionable.
3. Signal strength — does the data clearly show an opportunity (underpriced, large parcel, RZLT pressure, nearby grants, etc.)? Multiple overlapping signals = higher score.
4. Cross-reference value — sites that appear in multiple queries or combine multiple signals rank higher. A site that is RZLT + near grants + underpriced is exceptional.
5. Specificity — a specific site with an address beats an aggregated statistic.

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
      "title": "2,060sqm Infill Plot, Clondalkin",
      "reason": "2-3 sentences citing specific data signals.",
      "signals": ["RZLT pressure", "Below market price"]
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
- "sites" must contain 8-15 entries, ranked best-first. If fewer than 8 quality results exist, include all available (even 1-2 is fine).
- hypothesis_index / query_index / row_index are 0-based integers referencing the input data arrays. Double-check they are valid before including.
- ONLY select rows that have actual site data (geometry, address, or parcel ref). Skip aggregate-only rows.
- Skip rows from queries that returned errors.
- "score" is 0-100 representing opportunity strength: 90+ = exceptional, 70-89 = strong, 50-69 = moderate, below 50 = weak. Score based on: size of opportunity, data confidence, actionability.
- "follow_ups" should have exactly 3 entries. Each should be a specific, actionable query the user can run next.
- If no queries returned useful results, set sites to [] and explain in summary what the developer should try instead.
- IMPORTANT: Use ONLY the data fields that exist in the actual query results. Different tables have different columns — do NOT reference fields that aren't in the results.

TITLE RULES:
- "title" is a short descriptive label (max 8 words) for the site. Include size, type/use, and location/area name.
- Good examples: "2,060sqm Infill Plot, Clondalkin", "Commercial Corner Site, Castleknock", "Underpriced 3-bed Semi, Drumcondra", "319sqm Office/Restaurant, Old Navan Rd", "Large RZLT Site, Sandyford"
- NEVER use raw cadastral reference codes (like "DN-123456") or generic labels like "Site #1" or "Site #7"
- NEVER repeat the full raw address — distill it to a recognisable location name
- For commercial_valuations: mention current use and floor area (e.g. "416sqm Warehouse, Clondalkin")
- For cadastral parcels: mention area and character (e.g. "692sqm Residential Plot, Castleknock")

REASON RULES:
- "reason" must be 2-3 sentences citing SPECIFIC data from the query results.
- MUST mention concrete numbers: price/sqm vs area average, RZLT tax liability, nearby planning grant ref numbers, vacancy rates, floor area compared to peers.
- PLANNING PRECEDENT IS CRITICAL: If the query results include nearby_grants count, grant ref numbers (applicationnumber), or numresidentialunits, you MUST cite them in the reason. Example: "3 residential grants within 500m (ref 4436/23 for 1,098 units, ref SDZ25A/0013W for 886 units) confirm strong development precedent."
- For commercial sites: mention current use, total floor area, valuation, and WHY change-of-use or redevelopment makes sense (nearby residential pricing, planning precedent, area demographics).
- Bad: "Good site for development." Good: "319sqm office/restaurant site valued at €85k. 4 residential grants within 500m in last 2 years (including ref DCC-2024-1234 for 45 apartments) confirm strong change-of-use precedent. RZLT pressure adds acquisition leverage."

SIGNAL RULES:
- "signals" is an array of 1-4 short tags (max 4 words each) that justify the score.
- Planning signals (use when data shows nearby grants): "X grants within 500m", "Residential precedent", "Large scheme nearby", "SHD/LRD approved nearby"
- Other signals: "RZLT pressure", "Below market price/sqm", "High vacancy area", "Large underused parcel", "Change of use potential", "Near transport hub", "Infill opportunity", "Corner site"

SITE FILTERING — REJECT these (do NOT include in sites array):
- Road strips, motorway parcels, and infrastructure land (typically very elongated with area < 200sqm)
- Parcels smaller than 100sqm for any query
- For residential queries: parcels smaller than 150sqm (not viable for a dwelling)
- Aggregate-only or statistics rows without a specific site location
- Clearly non-developable land: public roads, river banks, railway corridors, electricity substations
- Sites where the data clearly shows they are already fully developed with no redevelopment signal

VISUALIZATION SELECTION:
After selecting sites, choose the best map visualization type for this data. Add these fields to your JSON:

"object_type": one of:
  - "markers" — ranked numbered pins (DEFAULT for most queries — specific sites, addresses, individual properties)
  - "polygon_highlights" — colored parcel/zone boundaries (use when primary_table is cadastral_freehold, cadastral_leasehold, rzlt, dlr_planning_polygons, osm_buildings, or national_planning_polygons AND geometry column is present in results — lets developer see actual parcel/building shapes)
  - "heatmap" — heat density overlay (use when results are 15+ point observations and the insight is WHERE concentration is highest, e.g. price hotspots, planning activity density)
  - "choropleth" — area polygons colored by metric (use when results are census_small_areas or urban_areas and a single normalized metric like vacancy_rate, apartment_pct, or employment_rate tells the story)

"available_views": array of view types valid for this dataset. Always include "markers" as a fallback (as long as lng/lat exist). Example: ["polygon_highlights", "markers"] or ["heatmap", "markers"] or ["choropleth", "markers"]

"choropleth_metric": string column name (e.g. "vacancy_rate", "apartment_pct") — ONLY set when object_type is "choropleth", otherwise null

"heatmap_weight_column": string column name (e.g. "sale_price", "_score", "site_area") — ONLY set when object_type is "heatmap", otherwise null

Add these 4 fields to your JSON response at the top level.
"""

# ── Agentic Loop: SQL Retry & Broaden Prompts ─────────────────────────────────

SQL_RETRY_PROMPT = """You are a PostGIS SQL expert fixing a broken query for an Irish property intelligence system.

ORIGINAL QUERY:
{original_sql}

ERROR:
{error_message}

{db_schema}

COMMON FIXES:
- "column X does not exist" → Check the schema above — each table has DIFFERENT columns. "name" only exists on osm_buildings, osm_amenities, osm_transport, schools, niah_buildings. Most tables use "address", "zone_desc", "nationalcadastralreference", etc.
- "function st_x(geometry)" → Use ST_X(ST_Centroid(geom)) for polygon tables, ST_X(geom) for point tables only
- "division by zero" → Use NULLIF(x, 0) around divisors
- "column reference is ambiguous" → Qualify with table alias
- "relation does not exist" → Check table name spelling against schema

SQL RULES:
- Every query MUST include: ST_AsGeoJSON(tablename.geom)::json AS geometry
- For POLYGON tables: ST_X(ST_Centroid(tablename.geom)) AS lng, ST_Y(ST_Centroid(tablename.geom)) AS lat
- For POINT tables: ST_X(tablename.geom) AS lng, ST_Y(tablename.geom) AS lat
- Table/column names are lowercase
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

The query returned no rows. This is the MOST IMPORTANT thing to fix — we MUST return results.

Broaden aggressively by doing ALL of these:
1. REMOVE the most restrictive WHERE clause entirely (don't just relax it)
2. DOUBLE the geographic area (expand bbox by 0.05 degrees in each direction, or increase radius to 2000m)
3. If filtering by price, area, or date — remove those filters entirely
4. If searching a specific neighborhood, expand to all of Dublin (bbox: -6.45 to -6.05, 53.25 to 53.45)
5. If using LIKE or pattern matching, simplify to a broader pattern or remove it
6. Keep ONLY the spatial filter and the table-specific essentials (e.g. sale_price > 0 for sold_properties)

IMPORTANT: The broadened query MUST return results. Be aggressive in removing filters.

Keep the same SELECT columns and geometry. LIMIT 25.

Return valid JSON only:
{{"corrected_sql": "SELECT ...", "explanation": "brief description of what you relaxed"}}
"""

FALLBACK_HYPOTHESIS_PROMPT = """You are LandOS AI. A property search query returned very few or zero results. Generate ONE simple, broad PostGIS query that is GUARANTEED to return results.

USER QUERY: {user_query}

{db_schema}

SQL RULES:
- Every query MUST include: ST_AsGeoJSON(tablename.geom)::json AS geometry
- For POLYGON tables: ST_X(ST_Centroid(tablename.geom)) AS lng, ST_Y(ST_Centroid(tablename.geom)) AS lat
- For POINT tables (sold_properties, dlr_planning_points, national_planning_points): ST_X(tablename.geom) AS lng, ST_Y(tablename.geom) AS lat
- Use a broad Dublin bbox: ST_MakeEnvelope(-6.45, 53.25, -6.05, 53.45, 4326)
- LIMIT 25
- Keep it simple — one table, almost NO WHERE clauses
- Use the table most relevant to the user's intent:
  * Sites/land/development → rzlt (use site_area > 0.01 only)
  * Properties/houses/prices → sold_properties (use sale_price > 0 only)
  * Planning/permissions → national_planning_polygons (use UPPER(decision) LIKE '%%GRANT%%' only)
  * Commercial → commercial_valuations (no filters needed)
- DO NOT add area, price, date, or type filters — we need RESULTS

Return valid JSON only (include "primary_table"):
{{"name": "Broad fallback search", "rationale": "Simplified search to find more results", "sql_queries": [{{"description": "...", "primary_table": "rzlt", "sql": "SELECT ..."}}]}}
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
        error_detail = ""
        try:
            error_detail = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            error_detail = resp.text[:200]
        raise HTTPException(status_code=502, detail=f"Gemini API error {resp.status_code}: {error_detail}")

    data = resp.json()

    # Safely extract text from Gemini response — handle all malformed shapes
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            # Gemini may return promptFeedback instead of candidates (safety filter)
            feedback = data.get("promptFeedback", {})
            block_reason = feedback.get("blockReason", "unknown")
            return {"error": f"Gemini blocked response: {block_reason}"}
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            finish = candidates[0].get("finishReason", "unknown")
            return {"error": f"Gemini returned empty response (finishReason: {finish})"}
    except (IndexError, TypeError, AttributeError) as e:
        return {"error": f"Gemini response parsing failed: {e}"}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks or mixed text
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try raw JSON extraction
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Try to repair truncated JSON (common when max_tokens is hit)
        # Close any open arrays/objects
        repaired = text.rstrip()
        if repaired and not repaired.endswith("}"):
            # Count open brackets
            opens = repaired.count("{") + repaired.count("[")
            closes = repaired.count("}") + repaired.count("]")
            # Truncate to last complete element
            # Find last complete object/array element
            last_comma = repaired.rfind(",")
            if last_comma > 0:
                candidate = repaired[:last_comma]
                # Close remaining brackets
                open_braces = candidate.count("{") - candidate.count("}")
                open_brackets = candidate.count("[") - candidate.count("]")
                candidate += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
        print(f"[AI] JSON parse failed. Text starts with: {text[:300]}")
        return {"error": f"Failed to parse Gemini JSON: {text[:200]}"}


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


POINT_TABLES = {
    "sold_properties", "dlr_planning_points", "national_planning_points",
    "osm_amenities", "osm_transport", "niah_buildings", "schools",
    "commercial_valuations",
}

# Tables with data ONLY in Dublin region — queries outside Dublin will return 0 rows
DUBLIN_ONLY_TABLES = {
    "cadastral_freehold", "cadastral_leasehold", "osm_buildings",
    "commercial_valuations", "census_small_areas", "zoning",
    "dlr_planning_polygons", "dlr_planning_points",
}

# Tables with nationwide data
NATIONWIDE_TABLES = {
    "rzlt", "national_planning_polygons", "national_planning_points",
    "sold_properties", "osm_amenities", "osm_transport",
    "flood_zones", "niah_buildings", "schools", "landuse",
}

# Non-Dublin Irish locations that users might search for
NON_DUBLIN_INDICATORS = [
    "cork", "galway", "limerick", "waterford", "kilkenny", "wexford", "sligo",
    "athlone", "drogheda", "dundalk", "navan", "naas", "maynooth", "celbridge",
    "leixlip", "newbridge", "carlow", "mullingar", "tullamore", "ennis",
    "tralee", "killarney", "letterkenny", "cavan", "longford", "roscommon",
    "castlebar", "ballina", "westport", "arklow", "wicklow", "gorey",
    "enniscorthy", "cobh", "midleton", "mallow", "kinsale", "youghal",
    "nenagh", "thurles", "clonmel", "tipperary", "portlaoise", "carrick",
    "shannon", "greystones", "bray",  # border towns that may lack Dublin data
    "county cork", "county galway", "county kerry", "county mayo",
    "county donegal", "county clare", "county wexford", "county wicklow",
    "county meath", "county kildare", "county louth", "county tipperary",
]


def is_non_dublin_query(user_query: str) -> bool:
    """Detect if the user is asking about an area outside Dublin."""
    query_lower = user_query.lower()
    # Check for explicit non-Dublin locations
    for loc in NON_DUBLIN_INDICATORS:
        if loc in query_lower:
            # Exception: some Dublin locations share names (e.g., "Bray" is borderline)
            # But it's safer to treat them as non-Dublin for table selection
            return True
    # Check for "outside Dublin", "not in Dublin", "nationwide", "all of Ireland"
    if any(phrase in query_lower for phrase in [
        "outside dublin", "not in dublin", "beyond dublin",
        "nationwide", "national", "all of ireland", "across ireland",
        "whole country", "every county",
    ]):
        return True
    return False


def filter_dublin_only_tables_from_sql(sql: str) -> str | None:
    """Check if SQL references Dublin-only tables. Returns warning message or None."""
    sql_lower = sql.lower()
    used_dublin_tables = []
    for table in DUBLIN_ONLY_TABLES:
        # Check for table in FROM/JOIN clauses
        if re.search(rf'\b{table}\b', sql_lower):
            used_dublin_tables.append(table)
    if used_dublin_tables:
        return f"Query uses Dublin-only tables ({', '.join(used_dublin_tables)}) for a non-Dublin area"
    return None


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
            cur.execute("SET statement_timeout = '8s'")
            cur.execute("BEGIN READ ONLY")
            try:
                cur.execute(wrapped_sql)
                columns = [desc[0] for desc in cur.description]
                raw_rows = cur.fetchall()
            except Exception as e:
                cur.execute("ROLLBACK")
                # Try executing without wrapper (some CTEs don't wrap well)
                try:
                    cur.execute("SET statement_timeout = '8s'")
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


def query_references_visible_area(query: str) -> bool:
    """Check if the user's query explicitly references the current map view."""
    VIEW_PHRASES = [
        "around here", "in this area", "what i can see", "on screen",
        "visible", "current view", "this view", "nearby", "on the map",
        "in view", "showing", "what's here", "this neighbourhood",
        "this neighborhood", "right here", "where i am",
    ]
    q = query.lower().strip()
    return any(phrase in q for phrase in VIEW_PHRASES)


def format_map_context(ctx: MapContext | None, user_query: str = "") -> str:
    """Format the user's current map state for injection into AI prompts.

    IMPORTANT: Map context is only included when the user's query explicitly
    references the visible area (e.g. 'around here', 'nearby', 'what I can see').
    For named locations (e.g. 'sites near Lucan'), the map viewport is IGNORED
    to prevent confusing the LLM with irrelevant bounding boxes.
    """
    if not ctx:
        return ""

    # Only include viewport/spatial context if user references the visible area
    include_spatial = query_references_visible_area(user_query)

    # Circle analysis is always relevant (user explicitly drew it)
    has_circle = ctx.circle_analysis and ctx.circle_analysis.get("center")
    # Selected entity is always relevant (user explicitly clicked it)
    has_selection = ctx.selected_entity and ctx.selected_entity.get("id")

    if not include_spatial and not has_circle and not has_selection:
        # No map context needed — the query specifies its own location
        return ""

    parts = ["\nMAP CONTEXT (user's current view):"]
    if include_spatial and ctx.viewport:
        sw = ctx.viewport.get("sw", [])
        ne = ctx.viewport.get("ne", [])
        if len(sw) == 2 and len(ne) == 2:
            parts.append(f"- Viewport: SW({sw[0]:.4f}, {sw[1]:.4f}) to NE({ne[0]:.4f}, {ne[1]:.4f})")
            parts.append("- The user is referring to THIS visible area. Use ST_MakeEnvelope with these bounds as the spatial filter.")
    if include_spatial and ctx.zoom is not None:
        parts.append(f"- Zoom level: {ctx.zoom}")
    if ctx.active_layers:
        parts.append(f"- Active layers: {', '.join(ctx.active_layers)}")
    if has_circle:
        c = ctx.circle_analysis
        center = c.get("center", [])
        if len(center) == 2:
            parts.append(f"- Circle analysis active: center ({center[0]:.4f}, {center[1]:.4f}), radius {c.get('radius_m', 0)}m")
            parts.append("- Use this circle as the spatial filter.")
    if has_selection:
        parts.append(f"- Selected entity: {ctx.selected_entity.get('table')} id={ctx.selected_entity.get('id')}")
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
    # Extract user query to decide whether map context is relevant
    _uq = ""
    for _m in reversed(messages):
        if _m.role == "user":
            _uq = _m.content
            break
    context_text = format_map_context(map_context, _uq)
    conv_text = format_conversation_context(conv_context)
    if context_text:
        prompt = prompt + context_text
    if conv_text:
        prompt = prompt + conv_text
    result = await call_gemini_with_prompt(prompt, messages, max_tokens=4096)

    # Check for Gemini error responses
    if isinstance(result, dict) and result.get("error"):
        error_detail = result.get("error", "unknown")
        print(f"[AI] Hypothesis generation Gemini error: {error_detail}")
        raise Exception(f"Couldn't analyze that query — try rephrasing or simplifying your question.")

    # Handle all possible Gemini response shapes:
    # 1. {"hypotheses": [...]}  — standard
    # 2. [{"name": ..., "sql_queries": ...}, ...]  — direct list of hypotheses
    # 3. [{"hypotheses": [...]}]  — list-wrapped dict (Gemini quirk)
    if isinstance(result, list):
        # Check if it's a list-wrapped dict like [{"hypotheses": [...]}]
        if len(result) == 1 and isinstance(result[0], dict) and "hypotheses" in result[0]:
            hypotheses = result[0]["hypotheses"]
        elif len(result) > 0 and isinstance(result[0], dict) and "hypotheses" in result[0]:
            # Multiple wrapped dicts — flatten all hypotheses
            hypotheses = []
            for item in result:
                if isinstance(item, dict) and "hypotheses" in item:
                    hypotheses.extend(item["hypotheses"])
                elif isinstance(item, dict) and "sql_queries" in item:
                    hypotheses.append(item)
        else:
            hypotheses = result
    else:
        hypotheses = result.get("hypotheses", [])

    # Validate and normalize each hypothesis — ensure required fields exist
    valid_hypotheses = []
    for i, h in enumerate(hypotheses):
        if not isinstance(h, dict):
            continue
        # Ensure required fields with safe defaults
        h.setdefault("name", f"Hypothesis {i+1}")
        h.setdefault("rationale", "")
        h.setdefault("sql_queries", [])
        # Validate sql_queries is a list of dicts
        if not isinstance(h["sql_queries"], list):
            h["sql_queries"] = []
        for q in h["sql_queries"]:
            if isinstance(q, dict):
                q.setdefault("description", "")
                q.setdefault("primary_table", "unknown")
        valid_hypotheses.append(h)

    if not valid_hypotheses:
        # Fallback: create a broad search hypothesis
        user_query = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_query = msg.content
                break
        valid_hypotheses = [{
            "name": "General exploration",
            "rationale": f"Broad search for: {user_query[:100]}",
            "sql_queries": [],
        }]

    return valid_hypotheses


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
    _uq = ""
    for _m in reversed(messages):
        if _m.role == "user":
            _uq = _m.content
            break
    context_text = format_map_context(map_context, _uq)
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

Query results: {json.dumps(rows[:15], default=str)[:6000]}

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
    _uq = ""
    for _m in reversed(messages):
        if _m.role == "user":
            _uq = _m.content
            break
    context_text = format_map_context(map_context, _uq)
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

Query results: {json.dumps(all_rows[:30], default=str)[:6000]}

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
        h_name = h.get("name", f"Hypothesis {i+1}")
        h_rationale = h.get("rationale", "No rationale provided")
        parts.append(f"## Analysis {i} (hypothesis_index={i}): {h_name}")
        parts.append(f"Rationale: {h_rationale}")
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
                parts.append(json.dumps(summarized, indent=2, default=str)[:8000])
        parts.append("")

    hypothesis_results_text = "\n".join(parts)

    eval_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        user_query=user_query,
        hypothesis_results=hypothesis_results_text,
    )

    eval_messages = [{"role": "user", "content": "Rank the best sites from these results."}]
    result = await call_gemini_with_prompt(eval_prompt, eval_messages, max_tokens=8192)

    # Handle Gemini error responses gracefully
    if isinstance(result, dict) and result.get("error"):
        error_msg = result.get("error", "unknown error")
        print(f"[AI] Evaluation Gemini error: {error_msg}")
        return {
            "type": "explore",
            "title": "Analysis Results",
            "summary": "AI ranking had a hiccup — showing the best available results.",
            "sites": [],
            "follow_ups": [
                {"label": "Try simpler query", "prompt": "Find the largest development sites in Dublin"},
                {"label": "Search RZLT sites", "prompt": "Show me RZLT sites over 0.5 hectares in south Dublin"},
                {"label": "Recent planning grants", "prompt": "Show recent planning grants for residential development in Dublin"},
            ],
            "object_type": "markers",
            "available_views": ["markers"],
        }

    # Ensure required fields exist with defaults
    if not isinstance(result, dict):
        result = {}
    result.setdefault("type", "explore")
    result.setdefault("title", "Analysis Results")
    result.setdefault("summary", "Analysis complete.")
    result.setdefault("sites", [])
    result.setdefault("follow_ups", [])
    result.setdefault("object_type", "markers")
    result.setdefault("available_views", ["markers"])

    # Validate sites array entries
    valid_sites = []
    for site in result.get("sites", []):
        if not isinstance(site, dict):
            continue
        # Ensure required index fields are integers
        try:
            site["hypothesis_index"] = int(site.get("hypothesis_index", 0))
            site["query_index"] = int(site.get("query_index", 0))
            site["row_index"] = int(site.get("row_index", 0))
        except (ValueError, TypeError):
            continue
        # Ensure score is an integer
        try:
            site["score"] = int(site.get("score", 50))
        except (ValueError, TypeError):
            site["score"] = 50
        site.setdefault("title", "")
        site.setdefault("reason", "")
        site.setdefault("signals", [])
        if not isinstance(site["signals"], list):
            site["signals"] = []
        valid_sites.append(site)
    result["sites"] = valid_sites

    return result


def infer_table(row: dict) -> str:
    """Infer the source table from row columns."""
    if "address" in row and "sale_price" in row:
        return "sold_properties"
    elif "zone_desc" in row or ("site_area" in row and "local_authority_name" in row):
        return "rzlt"
    elif "planningauthority" in row or "applicationnumber" in row or "developmentdescription" in row:
        return "national_planning_polygons"
    elif "plan_ref" in row or ("decision" in row and "descrptn" in row):
        return "dlr_planning_polygons"
    elif "osm_id" in row and ("building" in row or "building_levels" in row):
        return "osm_buildings"
    elif "property_number" in row and ("uses" in row or "category" in row or "valuation" in row):
        return "commercial_valuations"
    elif "nationalcadastralreference" in row or ("area_sqm" in row and "address" not in row and "sale_price" not in row):
        return "cadastral_freehold"
    elif "sa_pub2022" in row or "sa_urban_area_name" in row:
        return "census_small_areas"
    elif "flood_zone" in row or "flood_type" in row:
        return "flood_zones"
    elif "zone_code" in row or "zone_description" in row:
        return "zoning"
    elif "roll_number" in row and "school_type" in row:
        return "schools"
    elif "reg_no" in row and "original_type" in row:
        return "niah_buildings"
    elif "fclass" in row:
        return "landuse"
    elif "transport_type" in row:
        return "osm_transport"
    elif "amenity" in row and "osm_id" in row:
        return "osm_amenities"
    elif "site_area" in row:
        return "rzlt"  # fallback for RZLT without local_authority_name
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
    try:
        if geom_type == "Point" and len(coords) >= 2:
            row["lng"] = coords[0]
            row["lat"] = coords[1]
        elif geom_type in ("Polygon", "MultiPolygon"):
            # Use centroid approximation: average of first ring
            ring = coords[0] if geom_type == "Polygon" else coords[0][0]
            if ring and len(ring) > 0:
                row["lng"] = sum(c[0] for c in ring) / len(ring)
                row["lat"] = sum(c[1] for c in ring) / len(ring)
    except (IndexError, TypeError, ZeroDivisionError):
        pass  # Malformed geometry — skip coord extraction


def synthesize_title(row: dict, table: str) -> str:
    """Generate a human-readable title for a result row based on its table and data.

    This is the ultimate fallback — ensures every result has a meaningful title
    even when the AI evaluation fails to provide one.
    """
    parts = []

    # Size component
    area_sqm = row.get("area_sqm")
    site_area = row.get("site_area")
    total_floor_area = row.get("total_floor_area")
    floor_area_m2 = row.get("floor_area_m2")
    if area_sqm:
        try:
            parts.append(f"{float(area_sqm):,.0f}sqm")
        except (ValueError, TypeError):
            pass
    elif site_area:
        try:
            ha = float(site_area)
            if ha < 1:
                parts.append(f"{ha * 10000:,.0f}sqm")
            else:
                parts.append(f"{ha:,.1f}ha")
        except (ValueError, TypeError):
            pass
    elif total_floor_area:
        try:
            parts.append(f"{float(total_floor_area):,.0f}sqm")
        except (ValueError, TypeError):
            pass
    elif floor_area_m2:
        try:
            parts.append(f"{float(floor_area_m2):,.0f}sqm")
        except (ValueError, TypeError):
            pass

    # Type/use component
    if table == "sold_properties":
        ptype = row.get("property_type")
        if ptype:
            parts.append(str(ptype))
        else:
            parts.append("Property")
    elif table == "rzlt":
        parts.append("RZLT Site")
    elif table == "commercial_valuations":
        uses = row.get("uses") or row.get("category")
        if uses:
            parts.append(str(uses).title()[:30])
        else:
            parts.append("Commercial")
    elif table in ("cadastral_freehold", "cadastral_leasehold"):
        parts.append("Land Parcel")
    elif table in ("national_planning_polygons", "national_planning_points"):
        ref = row.get("applicationnumber", "")
        units = row.get("numresidentialunits")
        if units and int(units) > 0:
            parts.append(f"{units}-Unit Scheme ({ref})" if ref else f"{units}-Unit Scheme")
        elif ref:
            parts.append(f"Planning {ref}")
        else:
            parts.append("Planning App")
    elif table in ("dlr_planning_polygons", "dlr_planning_points"):
        ref = row.get("plan_ref", "")
        parts.append(f"DLR {ref}" if ref else "DLR Planning")
    elif table == "osm_buildings":
        btype = row.get("building")
        if btype and btype != "yes":
            parts.append(str(btype).title())
        else:
            parts.append("Building")
    elif table == "census_small_areas":
        parts.append("Census Area")
    else:
        parts.append("Site")

    # Location component — try multiple fields
    location = (
        row.get("address")
        or row.get("developmentaddress")
        or row.get("location")
        or row.get("sa_urban_area_name")
        or row.get("local_authority_name")
        or row.get("local_authority")
        or row.get("town")
        or row.get("county")
        or ""
    )
    if location:
        # Trim to just the area name (last part of address usually)
        loc_str = str(location).strip()
        if len(loc_str) > 40:
            # Try to get just the area/town from end of address
            loc_parts = loc_str.split(",")
            loc_str = loc_parts[-1].strip() if loc_parts else loc_str[:40]
        parts.append(loc_str)

    return ", ".join(parts) if parts else "Site"


def build_flat_results(hypotheses: list[dict], evaluation: dict) -> list[dict]:
    """Build a flat ranked list of sites from the evaluation's site picks.

    Bulletproof: catches all KeyErrors and synthesizes missing fields.
    """
    site_picks = evaluation.get("sites", [])
    if not isinstance(site_picks, list):
        site_picks = []
    results = []

    for rank, pick in enumerate(site_picks):
        if not isinstance(pick, dict):
            continue
        h_idx = pick.get("hypothesis_index", 0)
        q_idx = pick.get("query_index", 0)
        r_idx = pick.get("row_index", 0)

        # Validate indices are integers
        try:
            h_idx = int(h_idx)
            q_idx = int(q_idx)
            r_idx = int(r_idx)
        except (ValueError, TypeError):
            continue

        # Bounds check with safe access
        try:
            if h_idx < 0 or h_idx >= len(hypotheses):
                continue
            h = hypotheses[h_idx]
            queries = h.get("sql_queries", [])
            if q_idx < 0 or q_idx >= len(queries):
                continue
            query = queries[q_idx]
            all_rows = query.get("result", {}).get("rows", [])
            if r_idx < 0 or r_idx >= len(all_rows):
                continue
            row = dict(all_rows[r_idx])
        except (IndexError, KeyError, TypeError):
            continue

        # Extract lng/lat from geometry if not present as columns
        extract_coords_from_geometry(row)

        # Skip rows without any spatial data
        if not row.get("lng") and not row.get("lat"):
            continue

        # Post-processing filter: reject non-buildable results (cadastral only)
        # Only filter area_sqm (which is in sqm) — do NOT filter site_area (which is in hectares for RZLT)
        area_sqm = row.get("area_sqm")
        if area_sqm is not None:
            try:
                if float(area_sqm) < 20:
                    continue  # Skip very tiny cadastral parcels (road slivers, boundary artifacts)
            except (ValueError, TypeError):
                pass

        # Safely extract pick metadata with defaults
        reason = pick.get("reason", "") or ""
        score = pick.get("score", 0)
        try:
            score = int(score)
        except (ValueError, TypeError):
            score = 50
        title = pick.get("title", "") or ""
        signals = pick.get("signals", [])
        if not isinstance(signals, list):
            signals = []

        row["opportunity_reason"] = reason
        row["_score"] = score
        row["_signals"] = signals

        # Determine table
        try:
            tagged_table = hypotheses[h_idx]["sql_queries"][q_idx].get("primary_table")
        except (IndexError, KeyError):
            tagged_table = None
        row["_table"] = tagged_table if tagged_table in ALLOWED_TABLES else infer_table(row)

        # Synthesize title if AI didn't provide a good one
        import re
        is_generic = (
            not title
            or not title.strip()
            or re.match(r"^Site\s*#?\s*\d*$", title.strip(), re.IGNORECASE)
            or title.strip().lower() in ("site", "result", "opportunity", "option")
        )
        if not is_generic:
            row["_title"] = title
        else:
            row["_title"] = synthesize_title(row, row["_table"])

        row["_rank"] = rank
        results.append(row)

    # Fallback: if evaluation didn't pick sites, gather the best from each hypothesis
    if not results:
        for h in hypotheses:
            for q in h.get("sql_queries", []):
                rows = q.get("result", {}).get("rows", [])
                table = q.get("primary_table") if q.get("primary_table") in ALLOWED_TABLES else None
                for r_idx, row in enumerate(rows[:5]):
                    row = dict(row)
                    extract_coords_from_geometry(row)
                    if not row.get("lng") and not row.get("lat"):
                        continue
                    effective_table = table or infer_table(row)
                    row["_table"] = effective_table
                    row["_rank"] = len(results)
                    row["_score"] = 50  # default for fallback
                    row["_title"] = synthesize_title(row, effective_table)
                    row["_signals"] = []
                    row["opportunity_reason"] = q.get("description", h.get("name", ""))
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
            and (r.get("geometry") or {}).get("type") in ("Polygon", "MultiPolygon")
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


class AreaAnalysisRequest(BaseModel):
    lng: float
    lat: float
    radius: float  # metres
    query: str = ""  # optional follow-up question


@app.post("/api/ai/area_analysis")
async def ai_area_analysis(req: AreaAnalysisRequest):
    """AI-powered area analysis for a drawn circle on the map."""
    from starlette.responses import StreamingResponse

    async def generate():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        yield sse("status", {"phase": "gathering", "message": "Gathering area data..."})

        # ── 1. Gather all data within the circle ──────────────────────
        conn = get_conn()
        context_parts = []
        center_sql = f"ST_Transform(ST_SetSRID(ST_MakePoint({req.lng}, {req.lat}), 4326), 2157)"
        dwithin = f"ST_DWithin(ST_Transform(geom, 2157), {center_sql}, {req.radius})"

        try:
            with conn.cursor() as cur:
                # Census demographics
                cur.execute(f"""
                    SELECT COUNT(*), COALESCE(SUM(total_population),0),
                           COALESCE(ROUND(AVG(vacancy_rate)::numeric,1),0),
                           COALESCE(ROUND(AVG(apartment_pct)::numeric,1),0),
                           COALESCE(ROUND(AVG(owner_occupied_pct)::numeric,1),0),
                           COALESCE(ROUND(AVG(rented_pct)::numeric,1),0),
                           COALESCE(ROUND(AVG(third_level_pct)::numeric,1),0),
                           COALESCE(ROUND(AVG(population_density)::numeric,0),0),
                           COALESCE(ROUND(AVG(employment_rate)::numeric,1),0)
                    FROM census_small_areas WHERE {dwithin}
                """)
                row = cur.fetchone()
                if row and row[0] > 0:
                    context_parts.append(f"DEMOGRAPHICS: {row[1]} people, density {row[7]}/km², vacancy {row[2]}%, apartments {row[3]}%, owner-occupied {row[4]}%, rented {row[5]}%, 3rd-level education {row[6]}%, employment rate {row[8]}%")

                # Sold properties
                cur.execute(f"""
                    SELECT COUNT(*), COALESCE(ROUND(AVG(sale_price)),0),
                           COALESCE(ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sale_price)),0),
                           MIN(sale_price), MAX(sale_price)
                    FROM sold_properties WHERE sale_price > 0 AND {dwithin}
                """)
                row = cur.fetchone()
                if row and row[0] > 0:
                    context_parts.append(f"SOLD PROPERTIES: {row[0]} sales, avg €{row[1]:,.0f}, median €{row[2]:,.0f}, range €{row[3]:,.0f}-€{row[4]:,.0f}")

                # RZLT sites
                cur.execute(f"SELECT COUNT(*), COALESCE(ROUND(SUM(site_area)::numeric,0),0) FROM rzlt WHERE {dwithin}")
                row = cur.fetchone()
                if row and row[0] > 0:
                    context_parts.append(f"RZLT SITES: {row[0]} sites totalling {row[1]:,.0f} sqm (3% annual tax on residentially zoned undeveloped land)")

                # Planning applications
                cur.execute(f"""
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE UPPER(COALESCE(decision,'')) LIKE '%%GRANT%%'),
                           COUNT(*) FILTER (WHERE UPPER(COALESCE(decision,'')) LIKE '%%REFUS%%')
                    FROM national_planning_polygons WHERE {dwithin}
                """)
                row = cur.fetchone()
                if row and row[0] > 0:
                    context_parts.append(f"PLANNING: {row[0]} applications ({row[1]} granted, {row[2]} refused)")

                # Zoning
                cur.execute(f"""
                    SELECT zone_code, zone_description, COUNT(*)
                    FROM zoning WHERE ST_Intersects(geom, ST_Buffer({center_sql}::geography, {req.radius})::geometry)
                    GROUP BY 1,2 ORDER BY COUNT(*) DESC LIMIT 5
                """)
                zones = cur.fetchall()
                if zones:
                    zone_strs = [f"{z[0]}: {z[1][:50]} ({z[2]})" for z in zones]
                    context_parts.append(f"ZONING: {'; '.join(zone_strs)}")

                # Flood zones
                cur.execute(f"""
                    SELECT flood_zone_type, COUNT(*)
                    FROM flood_zones WHERE ST_Intersects(geom, ST_Buffer({center_sql}::geography, {req.radius})::geometry)
                    GROUP BY 1
                """)
                floods = cur.fetchall()
                if floods:
                    flood_strs = [f"{f[0]}: {f[1]} zones" for f in floods]
                    context_parts.append(f"FLOOD RISK: {'; '.join(flood_strs)}")

                # Protected structures
                cur.execute(f"SELECT COUNT(*) FROM niah_buildings WHERE {dwithin}")
                row = cur.fetchone()
                if row and row[0] > 0:
                    context_parts.append(f"PROTECTED STRUCTURES: {row[0]} NIAH buildings (development constraints)")

                # Commercial
                cur.execute(f"""
                    SELECT COUNT(*), STRING_AGG(DISTINCT category, ', '),
                           COALESCE(ROUND(AVG(valuation)),0)
                    FROM commercial_valuations WHERE {dwithin}
                """)
                row = cur.fetchone()
                if row and row[0] > 0:
                    context_parts.append(f"COMMERCIAL: {row[0]} properties (categories: {row[1]}), avg valuation €{row[2]:,.0f}")

                # Amenities
                cur.execute(f"SELECT COUNT(*) FROM osm_amenities WHERE {dwithin}")
                amn = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM osm_transport WHERE {dwithin}")
                trn = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM schools WHERE {dwithin}")
                sch = cur.fetchone()[0]
                if amn + trn + sch > 0:
                    context_parts.append(f"AMENITIES: {amn} POI, {trn} transport stops, {sch} schools within radius")

                # Parcels
                cur.execute(f"""
                    SELECT COUNT(*),
                           COALESCE(ROUND(AVG(ST_Area(ST_Transform(geom,2157)))::numeric),0),
                           COALESCE(ROUND(MAX(ST_Area(ST_Transform(geom,2157)))::numeric),0)
                    FROM cadastral_freehold WHERE {dwithin}
                """)
                row = cur.fetchone()
                if row and row[0] > 0:
                    context_parts.append(f"PARCELS: {row[0]} freehold parcels, avg size {row[1]:,.0f} sqm, largest {row[2]:,.0f} sqm")

        finally:
            put_conn(conn)

        yield sse("status", {"phase": "analyzing", "message": "AI analyzing area..."})

        # ── 2. Send to Gemini for analysis ────────────────────────────
        context_text = "\n".join(context_parts) if context_parts else "No data found in this area."

        follow_up_context = ""
        if req.query:
            follow_up_context = f"\n\nThe user has a specific question about this area: {req.query}\nAnswer their question using the data above."

        analysis_prompt = f"""You are a land intelligence analyst for Irish property developers.

Analyze this area (center: {req.lat:.6f}, {req.lng:.6f}, radius: {req.radius:.0f}m):

{context_text}
{follow_up_context}

Provide a structured analysis in this JSON format:
{{
  "area_name": "Best guess at area name based on coordinates",
  "overview": "2-3 sentence overview of what this area is",
  "market_summary": "Key price metrics, trends, and market position",
  "development_potential": "Assessment of development opportunities based on zoning, RZLT, vacancy, and parcel sizes",
  "risk_factors": "Flood risk, protected structures, planning refusal rates, or other constraints",
  "key_opportunities": ["List 3-5 specific actionable opportunities for a developer"],
  "follow_ups": [
    {{"label": "short label", "prompt": "follow-up question"}},
    {{"label": "short label", "prompt": "follow-up question"}},
    {{"label": "short label", "prompt": "follow-up question"}}
  ]
}}

Be specific and quantitative. Reference actual numbers from the data. Focus on actionable insights for a property developer."""

        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(
                analysis_prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            analysis = json.loads(response.text)
        except Exception as e:
            analysis = {
                "area_name": "Analysis Area",
                "overview": f"Error generating analysis: {str(e)}",
                "market_summary": context_text,
                "development_potential": "Unable to assess",
                "risk_factors": "Unable to assess",
                "key_opportunities": [],
                "follow_ups": [],
            }

        yield sse("area_analysis", {
            "analysis": analysis,
            "context": context_parts,
            "center": {"lng": req.lng, "lat": req.lat},
            "radius": req.radius,
        })
        yield sse("done", {})

    return StreamingResponse(generate(), media_type="text/event-stream")


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
    try:
        evaluation = await evaluate_hypotheses(user_query, hypotheses)
    except Exception as e:
        evaluation = {
            "title": "Analysis Results",
            "summary": f"Ranking encountered an issue ({e}), showing available results.",
            "sites": [], "follow_ups": [],
            "object_type": "markers", "available_views": ["markers"],
        }

    # Build the flat results array with geometry for the frontend map
    try:
        results = build_flat_results(hypotheses, evaluation)
    except Exception:
        results = []
    try:
        obj_type, available_views, choropleth_metric, heatmap_weight_col = determine_object_type(evaluation, results)
    except Exception:
        obj_type, available_views, choropleth_metric, heatmap_weight_col = "markers", ["markers"], None, None

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


def _simplify_geom(geom: dict, max_points: int = 30) -> dict:
    """Simplify a GeoJSON geometry for SSE preview payloads."""
    if geom["type"] == "Polygon":
        ring = geom["coordinates"][0]
        if len(ring) > max_points:
            step = max(1, len(ring) // max_points)
            ring = [ring[i] for i in range(0, len(ring), step)]
            if ring[-1] != geom["coordinates"][0][-1]:
                ring.append(geom["coordinates"][0][-1])
        return {"type": "Polygon", "coordinates": [ring]}
    elif geom["type"] == "MultiPolygon":
        simplified = []
        for poly in geom["coordinates"]:
            ring = poly[0]
            if len(ring) > max_points:
                step = max(1, len(ring) // max_points)
                ring = [ring[i] for i in range(0, len(ring), step)]
                if ring[-1] != poly[0][-1]:
                    ring.append(poly[0][-1])
            simplified.append([ring])
        return {"type": "MultiPolygon", "coordinates": simplified}
    return geom


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
        # Detect area early for map fly-to
        detected_area = extract_area_from_query(user_query)
        # Also try to detect non-Dublin Irish areas for geocoding
        if not detected_area:
            for loc in NON_DUBLIN_INDICATORS:
                if loc.lower() in user_query.lower():
                    detected_area = loc.title()
                    break
        if detected_area:
            # Geocode the area to get coordinates for map fly-to
            try:
                # Use Ireland-wide geocoding (not just Dublin)
                geocode_query = f"{detected_area}, Ireland"
                async with httpx.AsyncClient(timeout=5) as client:
                    geo_resp = await client.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={
                            "q": geocode_query,
                            "format": "json",
                            "limit": 1,
                            "countrycodes": "ie",
                        },
                        headers={"User-Agent": "LandOS/1.0"},
                    )
                    if geo_resp.status_code == 200:
                        geo_results = geo_resp.json()
                        if geo_results and len(geo_results) > 0:
                            geo = geo_results[0]
                            yield sse("area_focus", {
                                "area": detected_area,
                                "lat": float(geo["lat"]),
                                "lng": float(geo["lon"]),
                                "bbox": geo.get("boundingbox"),
                            })
            except Exception:
                # Non-critical — skip fly-to if geocoding fails
                pass

        yield sse("status", {
            "phase": "hypotheses",
            "message": f"Forming hypotheses{f' for {detected_area}' if detected_area else ''}...",
        })
        try:
            hypotheses = await generate_hypotheses(req.messages, req.map_context, conv_ctx)
        except Exception as e:
            yield sse("error", {"message": f"Failed to generate hypotheses: {e}"})
            yield sse("done", {})
            return
        yield sse("hypotheses", {
            "count": len(hypotheses),
            "names": [h.get("name", "") for h in hypotheses],
            "rationales": [h.get("rationale", "") for h in hypotheses],
        })

        # Phase 2: Execute hypotheses in parallel
        import asyncio

        # Detect non-Dublin queries for runtime table filtering
        _is_non_dublin = is_non_dublin_query(user_query)

        h_names = [h.get("name", f"Strategy {i+1}") for i, h in enumerate(hypotheses)]
        yield sse("status", {
            "phase": "executing",
            "message": f"Testing {len(hypotheses)} hypotheses in parallel...",
        })
        total_queries = 0
        successful_queries = 0
        MAX_SQL_RETRIES = 1

        # Queue collects SSE events from parallel hypothesis workers
        event_queue: asyncio.Queue = asyncio.Queue()

        async def run_hypothesis(h_idx: int, hypothesis: dict):
            """Execute a single hypothesis's queries (with retries) and push events to queue."""
            nonlocal total_queries, successful_queries
            h_name = hypothesis.get("name", f"Strategy {h_idx + 1}")

            # Signal that this hypothesis is starting
            await event_queue.put(("hypothesis_start", {
                "hypothesis_index": h_idx,
                "hypothesis_name": h_name,
            }))

            for q_idx, query in enumerate(hypothesis.get("sql_queries", [])):
                sql = query.get("sql", "")
                query_plan = query.get("query_plan")
                if query_plan and not sql.strip():
                    sql = compile_query_plan(query_plan)
                    query["sql"] = sql
                if not sql.strip():
                    continue

                # Runtime Dublin validation: skip Dublin-only tables for non-Dublin queries
                if _is_non_dublin:
                    dublin_warning = filter_dublin_only_tables_from_sql(sql)
                    if dublin_warning:
                        query["result"] = {
                            "rows": [],
                            "error": f"Skipped: {dublin_warning}. Only nationwide tables available for this area.",
                            "row_count": 0,
                        }
                        await event_queue.put(("tool_action", {
                            "action": "sql_skip",
                            "hypothesis": h_name,
                            "message": dublin_warning,
                        }))
                        continue

                # Run SQL in thread pool to avoid blocking
                result = None
                for attempt in range(MAX_SQL_RETRIES + 1):
                    result = await asyncio.to_thread(execute_hypothesis_sql, sql)
                    total_queries += 1

                    # Case 1: SQL error — ask Gemini to fix (but NOT timeouts — those mean the query is too expensive)
                    if result.get("error") and attempt < MAX_SQL_RETRIES:
                        error_snippet = str(result.get("error", ""))[:200]
                        error_lower = error_snippet.lower()
                        # Don't retry timeouts or cancellations — the query pattern is fundamentally too expensive
                        if "timeout" in error_lower or "cancel" in error_lower or "statement timeout" in error_lower:
                            print(f"[AI] SQL timeout for {h_name} — skipping (not retryable)")
                            await event_queue.put(("tool_action", {
                                "action": "sql_skip",
                                "hypothesis": h_name,
                                "message": f"Query too complex — skipped",
                            }))
                            break
                        print(f"[AI] SQL error (attempt {attempt+1}): {error_snippet}")
                        await event_queue.put(("tool_action", {
                            "action": "sql_retry",
                            "attempt": attempt + 1,
                            "error": error_snippet,
                            "hypothesis": h_name,
                        }))
                        try:
                            fix = await retry_failed_sql(sql, result.get("error", ""))
                            new_sql = fix.get("corrected_sql", "")
                            if new_sql.strip():
                                sql = new_sql
                                continue
                        except Exception as retry_err:
                            print(f"[AI] SQL retry failed: {retry_err}")
                        break

                    # Case 2: Empty results — broaden
                    elif result.get("row_count", 0) == 0 and not result.get("error") and attempt == 0:
                        print(f"[AI] 0 results for {h_name} — broadening...")
                        await event_queue.put(("tool_action", {
                            "action": "sql_broaden",
                            "hypothesis": h_name,
                            "description": query.get("description", ""),
                            "message": f"No matches for {h_name} — broadening...",
                        }))
                        try:
                            broader = await broaden_empty_sql(sql, query.get("description", ""))
                            new_sql = broader.get("corrected_sql", "")
                            if new_sql.strip():
                                sql = new_sql
                                continue
                            else:
                                print(f"[AI] Broaden returned empty SQL for {h_name}")
                        except Exception as broaden_err:
                            print(f"[AI] Broaden failed for {h_name}: {broaden_err}")
                        break

                    else:
                        break

                query["result"] = result
                if result and not result.get("error"):
                    successful_queries += 1

                    # Extract preview features (full geometry) for map highlighting
                    preview_features = []
                    for row in result.get("rows", [])[:25]:
                        geom = row.get("geometry")
                        if isinstance(geom, dict) and geom.get("type") in ("Polygon", "MultiPolygon"):
                            # Simplify large polygons for SSE payload size
                            simplified = _simplify_geom(geom)
                            preview_features.append(simplified)
                        elif isinstance(geom, dict) and geom.get("type") == "Point":
                            # Create a small buffer circle for points (visual area)
                            preview_features.append(geom)

                    # Build a one-line data snippet from the first result row
                    snippet = ""
                    rows = result.get("rows", [])
                    if rows:
                        first = rows[0]
                        parts = []
                        for key in ("address", "nationalcadastralreference", "zone_desc", "uses", "developmentdescription"):
                            if key in first and first[key]:
                                parts.append(str(first[key])[:40])
                                break
                        if first.get("area_sqm"):
                            try: parts.append(f"{float(first['area_sqm']):,.0f}sqm")
                            except (ValueError, TypeError): pass
                        elif first.get("total_floor_area"):
                            try: parts.append(f"{float(first['total_floor_area']):,.0f}sqm")
                            except (ValueError, TypeError): pass
                        if first.get("sale_price"):
                            try: parts.append(f"€{float(first['sale_price']):,.0f}")
                            except (ValueError, TypeError): pass
                        elif first.get("valuation"):
                            try: parts.append(f"val €{float(first['valuation']):,.0f}")
                            except (ValueError, TypeError): pass
                        snippet = " · ".join(parts)

                    await event_queue.put(("query_complete", {
                        "hypothesis_index": h_idx,
                        "query_index": q_idx,
                        "hypothesis_name": h_name,
                        "hypothesis_total": len(hypotheses),
                        "row_count": result["row_count"],
                        "description": query.get("description", ""),
                        "preview_features": preview_features,
                        "snippet": snippet,
                    }))

        # Launch all hypotheses in parallel
        tasks = [
            asyncio.create_task(run_hypothesis(i, h))
            for i, h in enumerate(hypotheses)
        ]

        # Drain the event queue as results come in, while tasks are running
        done_tasks = set()
        while len(done_tasks) < len(tasks):
            # Check for completed tasks
            for t in tasks:
                if t.done() and t not in done_tasks:
                    done_tasks.add(t)

            # Drain all available events
            while not event_queue.empty():
                evt_type, evt_data = event_queue.get_nowait()
                yield sse(evt_type, evt_data)

            if len(done_tasks) < len(tasks):
                await asyncio.sleep(0.05)

        # Final drain of any remaining events
        while not event_queue.empty():
            evt_type, evt_data = event_queue.get_nowait()
            yield sse(evt_type, evt_data)

        # Propagate any exceptions from tasks
        for t in tasks:
            if t.exception():
                pass  # Individual hypothesis failures are non-fatal

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

        # Recalculate total rows after any fallback additions
        total_rows = sum(
            q.get("result", {}).get("row_count", 0)
            for h in hypotheses for q in h.get("sql_queries", [])
            if not q.get("result", {}).get("error")
        )

        if total_rows == 0:
            # All hypotheses failed — tell the user clearly
            yield sse("result", {
                "type": "map_realization",
                "title": "No Results Found",
                "summary": "None of the search strategies found matching sites. This can happen when the area has limited data coverage or the query is too specific. Try a broader area or different criteria.",
                "sites": [],
                "follow_ups": [
                    {"label": "Try broader area", "prompt": f"Find development sites in Dublin"},
                    {"label": "Search RZLT sites", "prompt": "Show me RZLT sites over 0.5 hectares"},
                    {"label": "Recent planning grants", "prompt": "Show recent planning grants for apartments"},
                ],
                "object_type": "markers",
                "available_views": ["markers"],
            })
            return

        # Phase 3: Rank
        yield sse("status", {
            "phase": "ranking",
            "message": f"Ranking {total_rows} candidate{'s' if total_rows != 1 else ''} by opportunity score...",
        })
        try:
            evaluation = await evaluate_hypotheses(user_query, hypotheses)
        except Exception as e:
            # Don't crash — create a minimal evaluation and try to show raw results
            import traceback
            print(f"[AI] Ranking failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            evaluation = {
                "type": "explore",
                "title": "Analysis Results",
                "summary": "AI ranking had a hiccup — showing the best available results from your query.",
                "sites": [],
                "follow_ups": [
                    {"label": "Try simpler query", "prompt": "Find the largest development sites in Dublin"},
                    {"label": "Search RZLT sites", "prompt": "Show me RZLT sites over 0.5 hectares in south Dublin"},
                    {"label": "Recent planning grants", "prompt": "Show recent planning grants for residential development in Dublin"},
                ],
                "object_type": "markers",
                "available_views": ["markers"],
            }
        try:
            results = build_flat_results(hypotheses, evaluation)
        except Exception as e:
            import traceback
            print(f"[AI] build_flat_results failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            results = []
        try:
            obj_type, available_views, choropleth_metric, heatmap_weight_col = determine_object_type(evaluation, results)
        except Exception:
            obj_type, available_views, choropleth_metric, heatmap_weight_col = "markers", ["markers"], None, None

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
