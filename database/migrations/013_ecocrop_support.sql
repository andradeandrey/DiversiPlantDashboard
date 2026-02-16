-- Migration 013: EcoCrop Support
-- Adds ecocrop_id to species table and creates climate_envelope_ecocrop table
-- for FAO EcoCrop cultivated species data

-- 1. Add ecocrop_id column to species table
ALTER TABLE species ADD COLUMN IF NOT EXISTS ecocrop_id VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_species_ecocrop_id ON species(ecocrop_id);

-- 2. EcoCrop-specific climate envelope table (detailed FAO data)
CREATE TABLE IF NOT EXISTS climate_envelope_ecocrop (
    species_id INTEGER PRIMARY KEY REFERENCES species(id) ON DELETE CASCADE,

    -- Temperature (C)
    temp_optimal_min DECIMAL(6,2),
    temp_optimal_max DECIMAL(6,2),
    temp_abs_min DECIMAL(6,2),
    temp_abs_max DECIMAL(6,2),
    killing_temperature DECIMAL(6,2),

    -- Rainfall (mm/year)
    rainfall_optimal_min DECIMAL(8,2),
    rainfall_optimal_max DECIMAL(8,2),
    rainfall_abs_min DECIMAL(8,2),
    rainfall_abs_max DECIMAL(8,2),

    -- Growing cycle (days)
    growing_cycle_min INTEGER,
    growing_cycle_max INTEGER,

    -- Soil pH
    ph_optimal_min DECIMAL(4,2),
    ph_optimal_max DECIMAL(4,2),
    ph_abs_min DECIMAL(4,2),
    ph_abs_max DECIMAL(4,2),

    -- Metadata from EcoCrop
    categories TEXT[],
    life_span VARCHAR(50),
    altitude_max_m INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE climate_envelope_ecocrop IS 'FAO EcoCrop climate envelopes for cultivated species';

-- 3. Register ecocrop in crawler_status if table exists
INSERT INTO crawler_status (crawler_name, status)
VALUES ('ecocrop', 'idle')
ON CONFLICT (crawler_name) DO NOTHING;

-- 4. Update unified view to include EcoCrop as a climate envelope source
-- Must drop first because ROUND() changes column type from numeric(6,2) to numeric
DROP VIEW IF EXISTS species_climate_envelope_unified CASCADE;
CREATE OR REPLACE VIEW species_climate_envelope_unified AS
WITH sources AS (
    SELECT
        s.id as species_id,

        -- Source flags
        ceg.species_id IS NOT NULL as has_gbif,
        cee.species_id IS NOT NULL as has_ecoregion,
        sce.species_id IS NOT NULL as has_wcvp,
        cec.species_id IS NOT NULL as has_ecocrop,

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
        CASE
            WHEN sce.n_regions_sampled >= 5 THEN 'high'
            WHEN sce.n_regions_sampled >= 2 THEN 'medium'
            ELSE 'low'
        END as wcvp_quality,

        -- EcoCrop data (mapped to common columns)
        ROUND(((cec.temp_optimal_min + cec.temp_optimal_max) / 2.0)::numeric, 2) as ecocrop_temp_mean,
        cec.temp_abs_min as ecocrop_temp_min,
        cec.temp_abs_max as ecocrop_temp_max,
        cec.temp_abs_min as ecocrop_cold_month_min,
        cec.temp_abs_max as ecocrop_warm_month_max,
        ROUND(((cec.rainfall_optimal_min + cec.rainfall_optimal_max) / 2.0)::numeric, 2) as ecocrop_precip_mean,
        cec.rainfall_abs_min as ecocrop_precip_min,
        cec.rainfall_abs_max as ecocrop_precip_max,
        NULL::DECIMAL as ecocrop_precip_seasonality,
        1 as ecocrop_n_samples,
        'medium'::VARCHAR as ecocrop_quality

    FROM species s
    LEFT JOIN climate_envelope_gbif ceg ON s.id = ceg.species_id
    LEFT JOIN climate_envelope_ecoregion cee ON s.id = cee.species_id
    LEFT JOIN species_climate_envelope sce ON s.id = sce.species_id
    LEFT JOIN climate_envelope_ecocrop cec ON s.id = cec.species_id
    WHERE ceg.species_id IS NOT NULL
       OR cee.species_id IS NOT NULL
       OR sce.species_id IS NOT NULL
       OR cec.species_id IS NOT NULL
)
SELECT
    species_id,

    -- Priority source: GBIF > Ecoregion > WCVP > EcoCrop
    CASE
        WHEN has_gbif THEN 'gbif'
        WHEN has_ecoregion THEN 'ecoregion'
        WHEN has_wcvp THEN 'wcvp'
        WHEN has_ecocrop THEN 'ecocrop'
    END as envelope_source,

    -- Prioritized values
    COALESCE(gbif_temp_mean, eco_temp_mean, wcvp_temp_mean, ecocrop_temp_mean) as temp_mean,
    COALESCE(gbif_temp_min, eco_temp_min, wcvp_temp_min, ecocrop_temp_min) as temp_min,
    COALESCE(gbif_temp_max, eco_temp_max, wcvp_temp_max, ecocrop_temp_max) as temp_max,
    COALESCE(gbif_cold_month_min, eco_cold_month_min, wcvp_cold_month_min, ecocrop_cold_month_min) as cold_month_min,
    COALESCE(gbif_warm_month_max, eco_warm_month_max, wcvp_warm_month_max, ecocrop_warm_month_max) as warm_month_max,
    COALESCE(gbif_precip_mean, eco_precip_mean, wcvp_precip_mean, ecocrop_precip_mean) as precip_mean,
    COALESCE(gbif_precip_min, eco_precip_min, wcvp_precip_min, ecocrop_precip_min) as precip_min,
    COALESCE(gbif_precip_max, eco_precip_max, wcvp_precip_max, ecocrop_precip_max) as precip_max,
    COALESCE(gbif_precip_seasonality, eco_precip_seasonality, wcvp_precip_seasonality, ecocrop_precip_seasonality) as precip_seasonality,

    COALESCE(gbif_n_samples, eco_n_samples, wcvp_n_samples, ecocrop_n_samples) as n_samples,
    COALESCE(gbif_quality, eco_quality, wcvp_quality, ecocrop_quality) as envelope_quality,

    CASE
        WHEN has_gbif AND has_ecoregion AND has_wcvp THEN 'high'
        WHEN (has_gbif AND has_ecoregion) OR (has_gbif AND has_wcvp) OR (has_ecoregion AND has_wcvp) THEN 'medium'
        ELSE 'single'
    END as source_consensus

FROM sources;

COMMENT ON VIEW species_climate_envelope_unified IS
'Unified view combining climate envelopes from GBIF, Ecoregion, WCVP, and EcoCrop sources.
Priority order: GBIF > Ecoregion > WCVP > EcoCrop.';
