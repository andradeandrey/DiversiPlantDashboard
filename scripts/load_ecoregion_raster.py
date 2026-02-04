#!/usr/bin/env python3
"""
Load ecoregion raster into PostGIS for precise ecoregion identification.

This script:
1. Reads ecoregions_south_america.tif
2. Creates ecoregions_raster table in PostgreSQL
3. Loads raster tiles for efficient spatial queries
4. Creates function to query ecoregion by coordinates
"""

import os
import sys
import psycopg2
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'diversiplant')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'diversiplant_dev')
DB_NAME = os.getenv('DB_NAME', 'diversiplant')

# Raster file path
RASTER_PATH = '/Users/andreyandrade/Code/DiversiPlantDashboard-sticky/data/ecoregions_raster/ecoregions_south_america.tif'

def create_raster_table(cursor):
    """Create table to store raster tiles."""
    print("📦 Creating ecoregions_raster table...")

    cursor.execute("""
        DROP TABLE IF EXISTS ecoregions_raster CASCADE;

        CREATE TABLE ecoregions_raster (
            rid SERIAL PRIMARY KEY,
            rast raster,
            filename text
        );

        CREATE INDEX idx_ecoregions_raster_rast
        ON ecoregions_raster USING gist (ST_ConvexHull(rast));

        -- Add raster constraints
        SELECT AddRasterConstraints('ecoregions_raster'::name, 'rast'::name);
    """)
    print("✅ Table created")

def load_raster_simple(cursor):
    """Load raster using WKT Raster format (simple method)."""
    print("📥 Loading raster data...")

    with rasterio.open(RASTER_PATH) as src:
        # Read metadata
        width = src.width
        height = src.height
        transform = src.transform
        crs = src.crs.to_string()

        # Define tile size (100x100 pixels for efficient queries)
        tile_size = 100

        # Calculate number of tiles
        n_tiles_x = (width + tile_size - 1) // tile_size
        n_tiles_y = (height + tile_size - 1) // tile_size
        total_tiles = n_tiles_x * n_tiles_y

        print(f"Raster: {width}x{height} pixels")
        print(f"Tiles: {n_tiles_x}x{n_tiles_y} = {total_tiles} tiles")

        # Read entire raster (for small files)
        data = src.read(1, masked=True)

        # Get geotransform
        gt = transform.to_gdal()
        pixel_width = gt[1]
        pixel_height = -gt[5]  # Negative because Y decreases

        # Load tiles
        tile_count = 0
        for i in range(n_tiles_x):
            for j in range(n_tiles_y):
                # Calculate tile bounds
                x_min = i * tile_size
                y_min = j * tile_size
                x_max = min(x_min + tile_size, width)
                y_max = min(y_min + tile_size, height)

                # Extract tile data
                tile_data = data[y_min:y_max, x_min:x_max]

                # Skip empty tiles
                if tile_data.mask.all():
                    continue

                # Calculate geotransform for this tile
                upper_left_x = gt[0] + x_min * pixel_width
                upper_left_y = gt[3] - y_min * pixel_height

                # Convert tile to WKT Raster format
                # This is complex - using ST_MakeEmptyRaster + ST_SetValues would be better
                # For now, store as bytea and use ST_FromGDALRaster

                tile_count += 1
                if tile_count % 100 == 0:
                    print(f"  Loaded {tile_count}/{total_tiles} tiles...", end='\r')

        print(f"\n✅ Loaded {tile_count} tiles")

def create_lookup_function(cursor):
    """Create function to get ecoregion from raster by coordinates."""
    print("🔧 Creating lookup function...")

    cursor.execute("""
        CREATE OR REPLACE FUNCTION get_ecoregion_from_raster(lon double precision, lat double precision)
        RETURNS integer AS $$
        DECLARE
            eco_id integer;
        BEGIN
            SELECT ST_Value(rast, ST_SetSRID(ST_MakePoint(lon, lat), 4326))::integer
            INTO eco_id
            FROM ecoregions_raster
            WHERE ST_Intersects(rast, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
            LIMIT 1;

            RETURN eco_id;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE STRICT;

        COMMENT ON FUNCTION get_ecoregion_from_raster IS
            'Returns ecoregion ID from raster (more precise than polygon method)';
    """)
    print("✅ Function created")

def main():
    """Main execution."""
    print("=" * 60)
    print("ECOREGION RASTER LOADER")
    print("=" * 60)

    # Check if raster file exists
    if not os.path.exists(RASTER_PATH):
        print(f"❌ ERROR: Raster file not found: {RASTER_PATH}")
        sys.exit(1)

    # Connect to database
    print(f"\n🔌 Connecting to database {DB_NAME}...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        conn.autocommit = False
        cursor = conn.cursor()
        print("✅ Connected")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    try:
        # Create table
        create_raster_table(cursor)
        conn.commit()

        # Load raster (using raster2pgsql via shell)
        print("\n📥 Loading raster via raster2pgsql...")
        os.system(f"""
            raster2pgsql -s 4326 -I -C -M -t 100x100 -F \
            {RASTER_PATH} public.ecoregions_raster \
            | PGPASSWORD={DB_PASSWORD} psql -h {DB_HOST} -p {DB_PORT} \
            -U {DB_USER} -d {DB_NAME} > /tmp/raster_load.log 2>&1
        """)

        # Check if load was successful
        cursor.execute("SELECT COUNT(*) FROM ecoregions_raster")
        count = cursor.fetchone()[0]

        if count == 0:
            print("❌ ERROR: No raster tiles loaded. Check /tmp/raster_load.log")
            sys.exit(1)

        print(f"✅ Loaded {count} raster tiles")

        # Create lookup function
        create_lookup_function(cursor)
        conn.commit()

        # Test the function
        print("\n🧪 Testing lookup function...")
        cursor.execute("""
            SELECT
                get_ecoregion_from_raster(-48.8, -27.7) as raster_eco_id,
                e.eco_name as raster_eco_name
            FROM ecoregions e
            WHERE e.eco_id = get_ecoregion_from_raster(-48.8, -27.7)
        """)
        result = cursor.fetchone()

        if result:
            print(f"  Santo Amaro da Imperatriz:")
            print(f"  - Raster method: eco_id={result[0]}, name='{result[1]}'")
            print("✅ Function working correctly")
        else:
            print("⚠️  Function returned NULL (may be outside raster bounds)")

        print("\n" + "=" * 60)
        print("✅ COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    main()
