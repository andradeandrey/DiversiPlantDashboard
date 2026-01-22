#!/usr/bin/env python3
"""
Populate tdwg_climate table using raster data already loaded in PostGIS.

Uses ST_SummaryStats to calculate zonal statistics for each TDWG Level 3 region
from the worldclim_raster table.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'user': os.getenv('DB_USER', os.getenv('POSTGRES_USER', 'diversiplant')),
    'password': os.getenv('DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', 'diversiplant_dev')),
    'dbname': os.getenv('DB_NAME', os.getenv('POSTGRES_DB', 'diversiplant')),
}


def classify_koppen(mean_temp, annual_precip, max_temp, min_temp):
    """Simplified Köppen climate classification."""
    if max_temp is not None and max_temp < 10:
        return 'EF' if max_temp < 0 else 'ET'

    threshold = mean_temp * 20 + 280
    if annual_precip < threshold:
        if annual_precip < threshold / 2:
            return 'BWh' if mean_temp >= 18 else 'BWk'
        return 'BSh' if mean_temp >= 18 else 'BSk'

    if min_temp >= 18:
        return 'Af' if annual_precip >= 2500 else 'Am'

    if min_temp < -3:
        return 'Dfd' if min_temp < -38 else 'Dfb'

    if min_temp >= -3 and min_temp < 18:
        return 'Cfa' if annual_precip > 1500 else 'Cfb'

    return 'Cf'


def classify_whittaker(temp, precip):
    """Classify biome using Whittaker diagram logic."""
    if temp < -5:
        return 'Tundra'
    elif temp < 5:
        return 'Cold Desert' if precip < 250 else 'Boreal Forest'
    elif temp < 15:
        if precip < 300:
            return 'Cold Desert'
        elif precip < 750:
            return 'Temperate Grassland'
        else:
            return 'Temperate Forest'
    elif temp < 20:
        if precip < 300:
            return 'Hot Desert'
        elif precip < 750:
            return 'Subtropical Grassland'
        elif precip < 1500:
            return 'Subtropical Forest'
        else:
            return 'Temperate Rainforest'
    else:
        if precip < 250:
            return 'Hot Desert'
        elif precip < 750:
            return 'Tropical Savanna'
        elif precip < 1500:
            return 'Tropical Seasonal Forest'
        else:
            return 'Tropical Rainforest'


def main():
    print("Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check if we have raster data
    cursor.execute("SELECT COUNT(DISTINCT bio_var) FROM worldclim_raster")
    n_vars = cursor.fetchone()['count']
    print(f"Found {n_vars} bio variables in worldclim_raster")

    if n_vars == 0:
        print("ERROR: No raster data found. Run load_wc2_raster.py first.")
        sys.exit(1)

    # Get all TDWG Level 3 regions
    cursor.execute("""
        SELECT level3_code, level3_name
        FROM tdwg_level3
        WHERE geom IS NOT NULL
        ORDER BY level3_code
    """)
    regions = cursor.fetchall()
    print(f"Found {len(regions)} TDWG Level 3 regions")

    processed = 0
    errors = 0

    for region in regions:
        tdwg_code = region['level3_code']

        try:
            # Calculate zonal statistics for all bio variables using ST_SummaryStats
            # This clips the raster to the TDWG geometry and calculates stats
            cursor.execute("""
                WITH clipped AS (
                    SELECT
                        wr.bio_var,
                        ST_SummaryStats(
                            ST_Clip(wr.rast, t.geom, true),
                            1, true
                        ) as stats
                    FROM worldclim_raster wr
                    JOIN tdwg_level3 t ON ST_Intersects(wr.rast, t.geom)
                    WHERE t.level3_code = %s
                ),
                aggregated AS (
                    SELECT
                        bio_var,
                        SUM((stats).count) as pixel_count,
                        SUM((stats).sum) / NULLIF(SUM((stats).count), 0) as mean_val,
                        MIN((stats).min) as min_val,
                        MAX((stats).max) as max_val
                    FROM clipped
                    WHERE (stats).count > 0
                    GROUP BY bio_var
                )
                SELECT * FROM aggregated ORDER BY bio_var
            """, (tdwg_code,))

            stats = cursor.fetchall()

            if not stats:
                print(f"  {tdwg_code}: No data (outside raster coverage)")
                continue

            # Build climate data dict
            climate_data = {'tdwg_code': tdwg_code, 'resolution': '10m'}
            pixel_count = 0

            for row in stats:
                bio_var = row['bio_var']
                mean_val = row['mean_val']
                min_val = row['min_val']
                max_val = row['max_val']
                pixel_count = max(pixel_count, row['pixel_count'] or 0)

                # Store mean for all bio vars
                if mean_val is not None:
                    climate_data[f'{bio_var}_mean'] = float(mean_val)

                # Only store min/max for bio1 and bio12 (as per table schema)
                if bio_var in ('bio1', 'bio12'):
                    if min_val is not None:
                        climate_data[f'{bio_var}_min'] = float(min_val)
                    if max_val is not None:
                        climate_data[f'{bio_var}_max'] = float(max_val)

            climate_data['pixel_count'] = int(pixel_count)

            # Add classifications
            bio1 = climate_data.get('bio1_mean')
            bio5 = climate_data.get('bio5_mean')
            bio6 = climate_data.get('bio6_mean')
            bio12 = climate_data.get('bio12_mean')

            if bio1 is not None and bio12 is not None:
                climate_data['whittaker_biome'] = classify_whittaker(bio1, bio12)

                if bio6 is not None:
                    climate_data['koppen_zone'] = classify_koppen(bio1, bio12, bio5, bio6)

                if bio1 > -10:
                    climate_data['aridity_index'] = bio12 / (bio1 + 10) * 10

            # Insert/update into tdwg_climate
            columns = list(climate_data.keys())
            values = [climate_data[k] for k in columns]
            placeholders = ', '.join(['%s'] * len(columns))
            col_names = ', '.join(columns)
            update_clause = ', '.join([f'{col} = EXCLUDED.{col}' for col in columns if col != 'tdwg_code'])

            cursor.execute(f"""
                INSERT INTO tdwg_climate ({col_names})
                VALUES ({placeholders})
                ON CONFLICT (tdwg_code) DO UPDATE SET
                {update_clause},
                updated_at = CURRENT_TIMESTAMP
            """, values)

            processed += 1

            if processed % 50 == 0:
                conn.commit()
                print(f"  Processed {processed}/{len(regions)} regions...")

        except Exception as e:
            print(f"  ERROR {tdwg_code}: {e}")
            errors += 1
            conn.rollback()

    conn.commit()

    print(f"\n{'='*50}")
    print(f"Completed: {processed} regions populated, {errors} errors")

    # Show summary
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(bio1_mean) as with_temp,
            COUNT(koppen_zone) as with_koppen,
            COUNT(whittaker_biome) as with_biome
        FROM tdwg_climate
    """)
    summary = cursor.fetchone()
    print(f"\nSummary:")
    print(f"  Total regions: {summary['total']}")
    print(f"  With temperature: {summary['with_temp']}")
    print(f"  With Köppen zone: {summary['with_koppen']}")
    print(f"  With Whittaker biome: {summary['with_biome']}")

    # Show sample Brazilian regions
    cursor.execute("""
        SELECT tdwg_code, bio1_mean, bio12_mean, koppen_zone, whittaker_biome
        FROM tdwg_climate
        WHERE tdwg_code LIKE 'BZ%'
        ORDER BY tdwg_code
    """)
    br_regions = cursor.fetchall()
    if br_regions:
        print(f"\nBrazilian regions:")
        for r in br_regions:
            print(f"  {r['tdwg_code']}: {r['bio1_mean']:.1f}°C, {r['bio12_mean']:.0f}mm, {r['koppen_zone']}, {r['whittaker_biome']}")

    conn.close()


if __name__ == '__main__':
    main()
