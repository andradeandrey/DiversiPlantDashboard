#!/usr/bin/env python3
"""
WorldClim Raster Loader

Downloads WorldClim 2.1 bioclimatic rasters and loads them into PostGIS
for precise point-based climate queries.

Usage:
    python worldclim_raster.py [--resolution 10m] [--bio bio1,bio2,bio12]

Resolution options:
    - 10m: 10 arc-minutes (~340 km² at equator) - smallest files, fastest
    - 5m: 5 arc-minutes (~85 km²) - good balance
    - 2.5m: 2.5 arc-minutes (~21 km²) - detailed
    - 30s: 30 arc-seconds (~1 km²) - most detailed, large files

Note: Requires raster2pgsql (comes with PostGIS) and GDAL tools.
"""

import os
import sys
import argparse
import subprocess
import tempfile
import zipfile
import logging
from pathlib import Path
from urllib.request import urlretrieve
from urllib.error import URLError
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# WorldClim 2.1 download URLs
WORLDCLIM_BASE_URL = "https://biogeo.ucdavis.edu/data/worldclim/v2.1/base"

# Resolution configurations
RESOLUTIONS = {
    '10m': {'folder': 'wc2.1_10m', 'desc': '10 arc-minutes'},
    '5m': {'folder': 'wc2.1_5m', 'desc': '5 arc-minutes'},
    '2.5m': {'folder': 'wc2.1_2.5m', 'desc': '2.5 arc-minutes'},
    '30s': {'folder': 'wc2.1_30s', 'desc': '30 arc-seconds'},
}

# All bioclimatic variables
ALL_BIO_VARS = [f'bio{i}' for i in range(1, 20)]


def get_db_connection_string():
    """Get database connection string from environment."""
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    user = os.getenv('DB_USER', os.getenv('POSTGRES_USER', 'diversiplant'))
    password = os.getenv('DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', 'diversiplant_dev'))
    dbname = os.getenv('DB_NAME', os.getenv('POSTGRES_DB', 'diversiplant'))
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def check_dependencies():
    """Check if required tools are available."""
    tools = ['raster2pgsql', 'gdalinfo']
    missing = []

    for tool in tools:
        if shutil.which(tool) is None:
            missing.append(tool)

    if missing:
        logger.error(f"Missing required tools: {', '.join(missing)}")
        logger.error("Install PostGIS (for raster2pgsql) and GDAL (for gdalinfo)")
        return False

    return True


def download_worldclim(resolution: str, bio_var: str, output_dir: Path) -> Path:
    """Download WorldClim raster for a specific variable."""
    res_config = RESOLUTIONS[resolution]
    folder = res_config['folder']

    # WorldClim 2.1 file naming convention
    filename = f"{folder}_bio_{bio_var.replace('bio', '')}.zip"
    url = f"{WORLDCLIM_BASE_URL}/{filename}"

    zip_path = output_dir / filename

    if zip_path.exists():
        logger.info(f"Using cached: {filename}")
    else:
        logger.info(f"Downloading: {url}")
        try:
            urlretrieve(url, zip_path)
        except URLError as e:
            logger.error(f"Failed to download {url}: {e}")
            return None

    # Extract the zip
    tif_dir = output_dir / f"{folder}_{bio_var}"
    if not tif_dir.exists():
        logger.info(f"Extracting: {filename}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tif_dir)

    # Find the .tif file
    tif_files = list(tif_dir.rglob("*.tif"))
    if not tif_files:
        logger.error(f"No .tif file found in {tif_dir}")
        return None

    return tif_files[0]


def load_raster_to_postgis(
    tif_path: Path,
    bio_var: str,
    resolution: str,
    db_conn: str,
    tile_size: int = 100
) -> bool:
    """Load a raster file into PostGIS using raster2pgsql."""

    logger.info(f"Loading {bio_var} into PostGIS (tile size: {tile_size}x{tile_size})...")

    # Build raster2pgsql command
    # -s 4326: SRID (WGS84)
    # -t: tile size
    # -I: create spatial index
    # -C: apply raster constraints
    # -M: vacuum analyze after load
    # -a: append mode (don't create table)
    # -F: add filename column

    # First, check if this bio_var already exists
    check_cmd = f"""psql "{db_conn}" -t -c "SELECT COUNT(*) FROM worldclim_raster WHERE bio_var = '{bio_var}'" """
    try:
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        count = int(result.stdout.strip()) if result.stdout.strip() else 0
        if count > 0:
            logger.info(f"Skipping {bio_var} - already loaded ({count} tiles)")
            return True
    except Exception as e:
        logger.warning(f"Could not check existing data: {e}")

    # Use raster2pgsql to generate SQL and pipe to psql
    raster2pgsql_cmd = [
        'raster2pgsql',
        '-s', '4326',
        '-t', f'{tile_size}x{tile_size}',
        '-I',
        '-C',
        '-M',
        '-a',  # append mode
        '-F',  # add filename
        str(tif_path),
        'worldclim_raster'
    ]

    # We need to modify the SQL to include bio_var and resolution
    # Use a temp file approach
    logger.info(f"Generating SQL for {bio_var}...")

    try:
        # Generate SQL
        result = subprocess.run(
            raster2pgsql_cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for large files
        )

        if result.returncode != 0:
            logger.error(f"raster2pgsql failed: {result.stderr}")
            return False

        sql = result.stdout

        # Modify SQL to include bio_var and resolution
        # The INSERT statements look like: INSERT INTO worldclim_raster (rast, filename) VALUES (...)
        # We need to add bio_var and resolution columns

        # Replace the INSERT pattern
        sql = sql.replace(
            'INSERT INTO "worldclim_raster" ("rast","filename") VALUES',
            f"INSERT INTO worldclim_raster (rast, filename, bio_var, resolution) VALUES"
        )

        # Add bio_var and resolution to each VALUES clause
        # This is a bit tricky - we need to add them after the filename value
        import re

        def add_columns(match):
            # match.group(0) is like: VALUES ('...rast...','filename.tif')
            # We need to add ,'bio1','10m' before the closing )
            return match.group(0)[:-1] + f",'{bio_var}','{resolution}')"

        sql = re.sub(r"VALUES\s*\([^)]+\)", add_columns, sql)

        # Write to temp file and execute
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(sql)
            temp_sql = f.name

        logger.info(f"Loading {bio_var} into database...")

        psql_cmd = f'psql "{db_conn}" -f "{temp_sql}"'
        result = subprocess.run(
            psql_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout
        )

        # Clean up temp file
        os.unlink(temp_sql)

        if result.returncode != 0:
            logger.error(f"psql failed: {result.stderr}")
            return False

        logger.info(f"Successfully loaded {bio_var}")
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout loading {bio_var}")
        return False
    except Exception as e:
        logger.error(f"Error loading {bio_var}: {e}")
        return False


def load_raster_python(
    tif_path: Path,
    bio_var: str,
    resolution: str,
    tile_size: int = 100
) -> bool:
    """Alternative: Load raster using Python (rasterio + psycopg2).

    This is slower but doesn't require raster2pgsql CLI.
    """
    try:
        import rasterio
        import psycopg2
        from psycopg2 import sql
        import numpy as np
    except ImportError:
        logger.error("This method requires: pip install rasterio psycopg2-binary numpy")
        return False

    logger.info(f"Loading {bio_var} using Python (slower method)...")

    # Get connection parameters
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    user = os.getenv('DB_USER', os.getenv('POSTGRES_USER', 'diversiplant'))
    password = os.getenv('DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', 'diversiplant_dev'))
    dbname = os.getenv('DB_NAME', os.getenv('POSTGRES_DB', 'diversiplant'))

    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname
    )

    try:
        with rasterio.open(tif_path) as src:
            # Read metadata
            transform = src.transform
            crs = src.crs
            width = src.width
            height = src.height
            nodata = src.nodata

            logger.info(f"Raster: {width}x{height} pixels")

            # Calculate number of tiles
            n_tiles_x = (width + tile_size - 1) // tile_size
            n_tiles_y = (height + tile_size - 1) // tile_size
            total_tiles = n_tiles_x * n_tiles_y

            logger.info(f"Creating {total_tiles} tiles ({n_tiles_x}x{n_tiles_y})...")

            cursor = conn.cursor()
            loaded = 0

            for ty in range(n_tiles_y):
                for tx in range(n_tiles_x):
                    # Calculate window
                    col_off = tx * tile_size
                    row_off = ty * tile_size
                    win_width = min(tile_size, width - col_off)
                    win_height = min(tile_size, height - row_off)

                    window = rasterio.windows.Window(col_off, row_off, win_width, win_height)

                    # Read tile data
                    data = src.read(1, window=window)

                    # Skip empty tiles
                    if nodata is not None and np.all(data == nodata):
                        continue

                    # Calculate tile transform
                    tile_transform = rasterio.windows.transform(window, transform)

                    # Create WKT raster (simplified - PostGIS can import this)
                    # This is complex, so we'll use ST_MakeEmptyRaster + ST_SetValues

                    upperleft_x = tile_transform.c
                    upperleft_y = tile_transform.f
                    scale_x = tile_transform.a
                    scale_y = tile_transform.e

                    # Insert using ST_MakeEmptyRaster
                    cursor.execute("""
                        INSERT INTO worldclim_raster (bio_var, resolution, filename, rast)
                        VALUES (%s, %s, %s,
                            ST_SetValues(
                                ST_AddBand(
                                    ST_MakeEmptyRaster(%s, %s, %s, %s, %s, %s, 0, 0, 4326),
                                    1, '32BF', %s, %s
                                ),
                                1, 1, 1, %s
                            )
                        )
                    """, (
                        bio_var, resolution, str(tif_path.name),
                        win_width, win_height, upperleft_x, upperleft_y, scale_x, scale_y,
                        float(nodata) if nodata else -9999.0, float(nodata) if nodata else -9999.0,
                        data.tolist()
                    ))

                    loaded += 1

                    if loaded % 1000 == 0:
                        conn.commit()
                        logger.info(f"Loaded {loaded}/{total_tiles} tiles...")

            conn.commit()
            logger.info(f"Loaded {loaded} tiles for {bio_var}")

            # Create spatial index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_worldclim_raster_gist
                ON worldclim_raster USING GIST (ST_ConvexHull(rast))
            """)
            conn.commit()

            return True

    except Exception as e:
        logger.error(f"Error loading raster: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Load WorldClim rasters into PostGIS')
    parser.add_argument('--resolution', '-r', default='10m',
                        choices=list(RESOLUTIONS.keys()),
                        help='WorldClim resolution (default: 10m)')
    parser.add_argument('--bio', '-b', default='bio1,bio12',
                        help='Comma-separated list of bio variables (default: bio1,bio12)')
    parser.add_argument('--all-bio', action='store_true',
                        help='Load all 19 bio variables')
    parser.add_argument('--tile-size', '-t', type=int, default=100,
                        help='Tile size in pixels (default: 100)')
    parser.add_argument('--data-dir', '-d', default='./data/worldclim',
                        help='Directory to store downloaded files')
    parser.add_argument('--use-python', action='store_true',
                        help='Use Python method instead of raster2pgsql (slower)')
    parser.add_argument('--apply-migration', action='store_true',
                        help='Apply database migration first')

    args = parser.parse_args()

    # Check dependencies
    if not args.use_python and not check_dependencies():
        logger.error("Missing dependencies. Use --use-python for alternative method.")
        sys.exit(1)

    # Parse bio variables
    if args.all_bio:
        bio_vars = ALL_BIO_VARS
    else:
        bio_vars = [b.strip() for b in args.bio.split(',')]
        for bv in bio_vars:
            if bv not in ALL_BIO_VARS:
                logger.error(f"Invalid bio variable: {bv}. Valid: {ALL_BIO_VARS}")
                sys.exit(1)

    # Create data directory
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Get database connection
    db_conn = get_db_connection_string()

    # Apply migration if requested
    if args.apply_migration:
        migration_file = Path(__file__).parent.parent / 'database' / 'migrations' / '007_worldclim_raster.sql'
        if migration_file.exists():
            logger.info("Applying migration...")
            cmd = f'psql "{db_conn}" -f "{migration_file}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Migration failed: {result.stderr}")
                sys.exit(1)
            logger.info("Migration applied successfully")
        else:
            logger.warning(f"Migration file not found: {migration_file}")

    logger.info(f"Loading WorldClim {args.resolution} rasters: {bio_vars}")

    success_count = 0
    for bio_var in bio_vars:
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {bio_var}...")

        # Download
        tif_path = download_worldclim(args.resolution, bio_var, data_dir)
        if not tif_path:
            continue

        # Load into PostGIS
        if args.use_python:
            success = load_raster_python(tif_path, bio_var, args.resolution, args.tile_size)
        else:
            success = load_raster_to_postgis(tif_path, bio_var, args.resolution, db_conn, args.tile_size)

        if success:
            success_count += 1

    logger.info(f"\n{'='*50}")
    logger.info(f"Completed: {success_count}/{len(bio_vars)} variables loaded")

    # Show sample query
    logger.info("\nTest query (Florianópolis):")
    logger.info(f"  psql -c \"SELECT * FROM get_climate_at_point(-27.5954, -48.5480)\"")


if __name__ == '__main__':
    main()
