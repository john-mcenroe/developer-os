#!/usr/bin/env bash
# LandOS — Load National Planning Application data into PostGIS
# Run from the project root: bash scripts/load_national_planning.sh
#
# Prerequisites:
#   - Docker PostGIS running: docker compose up -d
#   - ogr2ogr (GDAL) installed: brew install gdal
#   - Data files in project root:
#       national_planning_points.geojson   (~496 MB, ~362k features)
#       national_planning_polygons.geojson (~988 MB, ~483k features)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

POINTS_GEOJSON="$PROJECT_ROOT/national_planning_points.geojson"
POLYGONS_GEOJSON="$PROJECT_ROOT/national_planning_polygons.geojson"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-landos}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"
PG_DSN="host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER password=$DB_PASS"

echo "==> Checking data files..."
[ -f "$POINTS_GEOJSON" ]   || { echo "ERROR: national_planning_points.geojson not found at $POINTS_GEOJSON"; exit 1; }
[ -f "$POLYGONS_GEOJSON" ] || { echo "ERROR: national_planning_polygons.geojson not found at $POLYGONS_GEOJSON"; exit 1; }

echo "==> Waiting for PostGIS to be ready..."
for i in $(seq 1 20); do
  if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    echo "    PostGIS is ready."
    break
  fi
  echo "    Waiting... ($i/20)"
  sleep 3
done

# ── 1. National Planning Application Points ──────────────────────────────────
echo ""
echo "==> Loading National Planning Points (~362k features — this will take a few minutes)..."

PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP TABLE IF EXISTS national_planning_points CASCADE;"

PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$POINTS_GEOJSON" \
  -nln national_planning_points \
  -nlt POINT \
  -lco GEOMETRY_NAME=geom \
  -lco SPATIAL_INDEX=YES \
  -t_srs EPSG:4326 \
  -progress

echo "    Indexing and registering layer..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE INDEX IF NOT EXISTS idx_national_planning_points_geom ON national_planning_points USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_national_planning_points_auth ON national_planning_points ("PlanningAuthority");
CREATE INDEX IF NOT EXISTS idx_national_planning_points_decision ON national_planning_points ("Decision");

INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'national_planning_points',
  'National Planning (Points)',
  'national_planning_points',
  false,
  12,
  '{"fillColor": "#3498db", "strokeColor": "#2980b9", "radius": 5}'
)
ON CONFLICT (name) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  style = EXCLUDED.style;
SQL

echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM national_planning_points;") national planning point features."

# ── 2. National Planning Application Polygons ────────────────────────────────
echo ""
echo "==> Loading National Planning Polygons (~483k features — this will take several minutes)..."

PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP TABLE IF EXISTS national_planning_polygons CASCADE;"

PGPASSWORD="$DB_PASS" ogr2ogr \
  -f "PostgreSQL" \
  "PG:$PG_DSN" \
  "$POLYGONS_GEOJSON" \
  -nln national_planning_polygons \
  -nlt PROMOTE_TO_MULTI \
  -lco GEOMETRY_NAME=geom \
  -lco SPATIAL_INDEX=YES \
  -t_srs EPSG:4326 \
  -progress

echo "    Indexing and registering layer..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE INDEX IF NOT EXISTS idx_national_planning_polygons_geom ON national_planning_polygons USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_national_planning_polygons_auth ON national_planning_polygons ("PlanningAuthority");
CREATE INDEX IF NOT EXISTS idx_national_planning_polygons_decision ON national_planning_polygons ("Decision");

INSERT INTO layers (name, display_name, table_name, is_active, min_zoom, style)
VALUES (
  'national_planning_polygons',
  'National Planning (Areas)',
  'national_planning_polygons',
  false,
  13,
  '{"fillColor": "rgba(52,152,219,0.2)", "strokeColor": "#3498db", "strokeWidth": 1.5}'
)
ON CONFLICT (name) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  style = EXCLUDED.style;
SQL

echo "    Loaded $(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM national_planning_polygons;") national planning polygon features."

echo ""
echo "==> Done! Restart the API server to pick up the new endpoints."
echo "    cd backend && python main.py"
