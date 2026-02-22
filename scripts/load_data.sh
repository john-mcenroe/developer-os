#!/usr/bin/env bash
# LandOS — Load cadastral parcel data into PostGIS
# Run from the project root: bash scripts/load_data.sh
#
# Prerequisites:
#   - Docker PostGIS running: docker compose up -d
#   - ogr2ogr (GDAL) installed: brew install gdal
#   - GML file present at ./CP_IE_TE_CadastralParcelsFreehold.gml

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GML_FILE="$PROJECT_ROOT/CP_IE_TE_CadastralParcelsFreehold.gml"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-landos}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"
PG_DSN="host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER password=$DB_PASS"

# Dublin bounding box
DUBLIN_W=-6.45
DUBLIN_S=53.22
DUBLIN_E=-6.05
DUBLIN_N=53.45

echo "==> Checking GML file..."
if [ ! -f "$GML_FILE" ]; then
  echo "ERROR: GML file not found at $GML_FILE"
  exit 1
fi

echo "==> Waiting for PostGIS to be ready..."
for i in $(seq 1 20); do
  if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "    PostGIS is ready."
    break
  fi
  echo "    Waiting... ($i/20)"
  sleep 3
done

echo "==> Enabling PostGIS extension..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "==> Dropping existing table if present..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "DROP TABLE IF EXISTS cadastral_freehold CASCADE;"

echo "==> Loading GML into PostGIS (this will take several minutes for the 7GB file)..."
PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$GML_FILE" \
  -nln cadastral_freehold \
  -lco SPATIAL_INDEX=YES \
  -lco GEOMETRY_NAME=geom \
  -t_srs EPSG:4326 \
  -progress

echo "==> Clipping to Dublin bounding box..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
DELETE FROM cadastral_freehold
WHERE NOT ST_Intersects(
  geom,
  ST_MakeEnvelope($DUBLIN_W, $DUBLIN_S, $DUBLIN_E, $DUBLIN_N, 4326)
);
SQL

echo "==> Adding area_sqm column (accurate area in Irish Transverse Mercator)..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
ALTER TABLE cadastral_freehold ADD COLUMN IF NOT EXISTS area_sqm DOUBLE PRECISION;
UPDATE cadastral_freehold SET area_sqm = ST_Area(ST_Transform(geom, 2157));
SQL

echo "==> Ensuring spatial index..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE INDEX IF NOT EXISTS idx_cadastral_freehold_geom ON cadastral_freehold USING GIST(geom);
SQL

echo "==> Creating layers metadata table..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE TABLE IF NOT EXISTS layers (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  table_name TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  min_zoom INTEGER DEFAULT 15,
  style JSONB
);

INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'cadastral_freehold',
  'Cadastral Parcels (Freehold)',
  'cadastral_freehold',
  true,
  15,
  '{"fillColor": "rgba(255,165,0,0.15)", "strokeColor": "#ff8c00", "strokeWidth": 1}'
)
ON CONFLICT (name) DO NOTHING;
SQL

# ── DLR Planning Applications ─────────────────────────────────────────────────
DLR_POLY="$PROJECT_ROOT/dlrplanningapps/DLR_PlanningAppsPolygons.shp"
DLR_POINTS="$PROJECT_ROOT/dlrplanningapps/DLR_PlanningAppsPoints.shp"

if [ -f "$DLR_POLY" ]; then
  echo "==> Loading DLR Planning Applications (Polygons)..."
  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "DROP TABLE IF EXISTS dlr_planning_polygons CASCADE;"

  PGPASSWORD="$DB_PASS" ogr2ogr \
    -f "PostgreSQL" \
    "PG:$PG_DSN" \
    "$DLR_POLY" \
    -nln dlr_planning_polygons \
    -nlt PROMOTE_TO_MULTI \
    -lco GEOMETRY_NAME=geom \
    -t_srs EPSG:4326 \
    -s_srs EPSG:2157 \
    -progress

  echo "    Indexing and registering layer..."
  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
  CREATE INDEX IF NOT EXISTS idx_dlr_planning_poly_geom ON dlr_planning_polygons USING GIST(geom);

  INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
  VALUES (
    'dlr_planning_polygons',
    'DLR Planning Apps (Areas)',
    'dlr_planning_polygons',
    true,
    13,
    '{"fillColor": "rgba(46,204,113,0.2)", "strokeColor": "#2ecc71", "strokeWidth": 1.5}'
  )
  ON CONFLICT (name) DO NOTHING;
SQL
  echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM dlr_planning_polygons;") polygon features."
else
  echo "==> Skipping DLR Planning Polygons (file not found at $DLR_POLY)"
fi

if [ -f "$DLR_POINTS" ]; then
  echo "==> Loading DLR Planning Applications (Points)..."
  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "DROP TABLE IF EXISTS dlr_planning_points CASCADE;"

  PGPASSWORD="$DB_PASS" ogr2ogr \
    -f "PostgreSQL" \
    "PG:$PG_DSN" \
    "$DLR_POINTS" \
    -nln dlr_planning_points \
    -lco SPATIAL_INDEX=YES \
    -lco GEOMETRY_NAME=geom \
    -t_srs EPSG:4326 \
    -s_srs EPSG:2157 \
    -progress

  echo "    Indexing and registering layer..."
  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
  CREATE INDEX IF NOT EXISTS idx_dlr_planning_pts_geom ON dlr_planning_points USING GIST(geom);

  INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
  VALUES (
    'dlr_planning_points',
    'DLR Planning Apps (Points)',
    'dlr_planning_points',
    true,
    12,
    '{"fillColor": "#27ae60", "strokeColor": "#1e8449", "radius": 5}'
  )
  ON CONFLICT (name) DO NOTHING;
SQL
  echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM dlr_planning_points;") point features."
else
  echo "==> Skipping DLR Planning Points (file not found at $DLR_POINTS)"
fi

# ── Sold Properties (from MongoDB) ────────────────────────────────────────────
echo "==> Loading Sold Properties from MongoDB..."
if docker ps --format '{{.Names}}' | grep -q mongodb-local; then
  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
  DROP TABLE IF EXISTS sold_properties CASCADE;
  CREATE TABLE sold_properties (
    id SERIAL PRIMARY KEY,
    mongo_id TEXT,
    address TEXT,
    sale_price INTEGER,
    asking_price INTEGER,
    beds INTEGER,
    baths INTEGER,
    property_type TEXT,
    energy_rating TEXT,
    agent_name TEXT,
    sale_date DATE,
    floor_area_m2 DOUBLE PRECISION,
    url TEXT,
    geom GEOMETRY(Point, 4326)
  );
  CREATE INDEX idx_sold_properties_geom ON sold_properties USING GIST(geom);
SQL

  # Export from MongoDB and load into PostGIS
  docker exec mongodb-local mongosh real_estate --quiet --eval "
    const docs = db.sold_properties.find(
      { latitude: { \\\$gt: 53.0, \\\$lt: 53.6 }, longitude: { \\\$gt: -6.6, \\\$lt: -5.9 } },
      { _id: 1, address: 1, sale_price: 1, asking_price: 1, beds: 1, baths: 1, property_type: 1, energy_rating: 1, agent_name: 1, sale_date: 1, myhome_floor_area_value: 1, url: 1, latitude: 1, longitude: 1 }
    ).toArray();
    print(JSON.stringify(docs));
  " > /tmp/sold_properties_dublin.json

  python3 -c "
import json, csv, io
with open('/tmp/sold_properties_dublin.json') as f:
    docs = json.load(f)
buf = io.StringIO()
writer = csv.writer(buf, delimiter='\t')
for doc in docs:
    lat, lng = doc.get('latitude'), doc.get('longitude')
    if lat is None or lng is None: continue
    if not (51.0 < lat < 56.0 and -11.0 < lng < -5.0): continue
    sd = (doc.get('sale_date') or '')[:10]
    writer.writerow([
        str(doc.get('_id','')), (doc.get('address') or '').replace('\t',' ').replace('\n',' '),
        doc.get('sale_price',''), doc.get('asking_price',''),
        doc.get('beds',''), doc.get('baths',''),
        doc.get('property_type',''), doc.get('energy_rating',''),
        (doc.get('agent_name') or '').replace('\t',' '), sd,
        doc.get('myhome_floor_area_value',''), doc.get('url',''),
        f'SRID=4326;POINT({lng} {lat})'
    ])
with open('/tmp/sold_properties.tsv','w') as f: f.write(buf.getvalue())
print(f'Exported {len(docs)} sold properties')
  "

  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "\COPY sold_properties(mongo_id,address,sale_price,asking_price,beds,baths,property_type,energy_rating,agent_name,sale_date,floor_area_m2,url,geom) FROM '/tmp/sold_properties.tsv' WITH (FORMAT text, NULL '')"

  PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
  INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
  VALUES (
    'sold_properties',
    'Sold Properties',
    'sold_properties',
    true,
    13,
    '{"fillColor": "#e74c3c", "strokeColor": "#c0392b", "radius": 5}'
  )
  ON CONFLICT (name) DO NOTHING;
SQL
  echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM sold_properties;") sold properties."
else
  echo "==> Skipping Sold Properties (mongodb-local container not running)"
fi

# ── Register RZLT layer (off by default — toggle on via UI) ──────────────────
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'rzlt',
  'RZLT Sites (Residential Zoned Land Tax)',
  'rzlt',
  false,
  10,
  '{"fillColor": "rgba(255,0,0,0.2)", "strokeColor": "#ff0000", "strokeWidth": 2}'
)
ON CONFLICT (name) DO UPDATE SET is_active = false;
SQL

echo ""
echo "==> Done! Summary:"
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "SELECT COUNT(*) AS total_parcels FROM cadastral_freehold;"
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "SELECT MIN(area_sqm)::int AS min_sqm, MAX(area_sqm)::int AS max_sqm, AVG(area_sqm)::int AS avg_sqm FROM cadastral_freehold;"
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "SELECT COUNT(*) AS dlr_planning_polygons FROM dlr_planning_polygons;" 2>/dev/null || true
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "SELECT COUNT(*) AS dlr_planning_points FROM dlr_planning_points;" 2>/dev/null || true
echo ""
echo "Ready. Start the API server: cd backend && uvicorn main:app --reload"
