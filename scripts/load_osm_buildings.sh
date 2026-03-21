#!/usr/bin/env bash
# LandOS — Download and load OSM building footprints into PostGIS
# Run from the project root: bash scripts/load_osm_buildings.sh
#
# Prerequisites:
#   - Docker PostGIS running: docker compose up -d
#   - ogr2ogr (GDAL) installed: brew install gdal
#   - Python 3 with json module (standard library)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-landos}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"
PG_DSN="host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER password=$DB_PASS"

# Dublin bounding box (same as load_data.sh)
DUBLIN_S=53.22
DUBLIN_W=-6.45
DUBLIN_N=53.45
DUBLIN_E=-6.05

OVERPASS_FILE="$PROJECT_ROOT/osm_buildings_dublin.json"
GEOJSON_FILE="$PROJECT_ROOT/osm_buildings_dublin.geojson"

echo "==> Waiting for PostGIS to be ready..."
for i in $(seq 1 20); do
  if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "    PostGIS is ready."
    break
  fi
  echo "    Waiting... ($i/20)"
  sleep 3
done

# Step 1: Download from Overpass API
if [ -f "$OVERPASS_FILE" ]; then
  echo "==> Overpass file already exists at $OVERPASS_FILE, skipping download."
else
  echo "==> Downloading OSM building footprints from Overpass API..."
  echo "    Bounding box: S=$DUBLIN_S W=$DUBLIN_W N=$DUBLIN_N E=$DUBLIN_E"
  echo "    This may take 2-5 minutes depending on server load..."
  curl -o "$OVERPASS_FILE" \
    --max-time 600 \
    -d "[out:json][timeout:300];way[\"building\"]($DUBLIN_S,$DUBLIN_W,$DUBLIN_N,$DUBLIN_E);out geom;" \
    'https://overpass-api.de/api/interpreter'
  echo "    Downloaded: $(du -h "$OVERPASS_FILE" | cut -f1)"
fi

# Step 2: Convert to GeoJSON
if [ -f "$GEOJSON_FILE" ]; then
  echo "==> GeoJSON file already exists at $GEOJSON_FILE, skipping conversion."
else
  echo "==> Converting Overpass JSON to GeoJSON..."
  python3 << 'PYEOF'
import json, sys, os

project_root = os.environ.get("PROJECT_ROOT", ".")
infile = os.path.join(project_root, "osm_buildings_dublin.json")
outfile = os.path.join(project_root, "osm_buildings_dublin.geojson")

with open(infile) as f:
    data = json.load(f)

features = []
for el in data["elements"]:
    geom_nodes = el.get("geometry", [])
    if len(geom_nodes) < 4:
        continue
    coords = [[n["lon"], n["lat"]] for n in geom_nodes]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    tags = el.get("tags", {})
    props = {
        "osm_id": el["id"],
        "building": tags.get("building", "yes"),
    }
    for key in ("name", "addr:housenumber", "addr:street", "addr:city", "building:levels", "amenity"):
        val = tags.get(key)
        if val:
            props[key.replace(":", "_")] = val
    features.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": props,
    })

with open(outfile, "w") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f)

print(f"    Converted {len(features)} building footprints")
PYEOF
fi

# Step 3: Load into PostGIS
echo "==> Dropping existing osm_buildings table if present..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP TABLE IF EXISTS osm_buildings CASCADE;"

echo "==> Loading GeoJSON into PostGIS..."
PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$GEOJSON_FILE" \
  -nln osm_buildings \
  -lco GEOMETRY_NAME=geom \
  -t_srs EPSG:4326 \
  -progress

# Step 4: Add computed columns and indexes
echo "==> Adding area_sqm column and spatial index..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
ALTER TABLE osm_buildings ADD COLUMN IF NOT EXISTS area_sqm DOUBLE PRECISION;
UPDATE osm_buildings SET area_sqm = ST_Area(ST_Transform(geom, 2157));
CREATE INDEX IF NOT EXISTS idx_osm_buildings_geom ON osm_buildings USING GIST(geom);
SQL

# Step 5: Register in layers table
echo "==> Registering layer metadata..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
INSERT INTO layers (id, label, source_table, color, min_zoom, default_visible, endpoint, layer_group)
VALUES ('osm_buildings', 'OSM Buildings', 'osm_buildings', '#8d6e63', 14, false, '/api/osm_buildings', 'boundaries')
ON CONFLICT (id) DO UPDATE SET
  label = EXCLUDED.label,
  color = EXCLUDED.color,
  min_zoom = EXCLUDED.min_zoom,
  endpoint = EXCLUDED.endpoint;
SQL

# Step 6: Stats
echo "==> Done! Summary:"
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
SELECT
  COUNT(*) AS total_buildings,
  COUNT(*) FILTER (WHERE building = 'house') AS houses,
  COUNT(*) FILTER (WHERE building = 'apartments') AS apartments,
  COUNT(*) FILTER (WHERE building = 'residential') AS residential,
  COUNT(*) FILTER (WHERE building = 'yes') AS generic,
  ROUND(AVG(area_sqm)::numeric, 1) AS avg_area_sqm
FROM osm_buildings;
SQL

echo ""
echo "==> OSM buildings loaded successfully."
echo "    Raw files: $OVERPASS_FILE, $GEOJSON_FILE"
echo "    These files are large and gitignored — re-run this script to regenerate."
