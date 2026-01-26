-- Migration 010: Multi-Source Climate Envelope System
-- Creates tables for GBIF occurrences, separate envelope sources, and discrepancy analysis

-- 1. Table for individual GBIF occurrences with extracted climate
CREATE TABLE IF NOT EXISTS gbif_occurrences (
    id SERIAL PRIMARY KEY,
    species_id INTEGER REFERENCES species(id),
    gbif_id BIGINT UNIQUE,
    latitude DECIMAL(10,6) NOT NULL,
    longitude DECIMAL(10,6) NOT NULL,
    coordinate_uncertainty_m INTEGER,
    year INTEGER,
    country_code VARCHAR(2),

    -- Climate extracted from WorldClim raster
    bio1 DECIMAL(6,2),   -- Annual Mean Temperature
    bio5 DECIMAL(6,2),   -- Max Temp of Warmest Month
    bio6 DECIMAL(6,2),   -- Min Temp of Coldest Month
    bio7 DECIMAL(6,2),   -- Temperature Annual Range
    bio12 DECIMAL(8,2),  -- Annual Precipitation
    bio15 DECIMAL(6,2),  -- Precipitation Seasonality

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gbif_occ_species ON gbif_occurrences(species_id);
CREATE INDEX IF NOT EXISTS idx_gbif_occ_coords ON gbif_occurrences(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_gbif_occ_year ON gbif_occurrences(year);

COMMENT ON TABLE gbif_occurrences IS 'Individual GBIF occurrence records with extracted WorldClim climate data';

-- 2. Envelope derived from GBIF occurrences (individual points)
CREATE TABLE IF NOT EXISTS climate_envelope_gbif (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),

    -- Temperature (C) - percentiles from occurrences
    temp_mean DECIMAL(6,2),
    temp_p05 DECIMAL(6,2),   -- Percentile 5%
    temp_p95 DECIMAL(6,2),   -- Percentile 95%
    temp_min DECIMAL(6,2),
    temp_max DECIMAL(6,2),

    -- Cold/Heat tolerance
    cold_month_mean DECIMAL(6,2),
    cold_month_p05 DECIMAL(6,2),
    warm_month_mean DECIMAL(6,2),
    warm_month_p95 DECIMAL(6,2),

    -- Precipitation (mm/year)
    precip_mean DECIMAL(8,2),
    precip_p05 DECIMAL(8,2),
    precip_p95 DECIMAL(8,2),
    precip_min DECIMAL(8,2),
    precip_max DECIMAL(8,2),
    precip_seasonality DECIMAL(6,2),

    -- Quality metrics
    n_occurrences INTEGER,
    n_countries INTEGER,
    year_range VARCHAR(20),
    envelope_quality VARCHAR(10),  -- high/medium/low

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_envelope_gbif_quality ON climate_envelope_gbif(envelope_quality);

COMMENT ON TABLE climate_envelope_gbif IS 'Climate envelopes derived from GBIF individual occurrences - highest precision';

-- 3. Envelope derived from WCVP regions (TDWG distribution)
CREATE TABLE IF NOT EXISTS climate_envelope_wcvp (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),

    temp_mean DECIMAL(6,2),
    temp_min DECIMAL(6,2),
    temp_max DECIMAL(6,2),
    temp_range DECIMAL(6,2),

    cold_month_min DECIMAL(6,2),
    warm_month_max DECIMAL(6,2),

    precip_mean DECIMAL(8,2),
    precip_min DECIMAL(8,2),
    precip_max DECIMAL(8,2),
    precip_seasonality DECIMAL(6,2),

    n_regions INTEGER,
    envelope_quality VARCHAR(10),

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_envelope_wcvp_quality ON climate_envelope_wcvp(envelope_quality);
CREATE INDEX IF NOT EXISTS idx_envelope_wcvp_regions ON climate_envelope_wcvp(n_regions);

COMMENT ON TABLE climate_envelope_wcvp IS 'Climate envelopes derived from WCVP TDWG region distribution - broadest coverage';

-- 4. Envelope derived from Ecoregions (TreeGOER data)
CREATE TABLE IF NOT EXISTS climate_envelope_ecoregion (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),

    temp_mean DECIMAL(6,2),
    temp_min DECIMAL(6,2),
    temp_max DECIMAL(6,2),
    temp_range DECIMAL(6,2),

    cold_month_min DECIMAL(6,2),
    warm_month_max DECIMAL(6,2),

    precip_mean DECIMAL(8,2),
    precip_min DECIMAL(8,2),
    precip_max DECIMAL(8,2),
    precip_seasonality DECIMAL(6,2),

    n_ecoregions INTEGER,
    envelope_quality VARCHAR(10),

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_envelope_eco_quality ON climate_envelope_ecoregion(envelope_quality);
CREATE INDEX IF NOT EXISTS idx_envelope_eco_regions ON climate_envelope_ecoregion(n_ecoregions);

COMMENT ON TABLE climate_envelope_ecoregion IS 'Climate envelopes derived from TreeGOER ecoregion data - trees only';

-- 5. Analysis table for comparing sources and detecting discrepancies
CREATE TABLE IF NOT EXISTS climate_envelope_analysis (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),

    -- Sources available
    has_gbif BOOLEAN DEFAULT FALSE,
    has_wcvp BOOLEAN DEFAULT FALSE,
    has_ecoregion BOOLEAN DEFAULT FALSE,
    n_sources INTEGER,

    -- Best envelope selection
    best_source VARCHAR(20),  -- 'gbif', 'wcvp', 'ecoregion', 'consensus'

    -- Consensus envelope (weighted average)
    consensus_temp_mean DECIMAL(6,2),
    consensus_temp_min DECIMAL(6,2),
    consensus_temp_max DECIMAL(6,2),
    consensus_precip_mean DECIMAL(8,2),
    consensus_precip_min DECIMAL(8,2),
    consensus_precip_max DECIMAL(8,2),

    -- Discrepancy metrics
    temp_mean_discrepancy DECIMAL(6,2),  -- Max diff between sources
    temp_range_discrepancy DECIMAL(6,2),
    precip_mean_discrepancy DECIMAL(8,2),
    overall_agreement VARCHAR(10),  -- 'high', 'medium', 'low', 'single'

    -- Review flags
    needs_review BOOLEAN DEFAULT FALSE,
    review_reason TEXT,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_sources ON climate_envelope_analysis(n_sources);
CREATE INDEX IF NOT EXISTS idx_analysis_agreement ON climate_envelope_analysis(overall_agreement);
CREATE INDEX IF NOT EXISTS idx_analysis_review ON climate_envelope_analysis(needs_review) WHERE needs_review = TRUE;
CREATE INDEX IF NOT EXISTS idx_analysis_best_source ON climate_envelope_analysis(best_source);

COMMENT ON TABLE climate_envelope_analysis IS 'Comparison and analysis of climate envelopes from different sources';

-- 6. View for easy access to best available envelope
CREATE OR REPLACE VIEW v_species_climate_envelope AS
SELECT
    s.id as species_id,
    s.canonical_name,
    s.family,
    su.growth_form,

    -- Best source selection
    cea.best_source,
    cea.n_sources,
    cea.overall_agreement,

    -- Use consensus or best available
    COALESCE(cea.consensus_temp_mean, ceg.temp_mean, cee.temp_mean, cew.temp_mean) as temp_mean,
    COALESCE(cea.consensus_temp_min, ceg.temp_min, cee.temp_min, cew.temp_min) as temp_min,
    COALESCE(cea.consensus_temp_max, ceg.temp_max, cee.temp_max, cew.temp_max) as temp_max,
    COALESCE(cea.consensus_precip_mean, ceg.precip_mean, cee.precip_mean, cew.precip_mean) as precip_mean,
    COALESCE(cea.consensus_precip_min, ceg.precip_min, cee.precip_min, cew.precip_min) as precip_min,
    COALESCE(cea.consensus_precip_max, ceg.precip_max, cee.precip_max, cew.precip_max) as precip_max,

    -- Cold/heat tolerance (use GBIF percentiles if available, else min/max from other sources)
    COALESCE(ceg.cold_month_p05, cee.cold_month_min, cew.cold_month_min) as cold_tolerance,
    COALESCE(ceg.warm_month_p95, cee.warm_month_max, cew.warm_month_max) as heat_tolerance,

    -- Quality indicator
    CASE
        WHEN cea.n_sources >= 2 AND cea.overall_agreement = 'high' THEN 'verified'
        WHEN ceg.envelope_quality = 'high' THEN 'high'
        WHEN COALESCE(ceg.envelope_quality, cee.envelope_quality, cew.envelope_quality) = 'medium' THEN 'medium'
        ELSE 'low'
    END as envelope_confidence,

    cea.needs_review

FROM species s
JOIN species_unified su ON s.id = su.species_id
LEFT JOIN climate_envelope_analysis cea ON s.id = cea.species_id
LEFT JOIN climate_envelope_gbif ceg ON s.id = ceg.species_id
LEFT JOIN climate_envelope_ecoregion cee ON s.id = cee.species_id
LEFT JOIN climate_envelope_wcvp cew ON s.id = cew.species_id
WHERE cea.species_id IS NOT NULL
   OR ceg.species_id IS NOT NULL
   OR cee.species_id IS NOT NULL
   OR cew.species_id IS NOT NULL;

COMMENT ON VIEW v_species_climate_envelope IS 'Unified view with best available climate envelope for each species';

-- 7. Function to update analysis table for a species
CREATE OR REPLACE FUNCTION update_envelope_analysis(p_species_id INTEGER)
RETURNS VOID AS $$
DECLARE
    v_gbif RECORD;
    v_wcvp RECORD;
    v_eco RECORD;
    v_n_sources INTEGER := 0;
    v_temps DECIMAL[];
    v_temp_discrepancy DECIMAL;
    v_precip_discrepancy DECIMAL;
    v_agreement VARCHAR(10);
BEGIN
    -- Get envelope from each source
    SELECT * INTO v_gbif FROM climate_envelope_gbif WHERE species_id = p_species_id;
    SELECT * INTO v_wcvp FROM climate_envelope_wcvp WHERE species_id = p_species_id;
    SELECT * INTO v_eco FROM climate_envelope_ecoregion WHERE species_id = p_species_id;

    -- Count sources
    IF v_gbif.species_id IS NOT NULL THEN v_n_sources := v_n_sources + 1; END IF;
    IF v_wcvp.species_id IS NOT NULL THEN v_n_sources := v_n_sources + 1; END IF;
    IF v_eco.species_id IS NOT NULL THEN v_n_sources := v_n_sources + 1; END IF;

    IF v_n_sources = 0 THEN
        RETURN;
    END IF;

    -- Calculate temperature discrepancy
    v_temps := ARRAY[]::DECIMAL[];
    IF v_gbif.temp_mean IS NOT NULL THEN v_temps := v_temps || v_gbif.temp_mean; END IF;
    IF v_wcvp.temp_mean IS NOT NULL THEN v_temps := v_temps || v_wcvp.temp_mean; END IF;
    IF v_eco.temp_mean IS NOT NULL THEN v_temps := v_temps || v_eco.temp_mean; END IF;

    IF array_length(v_temps, 1) >= 2 THEN
        v_temp_discrepancy := (SELECT MAX(t) - MIN(t) FROM unnest(v_temps) t);
    ELSE
        v_temp_discrepancy := 0;
    END IF;

    -- Determine agreement level
    IF v_n_sources = 1 THEN
        v_agreement := 'single';
    ELSIF v_temp_discrepancy <= 2 THEN
        v_agreement := 'high';
    ELSIF v_temp_discrepancy <= 5 THEN
        v_agreement := 'medium';
    ELSE
        v_agreement := 'low';
    END IF;

    -- Insert or update analysis
    INSERT INTO climate_envelope_analysis (
        species_id, has_gbif, has_wcvp, has_ecoregion, n_sources,
        best_source,
        consensus_temp_mean, consensus_temp_min, consensus_temp_max,
        consensus_precip_mean, consensus_precip_min, consensus_precip_max,
        temp_mean_discrepancy, overall_agreement, needs_review, review_reason
    ) VALUES (
        p_species_id,
        v_gbif.species_id IS NOT NULL,
        v_wcvp.species_id IS NOT NULL,
        v_eco.species_id IS NOT NULL,
        v_n_sources,
        CASE
            WHEN v_gbif.species_id IS NOT NULL AND v_gbif.envelope_quality IN ('high', 'medium') THEN 'gbif'
            WHEN v_eco.species_id IS NOT NULL AND v_eco.envelope_quality IN ('high', 'medium') THEN 'ecoregion'
            WHEN v_wcvp.species_id IS NOT NULL THEN 'wcvp'
            ELSE 'none'
        END,
        -- Weighted average for consensus
        ROUND((
            COALESCE(v_gbif.temp_mean * CASE v_gbif.envelope_quality WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END, 0) +
            COALESCE(v_wcvp.temp_mean * CASE v_wcvp.envelope_quality WHEN 'high' THEN 2 WHEN 'medium' THEN 1.5 ELSE 1 END, 0) +
            COALESCE(v_eco.temp_mean * CASE v_eco.envelope_quality WHEN 'high' THEN 2.5 WHEN 'medium' THEN 1.5 ELSE 1 END, 0)
        ) / NULLIF(
            CASE WHEN v_gbif.species_id IS NOT NULL THEN CASE v_gbif.envelope_quality WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END ELSE 0 END +
            CASE WHEN v_wcvp.species_id IS NOT NULL THEN CASE v_wcvp.envelope_quality WHEN 'high' THEN 2 WHEN 'medium' THEN 1.5 ELSE 1 END ELSE 0 END +
            CASE WHEN v_eco.species_id IS NOT NULL THEN CASE v_eco.envelope_quality WHEN 'high' THEN 2.5 WHEN 'medium' THEN 1.5 ELSE 1 END ELSE 0 END
        , 0)::numeric, 2),
        LEAST(COALESCE(v_gbif.temp_min, 999), COALESCE(v_wcvp.temp_min, 999), COALESCE(v_eco.temp_min, 999)),
        GREATEST(COALESCE(v_gbif.temp_max, -999), COALESCE(v_wcvp.temp_max, -999), COALESCE(v_eco.temp_max, -999)),
        ROUND((COALESCE(v_gbif.precip_mean, 0) + COALESCE(v_wcvp.precip_mean, 0) + COALESCE(v_eco.precip_mean, 0)) / NULLIF(v_n_sources, 0)::numeric, 2),
        LEAST(COALESCE(v_gbif.precip_min, 99999), COALESCE(v_wcvp.precip_min, 99999), COALESCE(v_eco.precip_min, 99999)),
        GREATEST(COALESCE(v_gbif.precip_max, 0), COALESCE(v_wcvp.precip_max, 0), COALESCE(v_eco.precip_max, 0)),
        v_temp_discrepancy,
        v_agreement,
        v_temp_discrepancy > 5,
        CASE WHEN v_temp_discrepancy > 5 THEN 'temp_mean diff > 5C' ELSE NULL END
    )
    ON CONFLICT (species_id) DO UPDATE SET
        has_gbif = EXCLUDED.has_gbif,
        has_wcvp = EXCLUDED.has_wcvp,
        has_ecoregion = EXCLUDED.has_ecoregion,
        n_sources = EXCLUDED.n_sources,
        best_source = EXCLUDED.best_source,
        consensus_temp_mean = EXCLUDED.consensus_temp_mean,
        consensus_temp_min = EXCLUDED.consensus_temp_min,
        consensus_temp_max = EXCLUDED.consensus_temp_max,
        consensus_precip_mean = EXCLUDED.consensus_precip_mean,
        consensus_precip_min = EXCLUDED.consensus_precip_min,
        consensus_precip_max = EXCLUDED.consensus_precip_max,
        temp_mean_discrepancy = EXCLUDED.temp_mean_discrepancy,
        overall_agreement = EXCLUDED.overall_agreement,
        needs_review = EXCLUDED.needs_review,
        review_reason = EXCLUDED.review_reason,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_envelope_analysis IS 'Updates the analysis table for a single species after envelope changes';

-- 8. Summary statistics view
CREATE OR REPLACE VIEW v_envelope_coverage_summary AS
SELECT
    su.growth_form,
    COUNT(DISTINCT su.species_id) as total_species,
    COUNT(DISTINCT ceg.species_id) as with_gbif,
    COUNT(DISTINCT cew.species_id) as with_wcvp,
    COUNT(DISTINCT cee.species_id) as with_ecoregion,
    COUNT(DISTINCT cea.species_id) FILTER (WHERE cea.n_sources >= 2) as multi_source,
    COUNT(DISTINCT cea.species_id) FILTER (WHERE cea.overall_agreement = 'high') as high_agreement,
    COUNT(DISTINCT cea.species_id) FILTER (WHERE cea.needs_review) as needs_review,
    ROUND(100.0 * COUNT(DISTINCT COALESCE(ceg.species_id, cew.species_id, cee.species_id)) /
          NULLIF(COUNT(DISTINCT su.species_id), 0), 1) as coverage_pct
FROM species_unified su
LEFT JOIN climate_envelope_gbif ceg ON su.species_id = ceg.species_id
LEFT JOIN climate_envelope_wcvp cew ON su.species_id = cew.species_id
LEFT JOIN climate_envelope_ecoregion cee ON su.species_id = cee.species_id
LEFT JOIN climate_envelope_analysis cea ON su.species_id = cea.species_id
GROUP BY su.growth_form
ORDER BY total_species DESC;

COMMENT ON VIEW v_envelope_coverage_summary IS 'Summary of climate envelope coverage by growth form';
