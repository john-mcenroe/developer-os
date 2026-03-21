#!/bin/bash
# Load OSM amenities and transport stops into PostGIS
# Data source: OpenStreetMap via Overpass API (all of Ireland)

set -e

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-landos}"
DB_USER="${DB_USER:-postgres}"
DB_PASS="${DB_PASS:-postgres}"

PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
export PGPASSWORD="$DB_PASS"

DATA_DIR="$(dirname "$0")/../data"

echo "=== Loading OSM Amenities ==="

$PSQL -c "DROP TABLE IF EXISTS osm_amenities CASCADE;"
$PSQL -c "
CREATE TABLE osm_amenities (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT,
    osm_type TEXT,
    amenity TEXT,
    name TEXT,
    addr_street TEXT,
    addr_housenumber TEXT,
    addr_city TEXT,
    phone TEXT,
    website TEXT,
    opening_hours TEXT,
    cuisine TEXT,
    healthcare TEXT,
    religion TEXT,
    denomination TEXT,
    operator TEXT,
    brand TEXT,
    geom GEOMETRY(Point, 4326)
);
"

# Parse Overpass JSON and insert into PostGIS
$PSQL -c "
CREATE OR REPLACE FUNCTION load_osm_amenities(data jsonb) RETURNS void AS \$\$
DECLARE
    elem jsonb;
    lng double precision;
    lat double precision;
BEGIN
    FOR elem IN SELECT jsonb_array_elements(data->'elements')
    LOOP
        -- Nodes have lat/lon directly, ways have center
        IF elem->>'type' = 'node' THEN
            lat := (elem->>'lat')::double precision;
            lng := (elem->>'lon')::double precision;
        ELSIF elem->'center' IS NOT NULL THEN
            lat := (elem->'center'->>'lat')::double precision;
            lng := (elem->'center'->>'lon')::double precision;
        ELSE
            CONTINUE;
        END IF;

        INSERT INTO osm_amenities (osm_id, osm_type, amenity, name, addr_street, addr_housenumber, addr_city, phone, website, opening_hours, cuisine, healthcare, religion, denomination, operator, brand, geom)
        VALUES (
            (elem->>'id')::bigint,
            elem->>'type',
            elem->'tags'->>'amenity',
            elem->'tags'->>'name',
            elem->'tags'->>'addr:street',
            elem->'tags'->>'addr:housenumber',
            elem->'tags'->>'addr:city',
            elem->'tags'->>'phone',
            elem->'tags'->>'website',
            elem->'tags'->>'opening_hours',
            elem->'tags'->>'cuisine',
            elem->'tags'->>'healthcare',
            elem->'tags'->>'religion',
            elem->'tags'->>'denomination',
            elem->'tags'->>'operator',
            elem->'tags'->>'brand',
            ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        );
    END LOOP;
END;
\$\$ LANGUAGE plpgsql;
"

echo "Inserting amenities..."
cat "$DATA_DIR/osm_amenities_ireland.json" | $PSQL -c "SELECT load_osm_amenities(pg_read_file('/dev/stdin')::jsonb);" 2>/dev/null || \
$PSQL -c "\copy (SELECT 1) TO '/dev/null'" && \
cat "$DATA_DIR/osm_amenities_ireland.json" | $PSQL -c "
    CREATE TEMP TABLE raw_json (doc jsonb);
    \copy raw_json FROM PROGRAM 'cat $DATA_DIR/osm_amenities_ireland.json' WITH (FORMAT text);
" 2>/dev/null || \
/opt/homebrew/bin/python3 -c "
import json, psycopg2, sys

conn = psycopg2.connect(host='$DB_HOST', port=$DB_PORT, dbname='$DB_NAME', user='$DB_USER', password='$DB_PASS')
cur = conn.cursor()

with open('$DATA_DIR/osm_amenities_ireland.json') as f:
    data = json.load(f)

batch = []
for elem in data.get('elements', []):
    tags = elem.get('tags', {})
    if elem['type'] == 'node':
        lat, lng = elem['lat'], elem['lon']
    elif 'center' in elem:
        lat, lng = elem['center']['lat'], elem['center']['lon']
    else:
        continue
    batch.append((
        elem['id'], elem['type'],
        tags.get('amenity'), tags.get('name'),
        tags.get('addr:street'), tags.get('addr:housenumber'), tags.get('addr:city'),
        tags.get('phone'), tags.get('website'), tags.get('opening_hours'),
        tags.get('cuisine'), tags.get('healthcare'), tags.get('religion'),
        tags.get('denomination'), tags.get('operator'), tags.get('brand'),
        lng, lat
    ))

from psycopg2.extras import execute_values
execute_values(cur, '''
    INSERT INTO osm_amenities (osm_id, osm_type, amenity, name, addr_street, addr_housenumber, addr_city, phone, website, opening_hours, cuisine, healthcare, religion, denomination, operator, brand, geom)
    VALUES %s
''', batch, template='(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326))')
conn.commit()
print(f'Inserted {len(batch)} amenities')
cur.close()
conn.close()
"

$PSQL -c "CREATE INDEX IF NOT EXISTS idx_osm_amenities_geom ON osm_amenities USING GIST (geom);"
$PSQL -c "CREATE INDEX IF NOT EXISTS idx_osm_amenities_type ON osm_amenities (amenity);"
$PSQL -c "DROP FUNCTION IF EXISTS load_osm_amenities(jsonb);"

echo "=== Loading OSM Transport ==="

$PSQL -c "DROP TABLE IF EXISTS osm_transport CASCADE;"
$PSQL -c "
CREATE TABLE osm_transport (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT,
    transport_type TEXT,
    name TEXT,
    network TEXT,
    operator TEXT,
    route_ref TEXT,
    railway TEXT,
    highway TEXT,
    bus TEXT,
    tram TEXT,
    train TEXT,
    subway TEXT,
    geom GEOMETRY(Point, 4326)
);
"

/opt/homebrew/bin/python3 -c "
import json, psycopg2

conn = psycopg2.connect(host='$DB_HOST', port=$DB_PORT, dbname='$DB_NAME', user='$DB_USER', password='$DB_PASS')
cur = conn.cursor()

with open('$DATA_DIR/osm_transport_ireland.json') as f:
    data = json.load(f)

batch = []
for elem in data.get('elements', []):
    if elem['type'] != 'node':
        continue
    tags = elem.get('tags', {})
    # Determine transport type
    ttype = tags.get('public_transport', '')
    if tags.get('railway') in ('station', 'halt', 'tram_stop'):
        ttype = tags['railway']
    elif tags.get('highway') == 'bus_stop':
        ttype = 'bus_stop'
    elif tags.get('amenity') == 'bus_station':
        ttype = 'bus_station'
    elif tags.get('amenity') == 'ferry_terminal':
        ttype = 'ferry_terminal'

    batch.append((
        elem['id'], ttype,
        tags.get('name'), tags.get('network'), tags.get('operator'),
        tags.get('route_ref'), tags.get('railway'), tags.get('highway'),
        tags.get('bus'), tags.get('tram'), tags.get('train'), tags.get('subway'),
        elem['lon'], elem['lat']
    ))

from psycopg2.extras import execute_values
execute_values(cur, '''
    INSERT INTO osm_transport (osm_id, transport_type, name, network, operator, route_ref, railway, highway, bus, tram, train, subway, geom)
    VALUES %s
''', batch, template='(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326))')
conn.commit()
print(f'Inserted {len(batch)} transport stops')
cur.close()
conn.close()
"

$PSQL -c "CREATE INDEX IF NOT EXISTS idx_osm_transport_geom ON osm_transport USING GIST (geom);"
$PSQL -c "CREATE INDEX IF NOT EXISTS idx_osm_transport_type ON osm_transport (transport_type);"

echo "=== Registering layers ==="

$PSQL -c "
INSERT INTO layers (id, name, description, type, source_table, min_zoom, max_zoom, enabled)
VALUES
    ('osm_amenities', 'OSM Amenities', 'Points of interest from OpenStreetMap — schools, shops, restaurants, healthcare, etc.', 'point', 'osm_amenities', 14, 22, true),
    ('osm_transport', 'OSM Transport', 'Public transport stops from OpenStreetMap — bus, rail, Luas, DART stations', 'point', 'osm_transport', 12, 22, true)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;
"

echo "=== Summary ==="
$PSQL -c "SELECT 'amenities' as layer, count(*) FROM osm_amenities UNION ALL SELECT 'transport', count(*) FROM osm_transport;"
$PSQL -c "SELECT amenity, count(*) FROM osm_amenities GROUP BY amenity ORDER BY count(*) DESC LIMIT 15;"
$PSQL -c "SELECT transport_type, count(*) FROM osm_transport GROUP BY transport_type ORDER BY count(*) DESC LIMIT 10;"

echo "Done!"
