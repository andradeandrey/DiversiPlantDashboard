-- Populate WCVP-derived climate envelopes
-- Uses species_regions (WCVP distribution) + tdwg_climate

-- This script calculates climate envelopes for all species with WCVP distribution data
-- by aggregating climate statistics from their native TDWG regions.

\echo 'Populating WCVP climate envelopes...'
\echo 'Using species_regions + tdwg_climate'

-- Count before
SELECT COUNT(*) as wcvp_envelopes_before FROM climate_envelope_wcvp;

-- Insert/update envelopes
INSERT INTO climate_envelope_wcvp (
    species_id,
    temp_mean,
    temp_min,
    temp_max,
    temp_range,
    cold_month_min,
    warm_month_max,
    precip_mean,
    precip_min,
    precip_max,
    precip_seasonality,
    n_regions,
    envelope_quality
)
SELECT
    s.id,
    ROUND(AVG(c.bio1_mean)::numeric, 2) as temp_mean,
    ROUND(MIN(c.bio1_min)::numeric, 2) as temp_min,
    ROUND(MAX(c.bio1_max)::numeric, 2) as temp_max,
    ROUND(AVG(c.bio7_mean)::numeric, 2) as temp_range,
    ROUND(MIN(c.bio6_mean)::numeric, 2) as cold_month_min,
    ROUND(MAX(c.bio5_mean)::numeric, 2) as warm_month_max,
    ROUND(AVG(c.bio12_mean)::numeric, 2) as precip_mean,
    ROUND(MIN(c.bio12_min)::numeric, 2) as precip_min,
    ROUND(MAX(c.bio12_max)::numeric, 2) as precip_max,
    ROUND(AVG(c.bio15_mean)::numeric, 2) as precip_seasonality,
    COUNT(DISTINCT sr.tdwg_code) as n_regions,
    CASE
        WHEN COUNT(DISTINCT sr.tdwg_code) >= 5 THEN 'high'
        WHEN COUNT(DISTINCT sr.tdwg_code) >= 2 THEN 'medium'
        ELSE 'low'
    END as envelope_quality
FROM species s
JOIN species_regions sr ON s.id = sr.species_id AND sr.is_native = TRUE
JOIN tdwg_climate c ON sr.tdwg_code = c.tdwg_code
WHERE c.bio1_mean IS NOT NULL
GROUP BY s.id
HAVING COUNT(DISTINCT sr.tdwg_code) >= 1
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
    n_regions = EXCLUDED.n_regions,
    envelope_quality = EXCLUDED.envelope_quality,
    updated_at = CURRENT_TIMESTAMP;

-- Count after
SELECT COUNT(*) as wcvp_envelopes_after FROM climate_envelope_wcvp;

-- Show quality distribution
\echo 'WCVP envelope quality distribution:'
SELECT
    envelope_quality,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM climate_envelope_wcvp
GROUP BY envelope_quality
ORDER BY
    CASE envelope_quality
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
    END;

-- Show coverage by growth form
\echo 'WCVP envelope coverage by growth form:'
SELECT
    COALESCE(su.growth_form, 'unknown') as growth_form,
    COUNT(DISTINCT su.species_id) as total_species,
    COUNT(DISTINCT cew.species_id) as with_wcvp_envelope,
    ROUND(100.0 * COUNT(DISTINCT cew.species_id) / NULLIF(COUNT(DISTINCT su.species_id), 0), 1) as coverage_pct
FROM species_unified su
LEFT JOIN climate_envelope_wcvp cew ON su.species_id = cew.species_id
GROUP BY su.growth_form
ORDER BY total_species DESC;

\echo 'WCVP envelope population complete!'
