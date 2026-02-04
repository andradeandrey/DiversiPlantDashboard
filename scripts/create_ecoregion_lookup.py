#!/usr/bin/env python3
"""
Create ecoregion lookup table from raster by sampling at regular grid.

This creates a lightweight alternative to full raster storage:
- Samples raster every 0.01 degrees (~1km)
- Stores (lon, lat, eco_id) tuples
- Uses spatial index for fast nearest-neighbor lookup
"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_values
import rasterio
import numpy as np
from tqdm import tqdm

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'diversiplant')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'diversiplant_dev')
DB_NAME = os.getenv('DB_NAME', 'diversiplant')

# Raster file path
RASTER_PATH = '/Users/andreyandrade/Code/DiversiPlantDashboard-sticky/data/ecoregions_raster/ecoregions_south_america.tif'

def create_lookup_table(cursor):
    """Create table to store sampled ecoregion points."""
    print("📦 Creating ecoregion_lookup table...")

    cursor.execute("""
        DROP TABLE IF EXISTS ecoregion_lookup CASCADE;

        CREATE TABLE ecoregion_lookup (
            id SERIAL PRIMARY KEY,
            location geography(POINT, 4326),
            eco_id INTEGER NOT NULL
        );

        CREATE INDEX idx_ecoregion_lookup_location
        ON ecoregion_lookup USING gist (location);

        CREATE INDEX idx_ecoregion_lookup_eco_id
        ON ecoregion_lookup (eco_id);

        COMMENT ON TABLE ecoregion_lookup IS
            'Sampled points from ecoregion raster for fast nearest-neighbor lookup';
    """)
    print("✅ Table created")

def sample_raster(cursor, sample_interval=0.01):
    """Sample raster at regular intervals and insert into database."""
    print(f"\n📊 Sampling raster (interval: {sample_interval}°)...")

    with rasterio.open(RASTER_PATH) as src:
        bounds = src.bounds
        transform = src.transform

        # Calculate sampling grid
        lon_min, lon_max = bounds.left, bounds.right
        lat_min, lat_max = bounds.bottom, bounds.top

        lons = np.arange(lon_min, lon_max, sample_interval)
        lats = np.arange(lat_min, lat_max, sample_interval)

        total_points = len(lons) * len(lats)
        print(f"Grid: {len(lons)} x {len(lats)} = {total_points:,} points")

        # Sample points
        samples = []
        valid_count = 0

        for lat in tqdm(lats, desc="Sampling rows"):
            for lon in lons:
                # Get pixel coordinates
                row, col = src.index(lon, lat)

                # Check if within bounds
                if 0 <= row < src.height and 0 <= col < src.width:
                    # Read value
                    value = src.read(1, window=((row, row+1), (col, col+1)))[0, 0]

                    # Skip nodata
                    if value > 0:
                        samples.append((lon, lat, int(value)))
                        valid_count += 1

                        # Batch insert every 10000 points
                        if len(samples) >= 10000:
                            insert_samples(cursor, samples)
                            samples = []

        # Insert remaining
        if samples:
            insert_samples(cursor, samples)

        print(f"✅ Sampled {valid_count:,} valid points")

def insert_samples(cursor, samples):
    """Bulk insert samples into database."""
    execute_values(
        cursor,
        """
        INSERT INTO ecoregion_lookup (location, eco_id)
        VALUES %s
        """,
        [(f'POINT({lon} {lat})', eco_id) for lon, lat, eco_id in samples],
        template="(ST_GeogFromText(%s), %s)"
    )

def create_lookup_function(cursor):
    """Create function to find nearest ecoregion."""
    print("\n🔧 Creating lookup function...")

    cursor.execute("""
        CREATE OR REPLACE FUNCTION get_ecoregion_from_raster(
            p_lon double precision,
            p_lat double precision,
            max_distance_m double precision DEFAULT 5000
        )
        RETURNS integer AS $$
        DECLARE
            result_eco_id integer;
        BEGIN
            -- Find nearest sampled point within max_distance
            SELECT eco_id INTO result_eco_id
            FROM ecoregion_lookup
            WHERE ST_DWithin(
                location,
                ST_GeogFromText('POINT(' || p_lon || ' ' || p_lat || ')'),
                max_distance_m
            )
            ORDER BY location <-> ST_GeogFromText('POINT(' || p_lon || ' ' || p_lat || ')')
            LIMIT 1;

            RETURN result_eco_id;
        END;
        $$ LANGUAGE plpgsql STABLE STRICT;

        COMMENT ON FUNCTION get_ecoregion_from_raster IS
            'Returns ecoregion ID using nearest-neighbor lookup from sampled raster points';

        -- Create comparison VIEW
        CREATE OR REPLACE VIEW ecoregion_comparison AS
        SELECT
            -48.8 as longitude,
            -27.7 as latitude,
            'Santo Amaro da Imperatriz, SC' as location_name,
            get_ecoregion_from_raster(-48.8, -27.7) as raster_eco_id,
            (SELECT eco_id FROM ecoregions WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(-48.8, -27.7), 4326))) as polygon_eco_id,
            (SELECT eco_name FROM ecoregions WHERE eco_id = get_ecoregion_from_raster(-48.8, -27.7)) as raster_eco_name,
            (SELECT eco_name FROM ecoregions WHERE eco_id = (SELECT eco_id FROM ecoregions WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(-48.8, -27.7), 4326)))) as polygon_eco_name;

        COMMENT ON VIEW ecoregion_comparison IS
            'Compare raster vs polygon ecoregion identification methods';
    """)
    print("✅ Function and view created")

def main():
    """Main execution."""
    print("=" * 70)
    print("ECOREGION LOOKUP TABLE CREATOR")
    print("=" * 70)

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
        create_lookup_table(cursor)
        conn.commit()

        # Sample raster
        sample_raster(cursor, sample_interval=0.01)  # ~1km resolution
        conn.commit()

        # Create lookup function
        create_lookup_function(cursor)
        conn.commit()

        # Test and compare methods
        print("\n🧪 Testing comparison...")
        cursor.execute("SELECT * FROM ecoregion_comparison")
        result = cursor.fetchone()

        print("\n" + "=" * 70)
        print(f"Location: {result[2]}")
        print(f"Coordinates: ({result[0]}, {result[1]})")
        print("-" * 70)
        print(f"Raster method:  eco_id={result[3]:3d} - {result[5]}")
        print(f"Polygon method: eco_id={result[4]:3d} - {result[6]}")
        print("=" * 70)

        if result[3] != result[4]:
            print("⚠️  Methods disagree! Raster is more precise.")
        else:
            print("✅ Methods agree!")

        # Statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total_points,
                COUNT(DISTINCT eco_id) as unique_ecoregions,
                pg_size_pretty(pg_total_relation_size('ecoregion_lookup')) as table_size
            FROM ecoregion_lookup
        """)
        stats = cursor.fetchone()

        print("\n" + "=" * 70)
        print("STATISTICS:")
        print(f"  Total sample points: {stats[0]:,}")
        print(f"  Unique ecoregions: {stats[1]}")
        print(f"  Table size: {stats[2]}")
        print("=" * 70)

        print("\n✅ COMPLETED SUCCESSFULLY")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    main()
