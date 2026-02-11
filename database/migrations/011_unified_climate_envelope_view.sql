-- Migration 011: Unified Climate Envelope View
--
-- Creates a view that combines climate envelopes from multiple sources
-- with intelligent prioritization:
-- 1. GBIF (highest priority - real occurrences)
-- 2. Ecoregion/TreeGOER (medium - specific to trees, ecoregion-based)
-- 3. WCVP (lowest - region-based, less precise)
--
-- This view replaces the need to manually choose sources and ensures
-- the recommendation system always uses the best available data.

CREATE OR REPLACE VIEW species_climate_envelope_unified AS
WITH sources AS (
    SELECT
        s.id as species_id,

        -- Source flags
        ceg.species_id IS NOT NULL as has_gbif,
        cee.species_id IS NOT NULL as has_ecoregion,
        sce.species_id IS NOT NULL as has_wcvp,

        -- GBIF data
        ceg.temp_mean as gbif_temp_mean,
        ceg.temp_min as gbif_temp_min,
        ceg.temp_max as gbif_temp_max,
        ceg.cold_month_mean as gbif_cold_month_min,
        ceg.warm_month_mean as gbif_warm_month_max,
        ceg.precip_mean as gbif_precip_mean,
        ceg.precip_min as gbif_precip_min,
        ceg.precip_max as gbif_precip_max,
        ceg.precip_seasonality as gbif_precip_seasonality,
        ceg.n_occurrences as gbif_n_samples,
        ceg.envelope_quality as gbif_quality,

        -- Ecoregion data
        cee.temp_mean as eco_temp_mean,
        cee.temp_min as eco_temp_min,
        cee.temp_max as eco_temp_max,
        cee.cold_month_min as eco_cold_month_min,
        cee.warm_month_max as eco_warm_month_max,
        cee.precip_mean as eco_precip_mean,
        cee.precip_min as eco_precip_min,
        cee.precip_max as eco_precip_max,
        cee.precip_seasonality as eco_precip_seasonality,
        cee.n_ecoregions as eco_n_samples,
        cee.envelope_quality as eco_quality,

        -- WCVP data
        sce.temp_mean as wcvp_temp_mean,
        sce.temp_min as wcvp_temp_min,
        sce.temp_max as wcvp_temp_max,
        sce.cold_month_min as wcvp_cold_month_min,
        sce.warm_month_max as wcvp_warm_month_max,
        sce.precip_mean as wcvp_precip_mean,
        sce.precip_min as wcvp_precip_min,
        sce.precip_max as wcvp_precip_max,
        sce.precip_seasonality as wcvp_precip_seasonality,
        sce.n_regions_sampled as wcvp_n_samples,
        -- WCVP doesn't have envelope_quality, derive from n_regions
        CASE
            WHEN sce.n_regions_sampled >= 5 THEN 'high'
            WHEN sce.n_regions_sampled >= 2 THEN 'medium'
            ELSE 'low'
        END as wcvp_quality

    FROM species s
    LEFT JOIN climate_envelope_gbif ceg ON s.id = ceg.species_id
    LEFT JOIN climate_envelope_ecoregion cee ON s.id = cee.species_id
    LEFT JOIN species_climate_envelope sce ON s.id = sce.species_id
    WHERE ceg.species_id IS NOT NULL
       OR cee.species_id IS NOT NULL
       OR sce.species_id IS NOT NULL
)
SELECT
    species_id,

    -- Priority source (for transparency)
    CASE
        WHEN has_gbif THEN 'gbif'
        WHEN has_ecoregion THEN 'ecoregion'
        WHEN has_wcvp THEN 'wcvp'
    END as envelope_source,

    -- Prioritized values (GBIF > Ecoregion > WCVP)
    COALESCE(gbif_temp_mean, eco_temp_mean, wcvp_temp_mean) as temp_mean,
    COALESCE(gbif_temp_min, eco_temp_min, wcvp_temp_min) as temp_min,
    COALESCE(gbif_temp_max, eco_temp_max, wcvp_temp_max) as temp_max,
    COALESCE(gbif_cold_month_min, eco_cold_month_min, wcvp_cold_month_min) as cold_month_min,
    COALESCE(gbif_warm_month_max, eco_warm_month_max, wcvp_warm_month_max) as warm_month_max,
    COALESCE(gbif_precip_mean, eco_precip_mean, wcvp_precip_mean) as precip_mean,
    COALESCE(gbif_precip_min, eco_precip_min, wcvp_precip_min) as precip_min,
    COALESCE(gbif_precip_max, eco_precip_max, wcvp_precip_max) as precip_max,
    COALESCE(gbif_precip_seasonality, eco_precip_seasonality, wcvp_precip_seasonality) as precip_seasonality,

    -- Sample size (number of occurrences/regions/ecoregions)
    COALESCE(gbif_n_samples, eco_n_samples, wcvp_n_samples) as n_samples,

    -- Quality flag
    COALESCE(gbif_quality, eco_quality, wcvp_quality) as envelope_quality,

    -- Multi-source consensus (optional, for future analysis)
    CASE
        WHEN has_gbif AND has_ecoregion AND has_wcvp THEN 'high'
        WHEN (has_gbif AND has_ecoregion) OR (has_gbif AND has_wcvp) OR (has_ecoregion AND has_wcvp) THEN 'medium'
        ELSE 'single'
    END as source_consensus

FROM sources;

-- Note: Cannot create index on views. If performance is an issue,
-- convert to MATERIALIZED VIEW and add:
-- CREATE INDEX idx_climate_envelope_unified_species
--     ON species_climate_envelope_unified (species_id);

COMMENT ON VIEW species_climate_envelope_unified IS
'Unified view combining climate envelopes from GBIF, Ecoregion (TreeGOER), and WCVP sources.
Priority order: GBIF > Ecoregion > WCVP.
Use this view instead of individual envelope tables for recommendations.';

-- Verification query
SELECT
    envelope_source,
    COUNT(*) as species_count,
    COUNT(*) FILTER (WHERE envelope_quality = 'high') as high_quality,
    COUNT(*) FILTER (WHERE envelope_quality = 'medium') as medium_quality,
    COUNT(*) FILTER (WHERE envelope_quality = 'low') as low_quality
FROM species_climate_envelope_unified
GROUP BY envelope_source
ORDER BY species_count DESC;

-- Tree coverage with unified view
SELECT
    'Trees with envelope (unified)' as metric,
    COUNT(DISTINCT ceu.species_id) as count,
    ROUND(100.0 * COUNT(DISTINCT ceu.species_id) /
          NULLIF(COUNT(DISTINCT su.species_id), 0), 1) as pct
FROM species_unified su
LEFT JOIN species_climate_envelope_unified ceu ON su.species_id = ceu.species_id
WHERE su.is_tree = TRUE;
