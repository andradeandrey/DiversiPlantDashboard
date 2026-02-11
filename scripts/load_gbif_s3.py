#!/usr/bin/env python3
"""
GBIF S3 Parquet Loader via DuckDB.

Bypasses GBIF API rate limits by querying GBIF open data on AWS S3 directly
using DuckDB. Processes ~286k pending species in bulk.

Phases:
    1. export   - Export species keys from PostgreSQL to local Parquet
    2. extract  - Query S3 Parquet via DuckDB, filter+sample occurrences
    3. load     - Load extracted occurrences into PostgreSQL
    4. climate  - Extract WorldClim climate at each occurrence point
    5. envelope - Calculate climate envelopes from occurrence data
    6. ecoregion - Spatial join occurrences → ecoregions → species_ecoregions

Usage:
    python scripts/load_gbif_s3.py                          # Run all phases
    python scripts/load_gbif_s3.py --phase extract           # Run single phase
    python scripts/load_gbif_s3.py --phase climate --batch-size 10000
    python scripts/load_gbif_s3.py --snapshot 2024-10-01     # Use specific GBIF snapshot
    python scripts/load_gbif_s3.py --growth-forms graminoid,bamboo --force  # Filter by growth form
    python scripts/load_gbif_s3.py --dry-run                 # Preview without writing

Dependencies:
    pip install duckdb pyarrow psycopg2-binary sqlalchemy numpy
"""

import argparse
import csv
import io
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('gbif_s3_loader')

# Data directory
DATA_DIR = Path(__file__).parent.parent / 'data' / 'gbif_s3'

# GBIF S3 bucket
GBIF_S3_BUCKET = 's3://gbif-open-data-us-east-1/occurrence'

# Quality filters (matching crawlers/gbif_occurrences.py)
MAX_UNCERTAINTY_M = 10000
MIN_YEAR = 1970
MAX_OCCURRENCES_PER_SPECIES = 500

# Climate extraction
CLIMATE_BIO_VARS = ['bio1', 'bio5', 'bio6', 'bio7', 'bio12', 'bio15']

# Envelope calculation
MIN_OCCURRENCES_FOR_ENVELOPE = 10

# Valid growth forms (from WCVP reclassification)
VALID_GROWTH_FORMS = [
    'graminoid', 'forb', 'subshrub', 'shrub', 'tree',
    'scrambler', 'vine', 'liana', 'palm', 'bamboo', 'other',
]

# Ecoregion mapping
ECOREGION_BATCH_SIZE = 50


def get_db_url():
    """Get database URL from environment."""
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        logger.error(
            "DATABASE_URL not set. "
            "Set it with: export DATABASE_URL=postgresql://user:pass@host/diversiplant"
        )
        sys.exit(1)
    return url


def get_engine(db_url=None):
    """Create SQLAlchemy engine."""
    from sqlalchemy import create_engine
    return create_engine(db_url or get_db_url())


def get_psycopg2_conn(db_url=None):
    """Create psycopg2 connection for COPY operations."""
    import psycopg2
    url = db_url or get_db_url()
    # Convert SQLAlchemy URL to psycopg2 format if needed
    if url.startswith('postgresql+psycopg2://'):
        url = url.replace('postgresql+psycopg2://', 'postgresql://')
    return psycopg2.connect(url)


# ============================================================
# Phase 1: Export species keys from PostgreSQL
# ============================================================

def phase_export_keys(db_url=None, force=False, limit=None, growth_forms=None):
    """
    Export species that need GBIF envelopes to a local Parquet file.

    Output: data/gbif_s3/species_keys.parquet
    Resumable: LEFT JOIN excludes species that already have envelopes.

    Args:
        limit: Max species to export (for batch mode). None = all pending.
        growth_forms: List of growth form strings to filter by. When set,
                      exports ALL matching species (ignores envelope status).
    """
    output_path = DATA_DIR / 'species_keys.parquet'

    if output_path.exists() and not force:
        import pyarrow.parquet as pq
        table = pq.read_table(str(output_path))
        logger.info(
            f"Phase 1 SKIP: species_keys.parquet already exists "
            f"({len(table)} species). Use --force to regenerate."
        )
        return len(table)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    limit_clause = f"LIMIT {limit}" if limit else ""
    gf_label = f" [growth_forms={','.join(growth_forms)}]" if growth_forms else ""
    logger.info(f"Phase 1: Exporting species keys from PostgreSQL...{f' (limit {limit})' if limit else ''}{gf_label}")

    from sqlalchemy import text
    from sqlalchemy.orm import Session
    import pyarrow as pa
    import pyarrow.parquet as pq

    engine = get_engine(db_url)

    with Session(engine) as session:
        if growth_forms:
            # Growth form filter: export ALL matching species regardless of envelope status
            gf_placeholders = ', '.join(f"'{gf}'" for gf in growth_forms)
            result = session.execute(text(f"""
                SELECT
                    s.id as species_id,
                    s.gbif_taxon_key,
                    s.canonical_name
                FROM species s
                JOIN species_unified su ON s.id = su.species_id
                WHERE s.gbif_taxon_key IS NOT NULL
                  AND su.growth_form IN ({gf_placeholders})
                ORDER BY s.id
                {limit_clause}
            """))
        else:
            # Default: only species missing GBIF envelopes
            result = session.execute(text(f"""
                SELECT
                    s.id as species_id,
                    s.gbif_taxon_key,
                    s.canonical_name
                FROM species s
                JOIN species_unified su ON s.id = su.species_id
                LEFT JOIN climate_envelope_gbif ceg ON s.id = ceg.species_id
                WHERE s.gbif_taxon_key IS NOT NULL
                  AND ceg.species_id IS NULL
                  AND su.growth_form IS NOT NULL
                ORDER BY s.id
                {limit_clause}
            """))

        rows = result.fetchall()

    if not rows:
        logger.info("Phase 1: No species need GBIF envelopes. Nothing to export.")
        return 0

    species_ids = [r[0] for r in rows]
    taxon_keys = [r[1] for r in rows]
    names = [r[2] for r in rows]

    table = pa.table({
        'species_id': pa.array(species_ids, type=pa.int32()),
        'gbif_taxon_key': pa.array(taxon_keys, type=pa.int64()),
        'canonical_name': pa.array(names, type=pa.string()),
    })

    pq.write_table(table, str(output_path))

    logger.info(f"Phase 1 DONE: Exported {len(rows)} species keys to {output_path}")
    return len(rows)


# ============================================================
# Phase 2: Extract occurrences from S3 via DuckDB
# ============================================================

def get_latest_snapshot():
    """Try to find the latest GBIF snapshot date on S3."""
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region = 'us-east-1';")

    try:
        result = con.execute(f"""
            SELECT DISTINCT regexp_extract(filename, '(\\d{{4}}-\\d{{2}}-\\d{{2}})', 1) as snapshot_date
            FROM glob('{GBIF_S3_BUCKET}/*/occurrence.parquet/000000')
            ORDER BY snapshot_date DESC
            LIMIT 1
        """).fetchone()

        if result:
            return result[0]
    except Exception:
        pass
    finally:
        con.close()

    return None


def phase_extract_s3(snapshot_date=None, db_url=None, force=False, memory_limit='4GB',
                     batch_size=None, max_files=None, start_file=None):
    """
    Extract occurrences from GBIF S3 Parquet using DuckDB.

    Performs INNER JOIN on specieskey to get only our species,
    samples max 500 per species (best quality first).

    Output: data/gbif_s3/occurrences_extract.parquet
    Resumable: Skips if output file already exists.
    """
    import duckdb

    keys_path = DATA_DIR / 'species_keys.parquet'
    output_path = DATA_DIR / 'occurrences_extract.parquet'

    if not keys_path.exists():
        logger.error("Phase 2: species_keys.parquet not found. Run phase 'export' first.")
        return 0

    if output_path.exists() and not force:
        import pyarrow.parquet as pq
        meta = pq.read_metadata(str(output_path))
        logger.info(
            f"Phase 2 SKIP: occurrences_extract.parquet already exists "
            f"({meta.num_rows} rows). Use --force to regenerate."
        )
        return meta.num_rows

    # Determine snapshot date
    if not snapshot_date:
        snapshot_date = '2024-10-01'  # Reasonable default
        logger.info(f"Using default GBIF snapshot: {snapshot_date}")
    else:
        logger.info(f"Using GBIF snapshot: {snapshot_date}")

    if max_files:
        # Generate list of specific file paths to limit data scanned
        start_idx = start_file or 0
        end_idx = start_idx + max_files
        s3_files = [
            f'{GBIF_S3_BUCKET}/{snapshot_date}/occurrence.parquet/{i:06d}'
            for i in range(start_idx, end_idx)
        ]
        s3_path = s3_files  # Will be passed as list to read_parquet
        est_gb = max_files * 0.1
        logger.info(
            f"Phase 2: Extracting from files {start_idx}-{end_idx-1} "
            f"({max_files} files, ~{est_gb:.0f}GB) of snapshot {snapshot_date}"
        )
    else:
        s3_path = f'{GBIF_S3_BUCKET}/{snapshot_date}/occurrence.parquet/*'
        logger.info(f"Phase 2: Extracting occurrences from {s3_path} (~200GB)")
    logger.info(f"  Memory limit: {memory_limit}")

    start_time = time.time()

    con = duckdb.connect()

    try:
        # Configure DuckDB for S3 anonymous access
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("SET s3_region = 'us-east-1';")
        con.execute(f"SET memory_limit = '{memory_limit}';")

        # Use temp directory for spill
        temp_dir = DATA_DIR / 'duckdb_temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        con.execute(f"SET temp_directory = '{temp_dir}';")

        # Load species keys
        con.execute(f"""
            CREATE TABLE species_keys AS
            SELECT species_id, gbif_taxon_key
            FROM read_parquet('{keys_path}')
        """)

        n_species = con.execute("SELECT COUNT(*) FROM species_keys").fetchone()[0]
        logger.info(f"  Loaded {n_species} species keys")

        if batch_size and n_species > batch_size:
            # Process in batches to avoid OOM
            total_rows = _extract_in_batches(con, s3_path, output_path, batch_size)
        else:
            # Single query for all species
            total_rows = _extract_single_query(con, s3_path, output_path)

        elapsed = time.time() - start_time
        logger.info(
            f"Phase 2 DONE: Extracted {total_rows:,} occurrences "
            f"in {elapsed/60:.1f} minutes"
        )
        return total_rows

    except Exception as e:
        logger.error(f"Phase 2 FAILED: {e}")
        # Clean up partial output
        if output_path.exists():
            output_path.unlink()
        raise
    finally:
        con.close()


def _format_s3_path(s3_path):
    """Format s3_path for DuckDB read_parquet (string or list)."""
    if isinstance(s3_path, list):
        quoted = ', '.join(f"'{f}'" for f in s3_path)
        return f"[{quoted}]"
    return f"'{s3_path}'"


def _extract_single_query(con, s3_path, output_path, max_retries=3):
    """Run a single DuckDB query to extract all occurrences with retry on S3 errors."""
    logger.info("  Running extraction query (single pass)...")

    parquet_src = _format_s3_path(s3_path)

    for attempt in range(1, max_retries + 1):
        try:
            return _do_extract_query(con, parquet_src, output_path)
        except Exception as e:
            error_str = str(e)
            if 'HTTP 403' in error_str or 'HTTP 503' in error_str:
                if attempt < max_retries:
                    wait_time = 30 * attempt  # 30s, 60s, 90s
                    logger.warning(
                        f"  S3 rate limit (attempt {attempt}/{max_retries}), "
                        f"waiting {wait_time}s before retry..."
                    )
                    time.sleep(wait_time)
                    continue
            raise

    raise Exception(f"Failed after {max_retries} retries")


def _do_extract_query(con, parquet_src, output_path):
    """Execute the actual DuckDB extraction query."""

    con.execute(f"""
        COPY (
            WITH ranked AS (
                SELECT
                    occ.gbifid,
                    sk.species_id,
                    occ.decimallatitude AS latitude,
                    occ.decimallongitude AS longitude,
                    occ.coordinateuncertaintyinmeters AS uncertainty_m,
                    occ.year,
                    occ.countrycode AS country_code,
                    ROW_NUMBER() OVER (
                        PARTITION BY occ.specieskey
                        ORDER BY
                            occ.coordinateuncertaintyinmeters ASC NULLS LAST,
                            occ.year DESC NULLS LAST
                    ) AS rn
                FROM read_parquet({parquet_src},
                                  hive_partitioning=false) occ
                INNER JOIN species_keys sk
                    ON occ.specieskey = sk.gbif_taxon_key
                WHERE occ.decimallatitude IS NOT NULL
                  AND occ.decimallongitude IS NOT NULL
                  AND ABS(occ.decimallatitude) <= 90
                  AND ABS(occ.decimallongitude) <= 180
                  AND NOT (occ.decimallatitude = 0 AND occ.decimallongitude = 0)
                  AND occ.kingdom = 'Plantae'
                  AND (occ.coordinateuncertaintyinmeters IS NULL
                       OR occ.coordinateuncertaintyinmeters <= {MAX_UNCERTAINTY_M})
                  AND (occ.year IS NULL OR occ.year >= {MIN_YEAR})
            )
            SELECT
                gbifid,
                species_id,
                latitude,
                longitude,
                uncertainty_m,
                year,
                country_code
            FROM ranked
            WHERE rn <= {MAX_OCCURRENCES_PER_SPECIES}
        ) TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    import pyarrow.parquet as pq
    meta = pq.read_metadata(str(output_path))
    return meta.num_rows


def _extract_in_batches(con, s3_path, output_path, batch_size):
    """Process species in batches to avoid OOM."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    parquet_src = _format_s3_path(s3_path)

    total_species = con.execute("SELECT COUNT(*) FROM species_keys").fetchone()[0]
    n_batches = (total_species + batch_size - 1) // batch_size

    logger.info(f"  Processing {total_species} species in {n_batches} batches of {batch_size}")

    all_tables = []
    offset = 0

    for batch_num in range(n_batches):
        batch_start = time.time()
        logger.info(f"  Batch {batch_num + 1}/{n_batches} (offset {offset})...")

        # Create batch-specific key table
        con.execute(f"""
            CREATE OR REPLACE TABLE batch_keys AS
            SELECT species_id, gbif_taxon_key
            FROM species_keys
            ORDER BY species_id
            LIMIT {batch_size} OFFSET {offset}
        """)

        batch_count = con.execute("SELECT COUNT(*) FROM batch_keys").fetchone()[0]
        if batch_count == 0:
            break

        batch_output = DATA_DIR / f'batch_{batch_num}.parquet'

        try:
            con.execute(f"""
                COPY (
                    WITH ranked AS (
                        SELECT
                            occ.gbifid,
                            sk.species_id,
                            occ.decimallatitude AS latitude,
                            occ.decimallongitude AS longitude,
                            occ.coordinateuncertaintyinmeters AS uncertainty_m,
                            occ.year,
                            occ.countrycode AS country_code,
                            ROW_NUMBER() OVER (
                                PARTITION BY occ.specieskey
                                ORDER BY
                                    occ.coordinateuncertaintyinmeters ASC NULLS LAST,
                                    occ.year DESC NULLS LAST
                            ) AS rn
                        FROM read_parquet({parquet_src},
                                          hive_partitioning=false) occ
                        INNER JOIN batch_keys sk
                            ON occ.specieskey = sk.gbif_taxon_key
                        WHERE occ.decimallatitude IS NOT NULL
                          AND occ.decimallongitude IS NOT NULL
                          AND ABS(occ.decimallatitude) <= 90
                          AND ABS(occ.decimallongitude) <= 180
                          AND NOT (occ.decimallatitude = 0 AND occ.decimallongitude = 0)
                          AND occ.kingdom = 'Plantae'
                          AND (occ.coordinateuncertaintyinmeters IS NULL
                               OR occ.coordinateuncertaintyinmeters <= {MAX_UNCERTAINTY_M})
                          AND (occ.year IS NULL OR occ.year >= {MIN_YEAR})
                    )
                    SELECT gbifid, species_id, latitude, longitude,
                           uncertainty_m, year, country_code
                    FROM ranked
                    WHERE rn <= {MAX_OCCURRENCES_PER_SPECIES}
                ) TO '{batch_output}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """)

            batch_table = pq.read_table(str(batch_output))
            all_tables.append(batch_table)
            n_rows = len(batch_table)

            elapsed = time.time() - batch_start
            logger.info(f"    Batch {batch_num + 1}: {n_rows:,} rows in {elapsed/60:.1f}m")

        finally:
            if batch_output.exists():
                batch_output.unlink()

        offset += batch_size

    if all_tables:
        combined = pa.concat_tables(all_tables)
        pq.write_table(combined, str(output_path), compression='zstd')
        return len(combined)

    return 0


# ============================================================
# Phase 3: Load occurrences into PostgreSQL
# ============================================================

def phase_load_postgres(db_url=None, force=False, chunk_size=100000):
    """
    Load extracted occurrences into PostgreSQL gbif_occurrences table.

    Uses a staging table + INSERT...ON CONFLICT for idempotent loading.
    Resumable: ON CONFLICT (gbif_id) DO NOTHING skips already-loaded records.
    """
    import pyarrow.parquet as pq
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    input_path = DATA_DIR / 'occurrences_extract.parquet'

    if not input_path.exists():
        logger.error("Phase 3: occurrences_extract.parquet not found. Run phase 'extract' first.")
        return 0

    logger.info("Phase 3: Loading occurrences into PostgreSQL...")

    # Read the extracted data
    table = pq.read_table(str(input_path))
    total_rows = len(table)
    logger.info(f"  Total rows to load: {total_rows:,}")

    if total_rows == 0:
        logger.info("Phase 3: No rows to load.")
        return 0

    # Check how many are already loaded
    engine = get_engine(db_url)
    with Session(engine) as session:
        existing = session.execute(text(
            "SELECT COUNT(*) FROM gbif_occurrences"
        )).scalar()
        logger.info(f"  Existing gbif_occurrences rows: {existing:,}")

    # Use psycopg2 for fast COPY loading
    conn = get_psycopg2_conn(db_url)
    cur = conn.cursor()

    start_time = time.time()
    loaded = 0
    skipped = 0

    try:
        # Create staging table
        cur.execute("""
            CREATE TEMP TABLE _staging_gbif_occ (
                gbif_id BIGINT,
                species_id INTEGER,
                latitude DECIMAL(10,6),
                longitude DECIMAL(10,6),
                coordinate_uncertainty_m INTEGER,
                year INTEGER,
                country_code VARCHAR(2)
            )
        """)
        conn.commit()

        # Process in chunks
        df = table.to_pandas()
        n_chunks = (len(df) + chunk_size - 1) // chunk_size

        for chunk_idx in range(n_chunks):
            chunk_start = chunk_idx * chunk_size
            chunk_end = min((chunk_idx + 1) * chunk_size, len(df))
            chunk = df.iloc[chunk_start:chunk_end]

            # Truncate staging
            cur.execute("TRUNCATE _staging_gbif_occ")

            # COPY into staging using StringIO buffer
            buf = io.StringIO()
            writer = csv.writer(buf, delimiter='\t')
            for _, row in chunk.iterrows():
                writer.writerow([
                    int(row['gbifid']) if not pd.isna(row['gbifid']) else r'\N',
                    int(row['species_id']),
                    round(float(row['latitude']), 6),
                    round(float(row['longitude']), 6),
                    int(row['uncertainty_m']) if not pd.isna(row['uncertainty_m']) else r'\N',
                    int(row['year']) if not pd.isna(row['year']) else r'\N',
                    row['country_code'] if not pd.isna(row['country_code']) else r'\N',
                ])
            buf.seek(0)
            cur.copy_from(buf, '_staging_gbif_occ', sep='\t', null=r'\N')

            # Insert from staging with conflict handling
            cur.execute("""
                INSERT INTO gbif_occurrences (
                    gbif_id, species_id, latitude, longitude,
                    coordinate_uncertainty_m, year, country_code
                )
                SELECT
                    gbif_id, species_id, latitude, longitude,
                    coordinate_uncertainty_m, year, country_code
                FROM _staging_gbif_occ
                ON CONFLICT (gbif_id) DO NOTHING
            """)

            chunk_loaded = cur.rowcount
            loaded += chunk_loaded
            skipped += len(chunk) - chunk_loaded
            conn.commit()

            elapsed = time.time() - start_time
            rate = loaded / elapsed if elapsed > 0 else 0
            logger.info(
                f"  Chunk {chunk_idx + 1}/{n_chunks}: "
                f"{loaded:,} loaded, {skipped:,} skipped "
                f"({rate:,.0f} rows/s)"
            )

    finally:
        cur.close()
        conn.close()

    elapsed = time.time() - start_time
    logger.info(
        f"Phase 3 DONE: {loaded:,} new rows loaded, "
        f"{skipped:,} duplicates skipped "
        f"in {elapsed/60:.1f} minutes"
    )
    return loaded


# ============================================================
# Phase 4: Extract climate at occurrence points
# ============================================================

def phase_climate_extraction(db_url=None, batch_size=5000, use_unique_coords=True):
    """
    Extract WorldClim climate data at each occurrence point.

    Optimization: Extract climate for unique (lat, lon) pairs first,
    then UPDATE occurrences by joining back. Many occurrences share
    coordinates, reducing ST_Value calls by 60-80%.

    Resumable: WHERE bio1 IS NULL processes only unextracted points.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    engine = get_engine(db_url)

    # Count pending occurrences
    with Session(engine) as session:
        total_pending = session.execute(text(
            "SELECT COUNT(*) FROM gbif_occurrences WHERE bio1 IS NULL"
        )).scalar()

        total_all = session.execute(text(
            "SELECT COUNT(*) FROM gbif_occurrences"
        )).scalar()

    if total_pending == 0:
        logger.info("Phase 4: All occurrences already have climate data.")
        return 0

    logger.info(
        f"Phase 4: Extracting climate for {total_pending:,} occurrences "
        f"(of {total_all:,} total)"
    )

    if use_unique_coords:
        return _climate_via_unique_coords(engine, batch_size)
    else:
        return _climate_direct_update(engine, batch_size)


def _climate_via_unique_coords(engine, batch_size):
    """
    Extract climate for unique coordinates first, then join back.

    This is much faster when many occurrences share coordinates.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    start_time = time.time()

    with Session(engine) as session:
        # Count unique coordinates pending
        n_unique = session.execute(text("""
            SELECT COUNT(DISTINCT (
                ROUND(latitude::numeric, 4),
                ROUND(longitude::numeric, 4)
            ))
            FROM gbif_occurrences
            WHERE bio1 IS NULL
        """)).scalar()

        logger.info(f"  Unique coordinate pairs to process: {n_unique:,}")

        # Create temp table for unique coords with climate
        session.execute(text("""
            CREATE TEMP TABLE IF NOT EXISTS _tmp_coord_climate (
                lat_round DECIMAL(10,4),
                lon_round DECIMAL(10,4),
                bio1 DECIMAL(6,2),
                bio5 DECIMAL(6,2),
                bio6 DECIMAL(6,2),
                bio7 DECIMAL(6,2),
                bio12 DECIMAL(8,2),
                bio15 DECIMAL(6,2),
                PRIMARY KEY (lat_round, lon_round)
            )
        """))
        session.commit()

        # Check how many unique coords already have climate
        existing_coords = session.execute(text(
            "SELECT COUNT(*) FROM _tmp_coord_climate"
        )).scalar()

        if existing_coords > 0:
            logger.info(f"  Resuming: {existing_coords:,} coords already extracted")

    processed = 0
    batch_num = 0

    while True:
        batch_start = time.time()

        with Session(engine) as session:
            # Get next batch of unique coordinates not yet in temp table
            result = session.execute(text("""
                SELECT DISTINCT
                    ROUND(go.latitude::numeric, 4) AS lat_round,
                    ROUND(go.longitude::numeric, 4) AS lon_round
                FROM gbif_occurrences go
                WHERE go.bio1 IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM _tmp_coord_climate tc
                      WHERE tc.lat_round = ROUND(go.latitude::numeric, 4)
                        AND tc.lon_round = ROUND(go.longitude::numeric, 4)
                  )
                LIMIT :batch_size
            """), {'batch_size': batch_size})

            coords = result.fetchall()

            if not coords:
                break

            # Extract climate for this batch using get_climate_json_at_point
            extracted = 0
            for lat_round, lon_round in coords:
                try:
                    climate = session.execute(
                        text("SELECT get_climate_json_at_point(:lat, :lon) AS cj"),
                        {'lat': float(lat_round), 'lon': float(lon_round)}
                    ).fetchone()

                    if climate and climate.cj:
                        cj = climate.cj
                        session.execute(text("""
                            INSERT INTO _tmp_coord_climate
                            (lat_round, lon_round, bio1, bio5, bio6, bio7, bio12, bio15)
                            VALUES (:lat, :lon, :bio1, :bio5, :bio6, :bio7, :bio12, :bio15)
                            ON CONFLICT (lat_round, lon_round) DO NOTHING
                        """), {
                            'lat': float(lat_round),
                            'lon': float(lon_round),
                            'bio1': cj.get('bio1'),
                            'bio5': cj.get('bio5'),
                            'bio6': cj.get('bio6'),
                            'bio7': cj.get('bio7'),
                            'bio12': cj.get('bio12'),
                            'bio15': cj.get('bio15'),
                        })
                        extracted += 1
                    else:
                        # Insert with NULLs so this coord is not re-fetched
                        session.execute(text("""
                            INSERT INTO _tmp_coord_climate
                            (lat_round, lon_round)
                            VALUES (:lat, :lon)
                            ON CONFLICT (lat_round, lon_round) DO NOTHING
                        """), {
                            'lat': float(lat_round),
                            'lon': float(lon_round),
                        })
                except Exception as e:
                    logger.debug(f"Climate error at ({lat_round},{lon_round}): {e}")

            session.commit()
            processed += len(coords)
            batch_num += 1

            batch_elapsed = time.time() - batch_start
            total_elapsed = time.time() - start_time
            rate = processed / total_elapsed if total_elapsed > 0 else 0
            remaining = (n_unique - processed) / rate if rate > 0 else 0

            logger.info(
                f"  Batch {batch_num}: {processed:,}/{n_unique:,} coords "
                f"({extracted} with climate) "
                f"[{rate:.0f}/s, ~{remaining/3600:.1f}h remaining]"
            )

    # Now apply climate from unique coords back to occurrences
    logger.info("  Applying climate to occurrences via coordinate join...")

    with Session(engine) as session:
        updated = session.execute(text("""
            UPDATE gbif_occurrences go
            SET
                bio1 = tc.bio1,
                bio5 = tc.bio5,
                bio6 = tc.bio6,
                bio7 = tc.bio7,
                bio12 = tc.bio12,
                bio15 = tc.bio15
            FROM _tmp_coord_climate tc
            WHERE ROUND(go.latitude::numeric, 4) = tc.lat_round
              AND ROUND(go.longitude::numeric, 4) = tc.lon_round
              AND go.bio1 IS NULL
              AND tc.bio1 IS NOT NULL
        """))

        rows_updated = updated.rowcount
        session.commit()

        # Clean up temp table
        session.execute(text("DROP TABLE IF EXISTS _tmp_coord_climate"))
        session.commit()

    elapsed = time.time() - start_time
    logger.info(
        f"Phase 4 DONE: {processed:,} unique coords processed, "
        f"{rows_updated:,} occurrences updated "
        f"in {elapsed/60:.1f} minutes"
    )
    return rows_updated


def _climate_direct_update(engine, batch_size):
    """
    Fallback: Direct UPDATE using get_climate_json_at_point per occurrence.
    Slower but simpler.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    start_time = time.time()
    processed = 0
    batch_num = 0

    while True:
        with Session(engine) as session:
            # Get batch of IDs without climate
            result = session.execute(text("""
                SELECT id, latitude, longitude
                FROM gbif_occurrences
                WHERE bio1 IS NULL
                ORDER BY id
                LIMIT :batch_size
            """), {'batch_size': batch_size})

            rows = result.fetchall()
            if not rows:
                break

            for occ_id, lat, lon in rows:
                try:
                    climate = session.execute(
                        text("SELECT get_climate_json_at_point(:lat, :lon) AS cj"),
                        {'lat': float(lat), 'lon': float(lon)}
                    ).fetchone()

                    if climate and climate.cj:
                        cj = climate.cj
                        session.execute(text("""
                            UPDATE gbif_occurrences
                            SET bio1 = :bio1, bio5 = :bio5, bio6 = :bio6,
                                bio7 = :bio7, bio12 = :bio12, bio15 = :bio15
                            WHERE id = :id
                        """), {
                            'id': occ_id,
                            'bio1': cj.get('bio1'),
                            'bio5': cj.get('bio5'),
                            'bio6': cj.get('bio6'),
                            'bio7': cj.get('bio7'),
                            'bio12': cj.get('bio12'),
                            'bio15': cj.get('bio15'),
                        })
                except Exception as e:
                    logger.debug(f"Climate error for occ {occ_id}: {e}")

            session.commit()
            processed += len(rows)
            batch_num += 1

            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            logger.info(
                f"  Batch {batch_num}: {processed:,} processed [{rate:.0f}/s]"
            )

    elapsed = time.time() - start_time
    logger.info(f"Phase 4 DONE: {processed:,} occurrences in {elapsed/60:.1f}m")
    return processed


# ============================================================
# Phase 5: Calculate climate envelopes from occurrences
# ============================================================

def phase_calculate_envelopes(db_url=None):
    """
    Calculate climate envelopes from occurrence data using SQL aggregation.

    Uses percentiles (P05, P95) for robust envelope bounds.
    Resumable: ON CONFLICT (species_id) DO UPDATE.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    engine = get_engine(db_url)

    logger.info("Phase 5: Calculating climate envelopes from occurrences...")

    with Session(engine) as session:
        # Count species with enough occurrences
        n_eligible = session.execute(text(f"""
            SELECT COUNT(DISTINCT species_id)
            FROM gbif_occurrences
            WHERE bio1 IS NOT NULL
            GROUP BY species_id
            HAVING COUNT(*) >= {MIN_OCCURRENCES_FOR_ENVELOPE}
        """)).fetchall()

        logger.info(f"  Species eligible for envelope: {len(n_eligible):,}")

        # Calculate and upsert envelopes
        result = session.execute(text(f"""
            INSERT INTO climate_envelope_gbif (
                species_id, temp_mean, temp_p05, temp_p95, temp_min, temp_max,
                cold_month_mean, cold_month_p05, warm_month_mean, warm_month_p95,
                precip_mean, precip_p05, precip_p95, precip_min, precip_max,
                precip_seasonality, n_occurrences, n_countries, year_range,
                envelope_quality
            )
            SELECT
                species_id,
                ROUND(AVG(bio1)::numeric, 2),
                ROUND(PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY bio1)::numeric, 2),
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY bio1)::numeric, 2),
                ROUND(MIN(bio1)::numeric, 2),
                ROUND(MAX(bio1)::numeric, 2),
                ROUND(AVG(bio6)::numeric, 2),
                ROUND(PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY bio6)::numeric, 2),
                ROUND(AVG(bio5)::numeric, 2),
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY bio5)::numeric, 2),
                ROUND(AVG(bio12)::numeric, 2),
                ROUND(PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY bio12)::numeric, 2),
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY bio12)::numeric, 2),
                ROUND(MIN(bio12)::numeric, 2),
                ROUND(MAX(bio12)::numeric, 2),
                ROUND(AVG(bio15)::numeric, 2),
                COUNT(*),
                COUNT(DISTINCT country_code),
                MIN(year)::text || '-' || MAX(year)::text,
                CASE
                    WHEN COUNT(*) >= 100 THEN 'high'
                    WHEN COUNT(*) >= 50  THEN 'medium'
                    ELSE 'low'
                END
            FROM gbif_occurrences
            WHERE bio1 IS NOT NULL
            GROUP BY species_id
            HAVING COUNT(*) >= {MIN_OCCURRENCES_FOR_ENVELOPE}
            ON CONFLICT (species_id) DO UPDATE SET
                temp_mean = EXCLUDED.temp_mean,
                temp_p05 = EXCLUDED.temp_p05,
                temp_p95 = EXCLUDED.temp_p95,
                temp_min = EXCLUDED.temp_min,
                temp_max = EXCLUDED.temp_max,
                cold_month_mean = EXCLUDED.cold_month_mean,
                cold_month_p05 = EXCLUDED.cold_month_p05,
                warm_month_mean = EXCLUDED.warm_month_mean,
                warm_month_p95 = EXCLUDED.warm_month_p95,
                precip_mean = EXCLUDED.precip_mean,
                precip_p05 = EXCLUDED.precip_p05,
                precip_p95 = EXCLUDED.precip_p95,
                precip_min = EXCLUDED.precip_min,
                precip_max = EXCLUDED.precip_max,
                precip_seasonality = EXCLUDED.precip_seasonality,
                n_occurrences = EXCLUDED.n_occurrences,
                n_countries = EXCLUDED.n_countries,
                year_range = EXCLUDED.year_range,
                envelope_quality = EXCLUDED.envelope_quality,
                updated_at = CURRENT_TIMESTAMP
        """))

        envelopes_created = result.rowcount
        session.commit()

        logger.info(f"  Created/updated {envelopes_created:,} envelopes")

        # Update analysis table for all species with new GBIF envelopes
        logger.info("  Updating envelope analysis...")
        session.execute(text("""
            SELECT update_envelope_analysis(species_id)
            FROM climate_envelope_gbif
            WHERE updated_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
        """))
        session.commit()

        # Report results
        quality_dist = session.execute(text("""
            SELECT envelope_quality, COUNT(*) as cnt
            FROM climate_envelope_gbif
            GROUP BY envelope_quality
            ORDER BY CASE envelope_quality
                WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END
        """)).fetchall()

        logger.info("  Envelope quality distribution:")
        for quality, count in quality_dist:
            logger.info(f"    {quality}: {count:,}")

    logger.info(f"Phase 5 DONE: {envelopes_created:,} envelopes created/updated")
    return envelopes_created


# ============================================================
# Phase 6: Map GBIF occurrences to ecoregions
# ============================================================

def phase_ecoregion_mapping(db_url=None, species_ids=None):
    """
    Spatial join: gbif_occurrences → ecoregions → species_ecoregions.

    For each species with GBIF occurrences, counts how many fall within each
    RESOLVE ecoregion polygon and upserts into species_ecoregions.

    Processes in batches of ECOREGION_BATCH_SIZE species to keep queries fast.
    Only processes species that have GBIF occurrences but NO existing ecoregion links.
    Preserves existing TreeGoer data (ON CONFLICT updates n_observations).

    Args:
        species_ids: If provided, only process these species IDs.
                     Otherwise, auto-detect species with GBIF data but no ecoregion links.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    engine = get_engine(db_url)

    logger.info("Phase 6: Mapping GBIF occurrences to ecoregions...")

    with Session(engine) as session:
        # Find species with GBIF occurrences but no ecoregion links
        if species_ids:
            # Filter to only those without ecoregion data
            result = session.execute(text("""
                SELECT DISTINCT go.species_id
                FROM gbif_occurrences go
                LEFT JOIN species_ecoregions se ON go.species_id = se.species_id
                WHERE go.species_id = ANY(:ids)
                  AND se.species_id IS NULL
                ORDER BY go.species_id
            """), {'ids': species_ids})
        else:
            result = session.execute(text("""
                SELECT DISTINCT go.species_id
                FROM gbif_occurrences go
                LEFT JOIN species_ecoregions se ON go.species_id = se.species_id
                WHERE se.species_id IS NULL
                ORDER BY go.species_id
            """))

        pending_ids = [r[0] for r in result.fetchall()]

    if not pending_ids:
        logger.info("Phase 6: All species with GBIF occurrences already have ecoregion data.")
        return 0

    logger.info(f"  Species to map: {len(pending_ids):,}")

    start_time = time.time()
    total_links = 0
    n_batches = (len(pending_ids) + ECOREGION_BATCH_SIZE - 1) // ECOREGION_BATCH_SIZE

    for batch_num in range(n_batches):
        batch_start = time.time()
        offset = batch_num * ECOREGION_BATCH_SIZE
        batch_ids = pending_ids[offset:offset + ECOREGION_BATCH_SIZE]

        with Session(engine) as session:
            result = session.execute(text("""
                INSERT INTO species_ecoregions (species_id, eco_id, n_observations)
                SELECT go.species_id, e.eco_id, COUNT(*)::int
                FROM gbif_occurrences go
                JOIN ecoregions e
                  ON ST_Contains(e.geom, ST_SetSRID(ST_Point(go.longitude, go.latitude), 4326))
                WHERE go.species_id = ANY(:ids)
                GROUP BY go.species_id, e.eco_id
                ON CONFLICT (species_id, eco_id)
                DO UPDATE SET n_observations = EXCLUDED.n_observations
            """), {'ids': batch_ids})

            batch_links = result.rowcount
            session.commit()

        total_links += batch_links
        batch_elapsed = time.time() - batch_start
        total_elapsed = time.time() - start_time
        remaining_batches = n_batches - (batch_num + 1)
        avg_batch_time = total_elapsed / (batch_num + 1)
        eta = remaining_batches * avg_batch_time

        logger.info(
            f"  Batch {batch_num + 1}/{n_batches}: "
            f"{len(batch_ids)} species → {batch_links} links "
            f"({batch_elapsed:.1f}s, ~{eta/60:.1f}m remaining)"
        )

    elapsed = time.time() - start_time
    logger.info(
        f"Phase 6 DONE: {total_links:,} species-ecoregion links created/updated "
        f"for {len(pending_ids):,} species in {elapsed/60:.1f} minutes"
    )
    return total_links


# ============================================================
# Status / verification
# ============================================================

def show_status(db_url=None):
    """Show current status of the GBIF S3 loading pipeline."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    engine = get_engine(db_url)

    print("\n=== GBIF S3 Loader Status ===\n")

    # Local files
    keys_path = DATA_DIR / 'species_keys.parquet'
    extract_path = DATA_DIR / 'occurrences_extract.parquet'

    if keys_path.exists():
        import pyarrow.parquet as pq
        table = pq.read_table(str(keys_path))
        print(f"  species_keys.parquet: {len(table):,} species")
    else:
        print("  species_keys.parquet: NOT FOUND")

    if extract_path.exists():
        import pyarrow.parquet as pq
        meta = pq.read_metadata(str(extract_path))
        print(f"  occurrences_extract.parquet: {meta.num_rows:,} rows")
    else:
        print("  occurrences_extract.parquet: NOT FOUND")

    print()

    # Database status
    with Session(engine) as session:
        # Species needing envelopes
        pending = session.execute(text("""
            SELECT COUNT(*)
            FROM species s
            JOIN species_unified su ON s.id = su.species_id
            LEFT JOIN climate_envelope_gbif ceg ON s.id = ceg.species_id
            WHERE s.gbif_taxon_key IS NOT NULL
              AND ceg.species_id IS NULL
              AND su.growth_form IS NOT NULL
        """)).scalar()
        print(f"  Species pending GBIF envelope: {pending:,}")

        # Occurrences
        total_occ = session.execute(text(
            "SELECT COUNT(*) FROM gbif_occurrences"
        )).scalar()
        with_climate = session.execute(text(
            "SELECT COUNT(*) FROM gbif_occurrences WHERE bio1 IS NOT NULL"
        )).scalar()
        without_climate = total_occ - with_climate
        print(f"  GBIF occurrences total: {total_occ:,}")
        print(f"    With climate: {with_climate:,}")
        print(f"    Without climate: {without_climate:,}")

        # Envelopes
        n_envelopes = session.execute(text(
            "SELECT COUNT(*) FROM climate_envelope_gbif"
        )).scalar()
        print(f"  GBIF envelopes: {n_envelopes:,}")

        # Quality distribution
        quality = session.execute(text("""
            SELECT envelope_quality, COUNT(*)
            FROM climate_envelope_gbif
            GROUP BY envelope_quality
            ORDER BY CASE envelope_quality
                WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END
        """)).fetchall()

        if quality:
            for q, cnt in quality:
                print(f"    {q}: {cnt:,}")

        # Coverage by growth form (envelopes)
        print("\n  Envelope coverage by growth form:")
        coverage = session.execute(text("""
            SELECT
                su.growth_form,
                COUNT(DISTINCT su.species_id) as total,
                COUNT(DISTINCT ceg.species_id) as with_gbif,
                ROUND(100.0 * COUNT(DISTINCT ceg.species_id) /
                      NULLIF(COUNT(DISTINCT su.species_id), 0), 1) as pct
            FROM species_unified su
            LEFT JOIN climate_envelope_gbif ceg ON su.species_id = ceg.species_id
            WHERE su.growth_form IS NOT NULL
            GROUP BY su.growth_form
            ORDER BY total DESC
        """)).fetchall()

        for gf, total, with_gbif, pct in coverage:
            print(f"    {gf}: {with_gbif:,}/{total:,} ({pct}%)")

        # Ecoregion coverage
        n_eco_species = session.execute(text(
            "SELECT COUNT(DISTINCT species_id) FROM species_ecoregions"
        )).scalar()
        n_eco_links = session.execute(text(
            "SELECT COUNT(*) FROM species_ecoregions"
        )).scalar()
        print(f"\n  Species with ecoregion data: {n_eco_species:,}")
        print(f"  Total species-ecoregion links: {n_eco_links:,}")

        # Ecoregion coverage by growth form
        print("\n  Ecoregion coverage by growth form:")
        eco_coverage = session.execute(text("""
            SELECT
                su.growth_form,
                COUNT(DISTINCT su.species_id) as total,
                COUNT(DISTINCT se.species_id) as with_eco,
                ROUND(100.0 * COUNT(DISTINCT se.species_id) /
                      NULLIF(COUNT(DISTINCT su.species_id), 0), 1) as pct
            FROM species_unified su
            LEFT JOIN species_ecoregions se ON su.species_id = se.species_id
            WHERE su.growth_form IS NOT NULL
            GROUP BY su.growth_form
            ORDER BY total DESC
        """)).fetchall()

        for gf, total, with_eco, pct in eco_coverage:
            print(f"    {gf}: {with_eco:,}/{total:,} ({pct}%)")

    print()


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='GBIF S3 Parquet Loader via DuckDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phases:
  export    Export species keys from PostgreSQL to Parquet
  extract   Query GBIF S3 Parquet via DuckDB
  load      Load extracted occurrences into PostgreSQL
  climate   Extract WorldClim climate at occurrence points
  envelope  Calculate climate envelopes from occurrence data
  ecoregion Spatial join occurrences to ecoregion polygons

Examples:
  %(prog)s                                             # Run all phases
  %(prog)s --phase extract                             # Run extraction only
  %(prog)s --phase climate --batch-size 10000
  %(prog)s --growth-forms graminoid,bamboo --force     # Filter by growth form
  %(prog)s --phase ecoregion                           # Run ecoregion mapping only
  %(prog)s --status                                    # Show pipeline status
        """
    )

    parser.add_argument(
        '--phase',
        choices=['export', 'extract', 'load', 'climate', 'envelope', 'ecoregion'],
        help='Run a specific phase (default: all phases sequentially)'
    )

    parser.add_argument(
        '--growth-forms',
        default=None,
        help='Comma-separated growth forms to filter species (e.g., graminoid,bamboo). '
             f'Valid values: {", ".join(VALID_GROWTH_FORMS)}'
    )

    parser.add_argument(
        '--snapshot',
        default=None,
        help='GBIF snapshot date (e.g., 2024-10-01). Default: 2024-10-01'
    )

    parser.add_argument(
        '--db-url',
        default=None,
        help='Database URL (default: from DATABASE_URL env var)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=5000,
        help='Batch size for climate extraction (default: 5000)'
    )

    parser.add_argument(
        '--memory-limit',
        default='4GB',
        help='DuckDB memory limit (default: 4GB)'
    )

    parser.add_argument(
        '--duckdb-batch-size',
        type=int,
        default=None,
        help='Process species in DuckDB batches (for OOM prevention)'
    )

    parser.add_argument(
        '--max-files',
        type=int,
        default=None,
        help='Limit number of S3 Parquet files to read (~100MB each). '
             'E.g., --max-files 100 reads ~10GB instead of ~200GB'
    )

    parser.add_argument(
        '--start-file',
        type=int,
        default=0,
        help='Starting file index for S3 Parquet files (default: 0). '
             'Use with --max-files to scan different ranges, e.g., '
             '--start-file 1000 --max-files 1000 scans files 1000-1999'
    )

    parser.add_argument(
        '--batch-mode',
        action='store_true',
        help='Process species in batches of --species-limit, looping until all done. '
             'Each batch runs all 6 phases before starting next batch.'
    )

    parser.add_argument(
        '--species-limit',
        type=int,
        default=11500,
        help='Max species per batch in batch mode (default: 11500 = ~5%% of total)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-run even if output files exist'
    )

    parser.add_argument(
        '--no-unique-coords',
        action='store_true',
        help='Disable unique-coordinate optimization for climate extraction'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Show pipeline status and exit'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview actions without executing'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def run_single_pipeline(args, db_url, species_limit=None):
    """Run a single pass of the pipeline (all phases or specified phase)."""
    start_time = time.time()
    phases = []

    # Parse and validate growth forms
    growth_forms = None
    if args.growth_forms:
        growth_forms = [gf.strip() for gf in args.growth_forms.split(',')]
        invalid = [gf for gf in growth_forms if gf not in VALID_GROWTH_FORMS]
        if invalid:
            logger.error(
                f"Invalid growth forms: {', '.join(invalid)}. "
                f"Valid values: {', '.join(VALID_GROWTH_FORMS)}"
            )
            sys.exit(1)
        logger.info(f"Growth form filter: {', '.join(growth_forms)}")

    if args.phase:
        phases = [args.phase]
    else:
        phases = ['export', 'extract', 'load', 'climate', 'envelope', 'ecoregion']

    logger.info(f"Running phases: {', '.join(phases)}")

    results = {}

    for phase in phases:
        phase_start = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"PHASE: {phase.upper()}")
        logger.info(f"{'='*60}")

        if args.dry_run:
            logger.info(f"  [DRY RUN] Would execute phase: {phase}")
            continue

        try:
            if phase == 'export':
                # In batch mode, always force export and use limit
                force = args.force or (species_limit is not None)
                results[phase] = phase_export_keys(
                    db_url, force=force, limit=species_limit,
                    growth_forms=growth_forms,
                )

            elif phase == 'extract':
                results[phase] = phase_extract_s3(
                    snapshot_date=args.snapshot,
                    db_url=db_url,
                    force=True,  # Always force in batch mode since species changed
                    memory_limit=args.memory_limit,
                    batch_size=args.duckdb_batch_size,
                    max_files=args.max_files,
                    start_file=args.start_file,
                )

            elif phase == 'load':
                results[phase] = phase_load_postgres(db_url, force=args.force)

            elif phase == 'climate':
                results[phase] = phase_climate_extraction(
                    db_url,
                    batch_size=args.batch_size,
                    use_unique_coords=not args.no_unique_coords,
                )

            elif phase == 'envelope':
                results[phase] = phase_calculate_envelopes(db_url)

            elif phase == 'ecoregion':
                # Read species_ids from the exported keys file if available
                keys_path = DATA_DIR / 'species_keys.parquet'
                eco_species_ids = None
                if keys_path.exists():
                    import pyarrow.parquet as pq
                    table = pq.read_table(str(keys_path), columns=['species_id'])
                    eco_species_ids = table.column('species_id').to_pylist()
                results[phase] = phase_ecoregion_mapping(db_url, species_ids=eco_species_ids)

            phase_elapsed = time.time() - phase_start
            logger.info(f"Phase {phase} completed in {phase_elapsed/60:.1f} minutes")

        except Exception as e:
            logger.error(f"Phase {phase} FAILED: {e}", exc_info=True)
            results[phase] = f"FAILED: {e}"
            if phase in ('export', 'extract', 'load'):
                logger.error("Aborting: subsequent phases depend on this one.")
                break

    total_elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"PIPELINE PASS COMPLETE in {total_elapsed/60:.1f} minutes")
    logger.info(f"{'='*60}")

    for phase, result in results.items():
        status = f"{result:,}" if isinstance(result, int) else str(result)
        logger.info(f"  {phase}: {status}")

    return results


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    db_url = args.db_url or os.environ.get('DATABASE_URL', '')

    if args.status:
        show_status(db_url or None)
        return

    if not db_url:
        logger.error(
            "DATABASE_URL not set. "
            "Set it with: export DATABASE_URL=postgresql://user:pass@host/diversiplant"
        )
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN - no changes will be made")

    if args.batch_mode:
        # Batch mode: loop until no more species to process
        logger.info(f"\n{'#'*60}")
        logger.info(f"BATCH MODE: Processing species in batches of {args.species_limit}")
        logger.info(f"{'#'*60}")

        batch_num = 0
        total_species = 0
        total_envelopes = 0
        batch_start_time = time.time()

        while True:
            batch_num += 1
            logger.info(f"\n{'#'*60}")
            logger.info(f"BATCH {batch_num}: Starting...")
            logger.info(f"{'#'*60}")

            results = run_single_pipeline(args, db_url, species_limit=args.species_limit)

            # Check if export returned 0 (no more species)
            export_count = results.get('export', 0)
            if isinstance(export_count, str) or export_count == 0:
                logger.info(f"\nBatch mode complete: No more species to process.")
                break

            total_species += export_count
            envelope_count = results.get('envelope', 0)
            if isinstance(envelope_count, int):
                total_envelopes += envelope_count

            # Check for failures
            if any(isinstance(v, str) and 'FAILED' in v for v in results.values()):
                logger.error("Batch failed, stopping batch mode.")
                break

            logger.info(f"\nBatch {batch_num} complete. Running total: {total_species:,} species, {total_envelopes:,} envelopes")

        total_time = time.time() - batch_start_time
        logger.info(f"\n{'#'*60}")
        logger.info(f"BATCH MODE COMPLETE")
        logger.info(f"{'#'*60}")
        logger.info(f"  Total batches: {batch_num}")
        logger.info(f"  Total species processed: {total_species:,}")
        logger.info(f"  Total envelopes created: {total_envelopes:,}")
        logger.info(f"  Total time: {total_time/3600:.1f} hours")

        show_status(db_url)

    else:
        # Single run mode (original behavior)
        results = run_single_pipeline(args, db_url, species_limit=None)

        # Show final status
        if not args.dry_run and 'envelope' in (args.phase or 'envelope'):
            show_status(db_url)


if __name__ == '__main__':
    main()
