-- Populate Ecoregion-derived climate envelopes (TreeGOER data)
-- Uses species_ecoregions + ecoregion centroids + WorldClim rasters
--
-- OPTIMIZED VERSION: Uses get_climate_json_at_point() which returns all bio
-- variables as JSONB in a single optimized call.
--
-- This script calculates climate envelopes for tree species using TreeGOER's
-- ecoregion occurrence data combined with WorldClim climate at ecoregion centroids.

\echo 'Populating Ecoregion climate envelopes...'
\echo 'Using species_ecoregions + ecoregion centroids + WorldClim (JSON method)'

-- Count before
SELECT COUNT(*) as eco_envelopes_before FROM climate_envelope_ecoregion;

-- Step 1: Create temp table with ecoregion centroids + climate via JSON function
\echo 'Extracting climate at ecoregion centroids (JSON method)...'

DROP TABLE IF EXISTS _tmp_ecoregion_climate;

CREATE TEMP TABLE _tmp_ecoregion_climate AS
SELECT
    e.eco_id,
    e.eco_name,
    climate_json,
    (climate_json->>'bio1')::decimal as bio1,
    (climate_json->>'bio5')::decimal as bio5,
    (climate_json->>'bio6')::decimal as bio6,
    (climate_json->>'bio7')::decimal as bio7,
    (climate_json->>'bio12')::decimal as bio12,
    (climate_json->>'bio15')::decimal as bio15
FROM (
    SELECT
        e.eco_id,
        e.eco_name,
        get_climate_json_at_point(
            ST_Y(ST_Centroid(e.geom)),
            ST_X(ST_Centroid(e.geom))
        ) as climate_json
    FROM ecoregions e
    WHERE e.geom IS NOT NULL
) e;

-- Check how many ecoregions have climate
\echo 'Ecoregion climate extraction results:'
SELECT
    COUNT(*) as total_ecoregions,
    COUNT(*) FILTER (WHERE bio1 IS NOT NULL) as with_climate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE bio1 IS NOT NULL) / NULLIF(COUNT(*), 0), 1) as coverage_pct
FROM _tmp_ecoregion_climate;

-- Step 2: Calculate envelopes from species_ecoregions + ecoregion climate
\echo 'Calculating envelopes from ecoregion data...'

INSERT INTO climate_envelope_ecoregion (
    species_id, temp_mean, temp_min, temp_max, temp_range,
    cold_month_min, warm_month_max, precip_mean, precip_min, precip_max,
    precip_seasonality, n_ecoregions, envelope_quality
)
SELECT
    se.species_id,
    ROUND(AVG(ec.bio1)::numeric, 2) as temp_mean,
    ROUND(MIN(ec.bio1)::numeric, 2) as temp_min,
    ROUND(MAX(ec.bio1)::numeric, 2) as temp_max,
    ROUND(AVG(ec.bio7)::numeric, 2) as temp_range,
    ROUND(MIN(ec.bio6)::numeric, 2) as cold_month_min,
    ROUND(MAX(ec.bio5)::numeric, 2) as warm_month_max,
    ROUND(AVG(ec.bio12)::numeric, 2) as precip_mean,
    ROUND(MIN(ec.bio12)::numeric, 2) as precip_min,
    ROUND(MAX(ec.bio12)::numeric, 2) as precip_max,
    ROUND(AVG(ec.bio15)::numeric, 2) as precip_seasonality,
    COUNT(DISTINCT se.eco_id) as n_ecoregions,
    CASE
        WHEN COUNT(DISTINCT se.eco_id) >= 10 THEN 'high'
        WHEN COUNT(DISTINCT se.eco_id) >= 3 THEN 'medium'
        ELSE 'low'
    END as envelope_quality
FROM species_ecoregions se
JOIN _tmp_ecoregion_climate ec ON se.eco_id = ec.eco_id
WHERE ec.bio1 IS NOT NULL
GROUP BY se.species_id
HAVING COUNT(DISTINCT se.eco_id) >= 1
ON CONFLICT (species_id) DO UPDATE SET
    temp_mean = EXCLUDED.temp_mean,
    temp_min = EXCLUDED.temp_min,
    temp_max = EXCLUDED.temp_max,
    temp_range = EXCLUDED.temp_range,
    cold_month_min = EXCLUDED.cold_month_min,
    warm_month_max = EXCLUDED.warm_month_max,
    precip_mean = EXCLUDED.precip_mean,
    precip_min = EXCLUDED.precip_min,
    precip_max = EXCLUDED.precip_max,
    precip_seasonality = EXCLUDED.precip_seasonality,
    n_ecoregions = EXCLUDED.n_ecoregions,
    envelope_quality = EXCLUDED.envelope_quality,
    updated_at = CURRENT_TIMESTAMP;

-- Cleanup
DROP TABLE IF EXISTS _tmp_ecoregion_climate;

-- Results
SELECT COUNT(*) as eco_envelopes_after FROM climate_envelope_ecoregion;

\echo 'Ecoregion envelope quality distribution:'
SELECT
    envelope_quality,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM climate_envelope_ecoregion
GROUP BY envelope_quality
ORDER BY CASE envelope_quality WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END;

-- Note: Ecoregion envelopes are only for trees (TreeGOER data)
\echo 'Note: Ecoregion envelopes cover only tree species from TreeGOER'
SELECT
    COUNT(DISTINCT cee.species_id) as species_with_ecoregion_envelope,
    COUNT(DISTINCT su.species_id) FILTER (WHERE su.is_tree = TRUE) as total_tree_species,
    ROUND(100.0 * COUNT(DISTINCT cee.species_id) /
          NULLIF(COUNT(DISTINCT su.species_id) FILTER (WHERE su.is_tree = TRUE), 0), 1) as tree_coverage_pct
FROM species_unified su
LEFT JOIN climate_envelope_ecoregion cee ON su.species_id = cee.species_id;

\echo 'Ecoregion envelope population complete!'
