-- Migration 009: Plant Diversity Recommendation System
-- Creates tables and functions for climate-based diversity recommendations

-- ============================================================================
-- TABLE 1: species_climate_envelope
-- Stores aggregated climate data across all native regions per species
-- ============================================================================

CREATE TABLE IF NOT EXISTS species_climate_envelope (
    species_id INTEGER PRIMARY KEY REFERENCES species(id) ON DELETE CASCADE,

    -- Temperature envelope (°C)
    temp_mean DECIMAL(6,2),      -- Average temperature across native range
    temp_min DECIMAL(6,2),       -- Absolute minimum tolerated (bio6)
    temp_max DECIMAL(6,2),       -- Absolute maximum tolerated (bio5)
    temp_range DECIMAL(6,2),     -- Temperature range (bio7)

    -- Precipitation envelope (mm/year)
    precip_mean DECIMAL(8,2),    -- Average annual precipitation
    precip_min DECIMAL(8,2),     -- Minimum precipitation tolerated
    precip_max DECIMAL(8,2),     -- Maximum precipitation tolerated
    precip_seasonality DECIMAL(6,2), -- Coefficient of variation (bio15)

    -- Cold/heat tolerance (critical thresholds)
    cold_month_min DECIMAL(6,2), -- bio6 minimum (frost tolerance)
    warm_month_max DECIMAL(6,2), -- bio5 maximum (heat tolerance)

    -- Climate breadth (generalist vs specialist)
    n_koppen_zones INTEGER,      -- Number of Köppen zones where species occurs
    n_whittaker_biomes INTEGER,  -- Number of biomes where species occurs
    climate_breadth_score DECIMAL(6,3), -- 0-1 (generalist = high)

    -- Metadata
    n_regions_sampled INTEGER,   -- Sample size for statistics
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for climate queries
CREATE INDEX idx_climate_envelope_temp ON species_climate_envelope(temp_mean);
CREATE INDEX idx_climate_envelope_precip ON species_climate_envelope(precip_mean);
CREATE INDEX idx_climate_envelope_species ON species_climate_envelope(species_id);

-- ============================================================================
-- TABLE 2: species_trait_vectors
-- Stores normalized trait values for Gower distance calculation
-- ============================================================================

CREATE TABLE IF NOT EXISTS species_trait_vectors (
    species_id INTEGER PRIMARY KEY REFERENCES species(id) ON DELETE CASCADE,

    -- Categorical traits (boolean flags)
    is_tree BOOLEAN,
    is_shrub BOOLEAN,
    is_herb BOOLEAN,
    is_climber BOOLEAN,
    is_palm BOOLEAN,
    is_nitrogen_fixer BOOLEAN,

    -- Continuous traits (normalized 0-1)
    height_normalized DECIMAL(5,4),  -- 0=herb, 1=tallest (80m)
    lifespan_normalized DECIMAL(5,4), -- 0=annual, 1=ancient (15000y)

    -- Dispersal (categorical groups)
    dispersal_animal BOOLEAN,
    dispersal_wind BOOLEAN,
    dispersal_water BOOLEAN,

    -- Phylogenetic proxy
    family_code INTEGER,  -- Numeric hash of family name

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for trait queries
CREATE INDEX idx_trait_vectors_height ON species_trait_vectors(height_normalized);
CREATE INDEX idx_trait_vectors_species ON species_trait_vectors(species_id);

-- ============================================================================
-- TABLE 3: recommendation_cache
-- Caches recommendation results to avoid recalculation
-- ============================================================================

CREATE TABLE IF NOT EXISTS recommendation_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,

    -- Query parameters
    location_tdwg VARCHAR(10),
    location_lat DECIMAL(10,6),
    location_lon DECIMAL(10,6),
    preferences JSONB,
    climate_threshold DECIMAL(3,2),
    n_species INTEGER,

    -- Cached results
    recommended_species INTEGER[],  -- Array of species IDs
    diversity_metrics JSONB,

    -- Cache metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    hit_count INTEGER DEFAULT 0
);

-- Indexes for cache lookups
CREATE INDEX idx_recommendation_cache_key ON recommendation_cache(cache_key);
CREATE INDEX idx_recommendation_cache_expires ON recommendation_cache(expires_at);

-- ============================================================================
-- FUNCTION: calculate_climate_match
-- Calculates a climate match score (0-1) for a species at a location
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_climate_match(
    p_species_id INTEGER,
    p_bio1 DECIMAL,  -- Target annual mean temperature
    p_bio5 DECIMAL,  -- Target max temp of warmest month
    p_bio6 DECIMAL,  -- Target min temp of coldest month
    p_bio12 DECIMAL, -- Target annual precipitation
    p_bio15 DECIMAL  -- Target precipitation seasonality
) RETURNS DECIMAL AS $$
DECLARE
    v_envelope RECORD;
    v_score DECIMAL := 0;
    v_temp_diff DECIMAL;
    v_precip_diff DECIMAL;
    v_season_diff DECIMAL;
BEGIN
    -- Get species climate envelope
    SELECT * INTO v_envelope
    FROM species_climate_envelope
    WHERE species_id = p_species_id;

    IF NOT FOUND THEN
        RETURN 0;
    END IF;

    -- 1. Temperature mean match (25% weight)
    -- Tolerance: ±10°C
    v_temp_diff := ABS(p_bio1 - v_envelope.temp_mean);
    v_score := v_score + GREATEST(0, 1 - v_temp_diff / 10.0) * 0.25;

    -- 2. Temperature extremes HARD FILTER (25% weight)
    -- Species cannot survive if outside tolerance range (±3°C margin)
    IF p_bio6 < v_envelope.temp_min - 3 OR p_bio5 > v_envelope.temp_max + 3 THEN
        RETURN 0;  -- Outside tolerance range - species would die
    ELSE
        v_score := v_score + 0.25;
    END IF;

    -- 3. Precipitation match (20% weight)
    IF v_envelope.precip_mean > 0 THEN
        v_precip_diff := ABS(p_bio12 - v_envelope.precip_mean);
        v_score := v_score + GREATEST(0, 1 - v_precip_diff / v_envelope.precip_mean) * 0.20;
    ELSE
        v_score := v_score + 0.10;  -- Partial credit if no data
    END IF;

    -- 4. Precipitation seasonality (15% weight)
    v_season_diff := ABS(p_bio15 - v_envelope.precip_seasonality);
    v_score := v_score + GREATEST(0, 1 - v_season_diff / 50.0) * 0.15;

    -- 5. Cold hardiness (15% weight)
    IF p_bio6 < 0 THEN  -- Frost occurs at target location
        IF v_envelope.cold_month_min < p_bio6 - 2 THEN
            v_score := v_score + 0.15;  -- Can handle frost
        ELSE
            v_score := v_score + 0.05;  -- Risky - might not survive frost
        END IF;
    ELSE
        v_score := v_score + 0.15;  -- No frost concern
    END IF;

    RETURN ROUND(v_score::numeric, 3);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- DATA POPULATION: species_climate_envelope
-- Aggregates climate data from all native regions per species
-- ============================================================================

INSERT INTO species_climate_envelope
SELECT
    s.id as species_id,
    ROUND(AVG(c.bio1_mean)::numeric, 2) as temp_mean,
    ROUND(MIN(c.bio1_min)::numeric, 2) as temp_min,
    ROUND(MAX(c.bio1_max)::numeric, 2) as temp_max,
    ROUND(AVG(c.bio7_mean)::numeric, 2) as temp_range,
    ROUND(AVG(c.bio12_mean)::numeric, 2) as precip_mean,
    ROUND(MIN(c.bio12_min)::numeric, 2) as precip_min,
    ROUND(MAX(c.bio12_max)::numeric, 2) as precip_max,
    ROUND(AVG(c.bio15_mean)::numeric, 2) as precip_seasonality,
    ROUND(MIN(c.bio6_mean)::numeric, 2) as cold_month_min,
    ROUND(MAX(c.bio5_mean)::numeric, 2) as warm_month_max,
    COUNT(DISTINCT c.koppen_zone) as n_koppen_zones,
    COUNT(DISTINCT c.whittaker_biome) as n_whittaker_biomes,
    LEAST(1.0, COUNT(DISTINCT c.koppen_zone)::numeric / 5.0) as climate_breadth_score,
    COUNT(DISTINCT sr.tdwg_code) as n_regions_sampled,
    CURRENT_TIMESTAMP as updated_at
FROM species s
JOIN species_regions sr ON s.id = sr.species_id AND sr.is_native = TRUE
JOIN tdwg_climate c ON sr.tdwg_code = c.tdwg_code
WHERE c.bio1_mean IS NOT NULL
GROUP BY s.id
HAVING COUNT(DISTINCT sr.tdwg_code) >= 2  -- Minimum 2 regions for reliability
ON CONFLICT (species_id) DO NOTHING;

-- ============================================================================
-- DATA POPULATION: species_trait_vectors
-- Normalizes trait values for diversity calculations
-- ============================================================================

INSERT INTO species_trait_vectors
SELECT
    su.species_id,
    su.is_tree,
    su.is_shrub,
    su.is_herb,
    su.is_climber,
    su.is_palm,
    COALESCE(su.nitrogen_fixer, FALSE) as is_nitrogen_fixer,

    -- Normalize height: 0-80m scale
    CASE
        WHEN su.max_height_m IS NULL THEN
            CASE
                WHEN su.is_tree THEN 0.5000  -- Default tree: mid-sized
                WHEN su.is_shrub THEN 0.1500
                WHEN su.is_herb THEN 0.0500
                ELSE 0.2500
            END
        ELSE LEAST(su.max_height_m / 80.0, 1.0)::numeric(5,4)
    END as height_normalized,

    -- Normalize lifespan: log scale 1-15000 years (Larrea tridentata = 11,700 years)
    CASE
        WHEN su.lifespan_years IS NULL THEN 0.3000  -- Default: medium
        ELSE (LN(GREATEST(su.lifespan_years, 1)) / LN(15000))::numeric(5,4)
    END as lifespan_normalized,

    -- Dispersal types (parse from dispersal_syndrome text)
    (su.dispersal_syndrome ILIKE '%zoo%' OR su.dispersal_syndrome ILIKE '%animal%' OR su.dispersal_syndrome ILIKE '%bird%') as dispersal_animal,
    (su.dispersal_syndrome ILIKE '%anemo%' OR su.dispersal_syndrome ILIKE '%wind%') as dispersal_wind,
    (su.dispersal_syndrome ILIKE '%hydro%' OR su.dispersal_syndrome ILIKE '%water%') as dispersal_water,

    -- Family code: simple hash for phylogenetic proxy
    ABS(HASHTEXT(s.family)) % 10000 as family_code,

    CURRENT_TIMESTAMP as updated_at
FROM species_unified su
JOIN species s ON su.species_id = s.id
WHERE su.growth_form IS NOT NULL
ON CONFLICT (species_id) DO NOTHING;

-- ============================================================================
-- VACUUM AND ANALYZE
-- ============================================================================

VACUUM ANALYZE species_climate_envelope;
VACUUM ANALYZE species_trait_vectors;
VACUUM ANALYZE recommendation_cache;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
