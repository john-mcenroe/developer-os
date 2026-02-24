#!/usr/bin/env bash
# LandOS — Load new South Dublin layers into PostGIS
# Run from the project root: bash scripts/load_new_layers.sh
#
# Prerequisites:
#   - Docker PostGIS running: docker compose up -d
#   - ogr2ogr (GDAL) installed: brew install gdal
#   - Data files in project root:
#       south_dublin_boundary.geojson
#       Planning_Register_911171319511293550.geojson

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

LAP_GEOJSON="$PROJECT_ROOT/south_dublin_boundary.geojson"
PLANNING_GEOJSON="$PROJECT_ROOT/Planning_Register_911171319511293550.geojson"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-landos}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"
PG_DSN="host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER password=$DB_PASS"

echo "==> Checking data files..."
[ -f "$LAP_GEOJSON" ]      || { echo "ERROR: south_dublin_boundary.geojson not found at $LAP_GEOJSON"; exit 1; }
[ -f "$PLANNING_GEOJSON" ] || { echo "ERROR: Planning Register GeoJSON not found at $PLANNING_GEOJSON"; exit 1; }

echo "==> Waiting for PostGIS to be ready..."
for i in $(seq 1 20); do
  if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "    PostGIS is ready."
    break
  fi
  echo "    Waiting... ($i/20)"
  sleep 3
done

# ── 1. South Dublin LAP Boundaries ───────────────────────────────────────────
echo ""
echo "==> Loading South Dublin LAP Boundaries (15 features)..."

PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP TABLE IF EXISTS sd_lap_boundaries CASCADE;"

PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$LAP_GEOJSON" \
  -nln sd_lap_boundaries \
  -nlt PROMOTE_TO_MULTI \
  -lco GEOMETRY_NAME=geom \
  -t_srs EPSG:4326 \
  -progress

echo "    Indexing and registering layer..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE INDEX IF NOT EXISTS idx_sd_lap_geom ON sd_lap_boundaries USING GIST(geom);

INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'sd_lap_boundaries',
  'SD Local Area Plans',
  'sd_lap_boundaries',
  false,
  9,
  '{"fillColor": "rgba(155,89,182,0.1)", "strokeColor": "#9b59b6", "strokeWidth": 2}'
)
ON CONFLICT (name) DO NOTHING;
SQL

echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM sd_lap_boundaries;") LAP boundary features."

# ── 2. South Dublin Planning Register ────────────────────────────────────────
echo ""
echo "==> Loading South Dublin Planning Register (~32k features — may take a minute)..."

PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP TABLE IF EXISTS sd_planning_register CASCADE;"

PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$PLANNING_GEOJSON" \
  -nln sd_planning_register \
  -nlt PROMOTE_TO_MULTI \
  -lco GEOMETRY_NAME=geom \
  -t_srs EPSG:4326 \
  -progress

echo "    Indexing and registering layer..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE INDEX IF NOT EXISTS idx_sd_planning_geom ON sd_planning_register USING GIST(geom);

INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'sd_planning_register',
  'SD Planning Register',
  'sd_planning_register',
  true,
  13,
  '{"fillColor": "rgba(230,126,34,0.2)", "strokeColor": "#e67e22", "strokeWidth": 1.5}'
)
ON CONFLICT (name) DO NOTHING;
SQL

echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM sd_planning_register;") SD planning register features."

echo ""
echo "==> Done! Restart the API server to pick up the new endpoints."
echo "    cd backend && python main.py"
