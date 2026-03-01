-- Migration 015: Fix climate matching for non-tree species (A2)
--
-- Problem: calculate_climate_match() returns 0 when species has no envelope,
-- causing threshold filters to exclude species without climate data.
-- Also: envelope was only built for species in 2+ TDWG regions, excluding
-- many herbs/forbs/vines with narrow native ranges.
--
-- Fix 1: Function returns NULL instead of 0 for missing envelopes
-- Fix 2: Lower HAVING threshold from 2 to 1 TDWG region
-- Fix 3: Ecoregion tab treats NULL score as "no data" (passes filter)

-- Fix 1: Recreate function to return NULL for missing species
CREATE OR REPLACE FUNCTION calculate_climate_match(
    p_species_id INTEGER,
    p_bio1 DECIMAL,
    p_bio5 DECIMAL,
    p_bio6 DECIMAL,
    p_bio12 DECIMAL,
    p_bio15 DECIMAL
) RETURNS DECIMAL AS $$
DECLARE
    v_envelope RECORD;
    v_score DECIMAL := 0;
    v_temp_diff DECIMAL;
    v_precip_diff DECIMAL;
    v_season_diff DECIMAL;
BEGIN
    SELECT * INTO v_envelope
    FROM species_climate_envelope
    WHERE species_id = p_species_id;

    IF NOT FOUND THEN
        RETURN NULL;  -- No climate envelope = unknown, not zero
    END IF;

    -- 1. Temperature mean match (25% weight)
    v_temp_diff := ABS(p_bio1 - v_envelope.temp_mean);
    v_score := v_score + GREATEST(0, 1 - v_temp_diff / 10.0) * 0.25;

    -- 2. Temperature extremes HARD FILTER (25% weight)
    IF p_bio6 < v_envelope.temp_min - 3 OR p_bio5 > v_envelope.temp_max + 3 THEN
        RETURN 0;
    ELSE
        v_score := v_score + 0.25;
    END IF;

    -- 3. Precipitation match (20% weight)
    IF v_envelope.precip_mean > 0 THEN
        v_precip_diff := ABS(p_bio12 - v_envelope.precip_mean);
        v_score := v_score + GREATEST(0, 1 - v_precip_diff / v_envelope.precip_mean) * 0.20;
    ELSE
        v_score := v_score + 0.10;
    END IF;

    -- 4. Precipitation seasonality (15% weight)
    v_season_diff := ABS(p_bio15 - v_envelope.precip_seasonality);
    v_score := v_score + GREATEST(0, 1 - v_season_diff / 50.0) * 0.15;

    -- 5. Cold hardiness (15% weight)
    IF p_bio6 < 0 THEN
        IF v_envelope.cold_month_min < p_bio6 - 2 THEN
            v_score := v_score + 0.15;
        ELSE
            v_score := v_score + 0.05;
        END IF;
    ELSE
        v_score := v_score + 0.15;
    END IF;

    RETURN ROUND(v_score::numeric, 3);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Fix 2: Repopulate species_climate_envelope with 1+ region threshold
-- (adds species that only occur natively in 1 TDWG area)
DELETE FROM species_climate_envelope;

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
HAVING COUNT(DISTINCT sr.tdwg_code) >= 1  -- Include species with 1+ native regions
ON CONFLICT (species_id) DO UPDATE SET
    temp_mean = EXCLUDED.temp_mean,
    temp_min = EXCLUDED.temp_min,
    temp_max = EXCLUDED.temp_max,
    temp_range = EXCLUDED.temp_range,
    precip_mean = EXCLUDED.precip_mean,
    precip_min = EXCLUDED.precip_min,
    precip_max = EXCLUDED.precip_max,
    precip_seasonality = EXCLUDED.precip_seasonality,
    cold_month_min = EXCLUDED.cold_month_min,
    warm_month_max = EXCLUDED.warm_month_max,
    n_koppen_zones = EXCLUDED.n_koppen_zones,
    n_whittaker_biomes = EXCLUDED.n_whittaker_biomes,
    climate_breadth_score = EXCLUDED.climate_breadth_score,
    n_regions_sampled = EXCLUDED.n_regions_sampled,
    updated_at = EXCLUDED.updated_at;
