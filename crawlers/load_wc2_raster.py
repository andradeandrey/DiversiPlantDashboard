#!/usr/bin/env python3
"""
Load existing WorldClim TIF files into PostGIS raster table.
Uses rasterio for reading and psycopg2 for inserting.
"""

import os
import sys
from pathlib import Path

# Check dependencies
try:
    import rasterio
    import numpy as np
    import psycopg2
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install rasterio numpy psycopg2-binary")
    sys.exit(1)

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data" / "wc2"
TILE_SIZE = 50  # Smaller tiles for faster queries

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'user': os.getenv('DB_USER', os.getenv('POSTGRES_USER', 'diversiplant')),
    'password': os.getenv('DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', 'diversiplant_dev')),
    'dbname': os.getenv('DB_NAME', os.getenv('POSTGRES_DB', 'diversiplant')),
}


def load_raster(tif_path: Path, bio_var: str, conn) -> int:
    """Load a single raster file into PostGIS."""

    print(f"Loading {bio_var} from {tif_path.name}...")

    cursor = conn.cursor()

    # Check if already loaded
    cursor.execute("SELECT COUNT(*) FROM worldclim_raster WHERE bio_var = %s", (bio_var,))
    if cursor.fetchone()[0] > 0:
        print(f"  {bio_var} already loaded, skipping")
        return 0

    with rasterio.open(tif_path) as src:
        # Get metadata
        width = src.width
        height = src.height
        transform = src.transform
        nodata = src.nodata if src.nodata is not None else -3.4e38

        print(f"  Raster size: {width}x{height}")

        # Calculate tiles
        n_tiles_x = (width + TILE_SIZE - 1) // TILE_SIZE
        n_tiles_y = (height + TILE_SIZE - 1) // TILE_SIZE
        total_tiles = n_tiles_x * n_tiles_y

        print(f"  Creating up to {total_tiles} tiles...")

        loaded = 0
        skipped = 0

        for ty in range(n_tiles_y):
            for tx in range(n_tiles_x):
                # Calculate window bounds
                col_off = tx * TILE_SIZE
                row_off = ty * TILE_SIZE
                win_width = min(TILE_SIZE, width - col_off)
                win_height = min(TILE_SIZE, height - row_off)

                # Read tile data
                window = rasterio.windows.Window(col_off, row_off, win_width, win_height)
                data = src.read(1, window=window)

                # Skip tiles that are all nodata
                valid_mask = ~np.isclose(data, nodata, rtol=1e-5)
                if not np.any(valid_mask):
                    skipped += 1
                    continue

                # Calculate tile geotransform
                tile_transform = rasterio.windows.transform(window, transform)

                upperleft_x = tile_transform.c
                upperleft_y = tile_transform.f
                scale_x = tile_transform.a
                scale_y = tile_transform.e

                # Convert data to list of lists for PostgreSQL
                # Replace nodata with NULL-friendly value
                data_clean = np.where(valid_mask, data, None)

                # Build the raster using ST_MakeEmptyRaster + ST_SetValues
                # This is slower but works without raster2pgsql
                try:
                    # Create raster with proper georeference
                    cursor.execute("""
                        INSERT INTO worldclim_raster (bio_var, resolution, filename, rast)
                        SELECT
                            %s, '10m', %s,
                            ST_SetBandNoDataValue(
                                ST_SetValues(
                                    ST_AddBand(
                                        ST_MakeEmptyRaster(%s, %s, %s::float8, %s::float8, %s::float8, %s::float8, 0, 0, 4326),
                                        1, '32BF'::text, %s::float8, %s::float8
                                    ),
                                    1, 1, 1, %s::float8[][]
                                ),
                                1, %s::float8
                            )
                    """, (
                        bio_var,
                        tif_path.name,
                        win_width, win_height,
                        upperleft_x, upperleft_y,
                        scale_x, scale_y,
                        float(nodata), float(nodata),
                        data.tolist(),
                        float(nodata)
                    ))
                    loaded += 1
                except Exception as e:
                    print(f"  Error inserting tile: {e}")
                    conn.rollback()
                    continue

                if loaded % 500 == 0:
                    conn.commit()
                    pct = (ty * n_tiles_x + tx + 1) / total_tiles * 100
                    print(f"  Progress: {loaded} tiles loaded ({pct:.1f}%)")

        conn.commit()
        print(f"  Done: {loaded} tiles loaded, {skipped} empty tiles skipped")
        return loaded


def main():
    # Find all TIF files
    tif_files = sorted(DATA_DIR.glob("wc2.1_10m_bio_*.tif"))

    if not tif_files:
        print(f"No TIF files found in {DATA_DIR}")
        sys.exit(1)

    print(f"Found {len(tif_files)} TIF files")

    # Connect to database
    print(f"Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        total_loaded = 0

        for tif_path in tif_files:
            # Extract bio variable name (bio1, bio2, etc.)
            # Filename format: wc2.1_10m_bio_1.tif
            parts = tif_path.stem.split('_')
            bio_num = parts[-1]
            bio_var = f"bio{bio_num}"

            loaded = load_raster(tif_path, bio_var, conn)
            total_loaded += loaded

        print(f"\n{'='*50}")
        print(f"Total: {total_loaded} tiles loaded")

        # Create spatial index if not exists
        print("Ensuring spatial index exists...")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_worldclim_raster_gist
            ON worldclim_raster USING GIST (ST_ConvexHull(rast))
        """)
        conn.commit()

        # Show summary
        cursor.execute("""
            SELECT bio_var, COUNT(*) as tiles
            FROM worldclim_raster
            GROUP BY bio_var
            ORDER BY bio_var
        """)
        print("\nTiles per variable:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} tiles")

        print("\nTest query (Florianópolis):")
        print("  SELECT * FROM get_climate_at_point(-27.5954, -48.5480);")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
