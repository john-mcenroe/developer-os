#!/usr/bin/env bash
# LandOS — Load Census 2022 data into PostGIS
# Run from the project root: bash scripts/load_census.sh
#
# Prerequisites:
#   - Docker PostGIS running: docker compose up -d
#   - ogr2ogr (GDAL) installed: brew install gdal
#   - Python 3 with csv module (standard library)
#
# Data files (in project root):
#   - Small_Area_...geojson  (Small Area polygons — 18,919 features)
#   - SAPS_2022_Small_Area_UR_171024 (1).csv  (Census stats — 18,920 rows × 795 cols)
#   - Urban_Areas_...geojson  (Urban Area boundaries — 867 features)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SA_GEOJSON="$PROJECT_ROOT/Small_Area_National_Statistical_Boundaries_2022_Ungeneralised_view_8865831477585298158.geojson"
CENSUS_CSV="$PROJECT_ROOT/SAPS_2022_Small_Area_UR_171024 (1).csv"
URBAN_GEOJSON="$PROJECT_ROOT/Urban_Areas_National_Statistical_Boundaries_2022_Ungeneralised_View_6867301564302593317.geojson"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-landos}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"
PG_DSN="host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER password=$DB_PASS"

# Dublin bounding box (clip to Dublin area for performance)
DUBLIN_W=-6.45
DUBLIN_S=53.22
DUBLIN_E=-6.05
DUBLIN_N=53.45

echo "==> Checking data files..."
[ -f "$SA_GEOJSON" ] || { echo "ERROR: Small Area GeoJSON not found"; exit 1; }
[ -f "$CENSUS_CSV" ] || { echo "ERROR: Census CSV not found"; exit 1; }
[ -f "$URBAN_GEOJSON" ] || { echo "ERROR: Urban Areas GeoJSON not found"; exit 1; }

echo "==> Waiting for PostGIS to be ready..."
for i in $(seq 1 20); do
  if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "    PostGIS is ready."
    break
  fi
  echo "    Waiting... ($i/20)"
  sleep 3
done

# ── 1. Load Small Area Polygons ───────────────────────────────────────────────
echo ""
echo "==> Loading Small Area polygons (18,919 features — this may take a minute)..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP TABLE IF EXISTS census_small_areas CASCADE;"

PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$SA_GEOJSON" \
  -nln census_small_areas \
  -lco SPATIAL_INDEX=YES \
  -lco GEOMETRY_NAME=geom \
  -t_srs EPSG:4326 \
  -progress

echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM census_small_areas;") Small Area polygons."

# Clip to Dublin bounding box
echo "==> Clipping Small Areas to Dublin bbox..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
DELETE FROM census_small_areas
WHERE NOT ST_Intersects(
  geom,
  ST_MakeEnvelope($DUBLIN_W, $DUBLIN_S, $DUBLIN_E, $DUBLIN_N, 4326)
);
SQL
echo "    After clipping: $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM census_small_areas;") Small Areas in Dublin."

# Add area column
echo "==> Adding area_sqm column..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS area_sqm DOUBLE PRECISION;
UPDATE census_small_areas SET area_sqm = ST_Area(ST_Transform(geom, 2157));
SQL

# ── 2. Join Census CSV statistics onto the polygons ───────────────────────────
echo ""
echo "==> Parsing Census CSV and joining to Small Area polygons..."

# Add census columns to the table
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
-- Demographics
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS total_population INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS male_population INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS female_population INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS population_density DOUBLE PRECISION;

-- Age bands
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS age_0_14 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS age_15_24 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS age_25_44 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS age_45_64 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS age_65_plus INTEGER;

-- Household composition (T5)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS total_households INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS avg_household_size DOUBLE PRECISION;

-- Housing type (T6_1): House vs Flat/Apartment
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS houses INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS apartments INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS apartment_pct DOUBLE PRECISION;

-- Housing age (T6_2)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS built_pre_1919 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS built_1919_1945 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS built_1946_1970 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS built_1971_2000 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS built_2001_2015 INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS built_2016_plus INTEGER;

-- Tenure (T6_3)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS owner_occupied INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS rented_total INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS owner_occupied_pct DOUBLE PRECISION;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS rented_pct DOUBLE PRECISION;

-- Rooms (T6_4)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS avg_rooms DOUBLE PRECISION;

-- Vacancy (T6_8)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS occupied_dwellings INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS temporarily_absent INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS unoccupied_holiday INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS other_vacant INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS vacancy_rate DOUBLE PRECISION;

-- Employment (T8_1)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS employed INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS unemployed INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS employment_rate DOUBLE PRECISION;

-- Education (T10_4) — highest level completed
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS third_level_total INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS third_level_pct DOUBLE PRECISION;

-- Commuting (T11)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS work_from_home INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS car_commuters INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS public_transport_commuters INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS wfh_pct DOUBLE PRECISION;

-- Health (T12_3)
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS health_very_good INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS health_good INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS health_good_pct DOUBLE PRECISION;

-- Urban/Rural
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS ur_category INTEGER;
ALTER TABLE census_small_areas ADD COLUMN IF NOT EXISTS ur_category_desc TEXT;
SQL

# Run Python to parse CSV and generate UPDATE statements
python3 << 'PYEOF'
import csv
import sys
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433")
DB_NAME = os.environ.get("DB_NAME", "landos")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "postgres")

csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SAPS_2022_Small_Area_UR_171024 (1).csv")
# Fallback path for running from project root
if not os.path.exists(csv_path):
    csv_path = "SAPS_2022_Small_Area_UR_171024 (1).csv"

import psycopg2

conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
cur = conn.cursor()

# Get all SA_PUB2022 values in our Dublin-clipped table
cur.execute("SELECT sa_pub2022 FROM census_small_areas")
dublin_sas = set(row[0] for row in cur.fetchall())
print(f"    Dublin Small Areas in DB: {len(dublin_sas)}")

def safe_int(val):
    try:
        return int(val) if val and val.strip() else 0
    except (ValueError, TypeError):
        return 0

def safe_float(val):
    try:
        return float(val) if val and val.strip() else 0.0
    except (ValueError, TypeError):
        return 0.0

def safe_div(num, denom):
    return round(num / denom * 100, 1) if denom and denom > 0 else None

updated = 0
with open(csv_path, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        geogid = row.get('GEOGID', '').strip()
        if geogid not in dublin_sas:
            continue

        # Demographics (T1_1)
        total_pop = safe_int(row.get('T1_1AGETT', 0))
        male_pop = safe_int(row.get('T1_1AGETM', 0))
        female_pop = safe_int(row.get('T1_1AGETF', 0))

        # Age bands (sum individual ages into bands)
        age_0_14 = sum(safe_int(row.get(f'T1_1AGE{i}T', 0)) for i in range(15))
        age_15_19 = sum(safe_int(row.get(f'T1_1AGE{i}T', 0)) for i in range(15, 20))
        age_20_24 = safe_int(row.get('T1_1AGE20_24T', 0))
        age_25_29 = safe_int(row.get('T1_1AGE25_29T', 0))
        age_30_34 = safe_int(row.get('T1_1AGE30_34T', 0))
        age_35_39 = safe_int(row.get('T1_1AGE35_39T', 0))
        age_40_44 = safe_int(row.get('T1_1AGE40_44T', 0))
        age_45_49 = safe_int(row.get('T1_1AGE45_49T', 0))
        age_50_54 = safe_int(row.get('T1_1AGE50_54T', 0))
        age_55_59 = safe_int(row.get('T1_1AGE55_59T', 0))
        age_60_64 = safe_int(row.get('T1_1AGE60_64T', 0))
        age_65_69 = safe_int(row.get('T1_1AGE65_69T', 0))
        age_70_74 = safe_int(row.get('T1_1AGE70_74T', 0))
        age_75_79 = safe_int(row.get('T1_1AGE75_79T', 0))
        age_80_84 = safe_int(row.get('T1_1AGE80_84T', 0))
        age_85_plus = safe_int(row.get('T1_1AGEGE_85T', 0))

        age_15_24 = age_15_19 + age_20_24
        age_25_44 = age_25_29 + age_30_34 + age_35_39 + age_40_44
        age_45_64 = age_45_49 + age_50_54 + age_55_59 + age_60_64
        age_65_plus = age_65_69 + age_70_74 + age_75_79 + age_80_84 + age_85_plus

        # Households (T5_1): total households = T5_1T_H
        total_households = safe_int(row.get('T5_1T_H', 0))
        total_persons_in_hh = safe_int(row.get('T5_1T_P', 0))
        avg_hh_size = round(total_persons_in_hh / total_households, 2) if total_households > 0 else None

        # Housing type (T6_1): HB=House/Bungalow, FA=Flat/Apartment, BS=Bedsit, CM=Caravan/Mobile
        houses = safe_int(row.get('T6_1_HB_H', 0))
        apartments = safe_int(row.get('T6_1_FA_H', 0)) + safe_int(row.get('T6_1_BS_H', 0))
        total_dwelling_type = safe_int(row.get('T6_1_TH', 0))
        apartment_pct = safe_div(apartments, total_dwelling_type)

        # Housing age (T6_2) — _H suffix = households
        built_pre_1919 = safe_int(row.get('T6_2_PRE19H', 0))
        built_1919_1945 = safe_int(row.get('T6_2_19_45H', 0))
        built_1946_1960 = safe_int(row.get('T6_2_46_60H', 0))
        built_1961_1970 = safe_int(row.get('T6_2_61_70H', 0))
        built_1971_1980 = safe_int(row.get('T6_2_71_80H', 0))
        built_1981_1990 = safe_int(row.get('T6_2_81_90H', 0))
        built_1991_2000 = safe_int(row.get('T6_2_91_00H', 0))
        built_2001_2010 = safe_int(row.get('T6_2_01_10H', 0))
        built_2011_2015 = safe_int(row.get('T6_2_11_15H', 0))
        built_2016_plus = safe_int(row.get('T6_2_16LH', 0))

        built_1946_1970 = built_1946_1960 + built_1961_1970
        built_1971_2000 = built_1971_1980 + built_1981_1990 + built_1991_2000
        built_2001_2015 = built_2001_2010 + built_2011_2015

        # Tenure (T6_3) — OML=owner with mortgage/loan, OO=owner outright, RPL=rented private, RLA=rented LA
        owner_occ = safe_int(row.get('T6_3_OMLH', 0)) + safe_int(row.get('T6_3_OOH', 0))
        rented = safe_int(row.get('T6_3_RPLH', 0)) + safe_int(row.get('T6_3_RLAH', 0)) + safe_int(row.get('T6_3_RVCHBH', 0))
        tenure_total = safe_int(row.get('T6_3_TH', 0))
        owner_pct = safe_div(owner_occ, tenure_total)
        rented_pct = safe_div(rented, tenure_total)

        # Rooms (T6_4) — weighted average
        rooms_total = 0
        rooms_count = 0
        for r_num in range(1, 8):
            cnt = safe_int(row.get(f'T6_4_{r_num}RH', 0))
            rooms_total += r_num * cnt
            rooms_count += cnt
        cnt_8plus = safe_int(row.get('T6_4_GE8RH', 0))
        rooms_total += 8 * cnt_8plus
        rooms_count += cnt_8plus
        avg_rooms = round(rooms_total / rooms_count, 1) if rooms_count > 0 else None

        # Vacancy (T6_8)
        occupied = safe_int(row.get('T6_8_O', 0))
        temp_absent = safe_int(row.get('T6_8_TA', 0))
        unoccupied_hol = safe_int(row.get('T6_8_UHH', 0))
        other_vacant = safe_int(row.get('T6_8_OVD', 0))
        total_dwellings = safe_int(row.get('T6_8_T', 0))
        vacancy_rate = safe_div(unoccupied_hol + other_vacant, total_dwellings)

        # Employment (T8_1) — WT=working total, LFFJT=looking first job, STUT=student, LTUT=long-term unemployed
        employed = safe_int(row.get('T8_1_WT', 0))
        unemployed = safe_int(row.get('T8_1_LFFJT', 0)) + safe_int(row.get('T8_1_STUT', 0)) + safe_int(row.get('T8_1_LTUT', 0))
        labour_force = employed + unemployed
        employment_rate = safe_div(employed, labour_force)

        # Education (T10_4) — HDQ=Higher Diploma/PG, PD=Postgrad Degree, D=Doctorate
        # Third level = HDPQ + PD + D (higher diplomas, postgrad, doctorate)
        third_level = (safe_int(row.get('T10_4_HDPQT', 0)) +
                       safe_int(row.get('T10_4_PDT', 0)) +
                       safe_int(row.get('T10_4_DT', 0)) +
                       safe_int(row.get('T10_4_ODNDT', 0)) +
                       safe_int(row.get('T10_4_HCT', 0)))
        edu_total = safe_int(row.get('T10_4_TT', 0))
        third_level_pct = safe_div(third_level, edu_total)

        # Commuting (T11_1) — FW=foot walk, BIW=bicycle, BUW=bus, MW=motorcycle, CDW=car driver
        wfh = safe_int(row.get('T11_4_WFH', 0))
        car_commuters = safe_int(row.get('T11_1_CDW', 0)) + safe_int(row.get('T11_1_CPW', 0))  # car driver + passenger
        pt_commuters = safe_int(row.get('T11_1_BUW', 0)) + safe_int(row.get('T11_1_TDLW', 0))  # bus + train/dart/luas
        commute_total = safe_int(row.get('T11_1_TW', 0))
        wfh_pct = safe_div(wfh, safe_int(row.get('T11_4_T', 0)))

        # Health (T12_3)
        health_vg = safe_int(row.get('T12_3_VGT', 0))
        health_g = safe_int(row.get('T12_3_GT', 0))
        health_total = safe_int(row.get('T12_3_TT', 0))
        health_good_pct = safe_div(health_vg + health_g, health_total)

        # Urban/Rural
        ur_cat = safe_int(row.get('UR_Category', 0))
        ur_desc = row.get('UR_Category_Desc', '').strip()

        cur.execute("""
            UPDATE census_small_areas SET
                total_population = %s, male_population = %s, female_population = %s,
                age_0_14 = %s, age_15_24 = %s, age_25_44 = %s, age_45_64 = %s, age_65_plus = %s,
                total_households = %s, avg_household_size = %s,
                houses = %s, apartments = %s, apartment_pct = %s,
                built_pre_1919 = %s, built_1919_1945 = %s, built_1946_1970 = %s,
                built_1971_2000 = %s, built_2001_2015 = %s, built_2016_plus = %s,
                owner_occupied = %s, rented_total = %s, owner_occupied_pct = %s, rented_pct = %s,
                avg_rooms = %s,
                occupied_dwellings = %s, temporarily_absent = %s, unoccupied_holiday = %s,
                other_vacant = %s, vacancy_rate = %s,
                employed = %s, unemployed = %s, employment_rate = %s,
                third_level_total = %s, third_level_pct = %s,
                work_from_home = %s, car_commuters = %s, public_transport_commuters = %s, wfh_pct = %s,
                health_very_good = %s, health_good = %s, health_good_pct = %s,
                ur_category = %s, ur_category_desc = %s
            WHERE sa_pub2022 = %s
        """, (
            total_pop, male_pop, female_pop,
            age_0_14, age_15_24, age_25_44, age_45_64, age_65_plus,
            total_households, avg_hh_size,
            houses, apartments, apartment_pct,
            built_pre_1919, built_1919_1945, built_1946_1970,
            built_1971_2000, built_2001_2015, built_2016_plus,
            owner_occ, rented, owner_pct, rented_pct,
            avg_rooms,
            occupied, temp_absent, unoccupied_hol,
            other_vacant, vacancy_rate,
            employed, unemployed, employment_rate,
            third_level, third_level_pct,
            wfh, car_commuters, pt_commuters, wfh_pct,
            health_vg, health_g, health_good_pct,
            ur_cat, ur_desc,
            geogid
        ))
        updated += 1

conn.commit()
cur.close()
conn.close()
print(f"    Updated {updated} Small Areas with census data.")
PYEOF

# Compute population density
echo "==> Computing population density..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
UPDATE census_small_areas
SET population_density = CASE WHEN area_sqm > 0 THEN ROUND((total_population / (area_sqm / 1000000.0))::numeric, 0) ELSE NULL END
WHERE total_population IS NOT NULL;
SQL

# ── 3. Load Urban Area Boundaries ─────────────────────────────────────────────
echo ""
echo "==> Loading Urban Area boundaries (867 features)..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP TABLE IF EXISTS urban_areas CASCADE;"

PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$URBAN_GEOJSON" \
  -nln urban_areas \
  -lco SPATIAL_INDEX=YES \
  -lco GEOMETRY_NAME=geom \
  -t_srs EPSG:4326 \
  -progress

# Clip to Dublin
echo "==> Clipping Urban Areas to Dublin bbox..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
DELETE FROM urban_areas
WHERE NOT ST_Intersects(
  geom,
  ST_MakeEnvelope($DUBLIN_W, $DUBLIN_S, $DUBLIN_E, $DUBLIN_N, 4326)
);
SQL
echo "    After clipping: $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM urban_areas;") Urban Areas in Dublin."

# ── 4. Register layers ────────────────────────────────────────────────────────
echo ""
echo "==> Registering census layers..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'census_small_areas',
  'Census Small Areas (2022)',
  'census_small_areas',
  false,
  12,
  '{"fillColor": "rgba(0, 188, 212, 0.2)", "strokeColor": "#00bcd4", "strokeWidth": 1}'
)
ON CONFLICT (name) DO NOTHING;

INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'urban_areas',
  'Urban Area Boundaries',
  'urban_areas',
  false,
  10,
  '{"fillColor": "rgba(0, 150, 136, 0.15)", "strokeColor": "#009688", "strokeWidth": 2}'
)
ON CONFLICT (name) DO NOTHING;
SQL

# ── 5. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "==> Done! Census data summary:"
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
SELECT
  COUNT(*) AS small_areas,
  SUM(total_population) AS total_pop,
  ROUND(AVG(total_population)) AS avg_pop_per_sa,
  ROUND(AVG(vacancy_rate)::numeric, 1) AS avg_vacancy_pct,
  ROUND(AVG(owner_occupied_pct)::numeric, 1) AS avg_owner_occ_pct,
  ROUND(AVG(rented_pct)::numeric, 1) AS avg_rented_pct
FROM census_small_areas
WHERE total_population IS NOT NULL;
SQL

echo ""
echo "Ready. Census data is now available in the database."
echo "Tables: census_small_areas (polygons + stats), urban_areas (boundaries)"
