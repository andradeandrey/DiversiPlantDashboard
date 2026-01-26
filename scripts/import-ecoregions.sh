#!/bin/bash

# Script to import RESOLVE Ecoregions 2017 into PostgreSQL
# Source: https://ecoregions.appspot.com/ (RESOLVE Ecoregions 2017)

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data"
ZIP_FILE="$DATA_DIR/Ecoregions2017.zip"
TEMP_DIR="$DATA_DIR/ecoregions_temp"
SHP_FILE="$TEMP_DIR/Ecoregions2017.shp"

# Database configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-diversiplant}"
DB_NAME="${DB_NAME:-diversiplant}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-diversiplant-db}"

echo "================================================================"
echo "Importing RESOLVE Ecoregions 2017"
echo "================================================================"
echo ""
echo "Source: https://ecoregions.appspot.com/"
echo "Container: $DOCKER_CONTAINER"
echo ""

# Check if zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: $ZIP_FILE not found"
    echo ""
    echo "Download from: https://ecoregions.appspot.com/"
    exit 1
fi

# Extract shapefile
echo "Extracting shapefile..."
mkdir -p "$TEMP_DIR"
unzip -o "$ZIP_FILE" -d "$TEMP_DIR"

# Check if ogr2ogr is available
if ! command -v ogr2ogr &> /dev/null; then
    echo "Error: ogr2ogr not found. Install GDAL:"
    echo "  brew install gdal"
    exit 1
fi

# Clear existing data
echo ""
echo "Clearing existing ecoregions data..."
docker exec "$DOCKER_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "TRUNCATE TABLE ecoregions RESTART IDENTITY CASCADE;" 2>/dev/null || true

# Convert shapefile to SQL and import via Docker
echo ""
echo "Converting shapefile to SQL..."
ogr2ogr -f "PGDUMP" "$TEMP_DIR/ecoregions.sql" "$SHP_FILE" \
    -lco GEOMETRY_NAME=geom \
    -lco CREATE_TABLE=OFF \
    -lco DROP_TABLE=OFF \
    -t_srs EPSG:4326 \
    -nlt PROMOTE_TO_MULTI \
    -nln ecoregions_raw \
    -sql "SELECT ECO_ID, ECO_NAME, BIOME_NAME, BIOME_NUM, REALM FROM Ecoregions2017"

echo ""
echo "Importing 847 ecoregions via Docker..."

# Create temporary table and import
docker exec "$DOCKER_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
-- Create temporary import table
DROP TABLE IF EXISTS ecoregions_raw;
CREATE TABLE ecoregions_raw (
    ogc_fid SERIAL PRIMARY KEY,
    eco_id INTEGER,
    eco_name VARCHAR(255),
    biome_name VARCHAR(255),
    biome_num INTEGER,
    realm VARCHAR(50),
    geom geometry(MultiPolygon, 4326)
);
EOF

# Copy SQL file to container and execute
docker cp "$TEMP_DIR/ecoregions.sql" "$DOCKER_CONTAINER:/tmp/ecoregions.sql"

# The PGDUMP format may need adjustment, let's use a different approach
# Convert to GeoJSON first, then import via COPY

echo "Converting to GeoJSON..."
ogr2ogr -f "GeoJSON" "$TEMP_DIR/ecoregions.geojson" "$SHP_FILE" \
    -t_srs EPSG:4326 \
    -sql "SELECT ECO_ID, ECO_NAME, BIOME_NAME, BIOME_NUM, REALM FROM Ecoregions2017"

# Create import script
cat > "$TEMP_DIR/import.sql" << 'EOSQL'
-- Create temporary table for GeoJSON import
DROP TABLE IF EXISTS ecoregions_raw;
CREATE TEMP TABLE ecoregions_raw (
    doc JSON
);

-- Load will be done via \copy

-- After loading, transform to final table
EOSQL

echo "Importing GeoJSON features..."

# Use Python to import GeoJSON (more reliable than bash for this)
python3 << PYTHON
import json
import subprocess

# Load GeoJSON
with open('$TEMP_DIR/ecoregions.geojson', 'r') as f:
    data = json.load(f)

# Build INSERT statements
inserts = []
for feature in data['features']:
    props = feature['properties']
    geom = json.dumps(feature['geometry'])

    eco_id = props.get('ECO_ID') or 'NULL'
    eco_name = (props.get('ECO_NAME') or '').replace("'", "''")
    biome_name = (props.get('BIOME_NAME') or '').replace("'", "''")
    biome_num = props.get('BIOME_NUM') or 'NULL'
    realm = (props.get('REALM') or '').replace("'", "''")

    sql = f"""INSERT INTO ecoregions (eco_id, eco_name, biome_name, biome_num, realm, geom)
VALUES ({eco_id}, '{eco_name}', '{biome_name}', {biome_num}, '{realm}',
        ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON('{geom}'), 4326)))
ON CONFLICT (eco_id) DO UPDATE SET
    eco_name = EXCLUDED.eco_name,
    biome_name = EXCLUDED.biome_name,
    biome_num = EXCLUDED.biome_num,
    realm = EXCLUDED.realm,
    geom = EXCLUDED.geom;"""
    inserts.append(sql)

# Write to file
sql_file = '$TEMP_DIR/final_import.sql'
with open(sql_file, 'w') as f:
    f.write('BEGIN;\n')
    for sql in inserts:
        f.write(sql + '\n')
    f.write('COMMIT;\n')
    f.write('ANALYZE ecoregions;\n')

print(f"Generated {len(inserts)} INSERT statements")
PYTHON

# Copy and execute final SQL
docker cp "$TEMP_DIR/final_import.sql" "$DOCKER_CONTAINER:/tmp/final_import.sql"
docker exec "$DOCKER_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -f /tmp/final_import.sql

# Cleanup
echo ""
echo "Cleaning up temporary files..."
rm -rf "$TEMP_DIR"
docker exec "$DOCKER_CONTAINER" rm -f /tmp/ecoregions.sql /tmp/final_import.sql 2>/dev/null || true

# Verify import
echo ""
echo "================================================================"
echo "Import complete! Verifying data..."
echo "================================================================"
echo ""

docker exec "$DOCKER_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
-- Count by realm
SELECT realm, COUNT(*) as n_ecoregions, COUNT(DISTINCT biome_name) as n_biomes
FROM ecoregions
GROUP BY realm
ORDER BY n_ecoregions DESC;

-- Total count
SELECT
    COUNT(*) as total_ecoregions,
    COUNT(DISTINCT biome_name) as unique_biomes,
    COUNT(DISTINCT realm) as unique_realms
FROM ecoregions;

-- Test query for Curitiba coordinates
SELECT eco_name, biome_name, realm
FROM ecoregions
WHERE ST_Contains(geom, ST_SetSRID(ST_Point(-49.27, -25.43), 4326));
EOF

echo ""
echo "Ecoregions imported successfully!"
echo ""
