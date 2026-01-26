-- Analyze climate envelope discrepancies between sources
-- Populates climate_envelope_analysis table and generates reports

\echo '=================================================='
\echo 'Climate Envelope Discrepancy Analysis'
\echo '=================================================='

-- Count current state
\echo ''
\echo '=== Current Envelope Counts ==='
SELECT 'GBIF' as source, COUNT(*) as count FROM climate_envelope_gbif
UNION ALL
SELECT 'WCVP', COUNT(*) FROM climate_envelope_wcvp
UNION ALL
SELECT 'Ecoregion', COUNT(*) FROM climate_envelope_ecoregion
UNION ALL
SELECT 'Analysis', COUNT(*) FROM climate_envelope_analysis;

-- Populate analysis table for all species with any envelope
\echo ''
\echo '=== Populating Analysis Table ==='

INSERT INTO climate_envelope_analysis (
    species_id,
    has_gbif,
    has_wcvp,
    has_ecoregion,
    n_sources,
    best_source,
    consensus_temp_mean,
    consensus_temp_min,
    consensus_temp_max,
    consensus_precip_mean,
    consensus_precip_min,
    consensus_precip_max,
    temp_mean_discrepancy,
    temp_range_discrepancy,
    precip_mean_discrepancy,
    overall_agreement,
    needs_review,
    review_reason
)
SELECT
    s.id,

    -- Sources available
    ceg.species_id IS NOT NULL as has_gbif,
    cew.species_id IS NOT NULL as has_wcvp,
    cee.species_id IS NOT NULL as has_ecoregion,
    (CASE WHEN ceg.species_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN cew.species_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN cee.species_id IS NOT NULL THEN 1 ELSE 0 END) as n_sources,

    -- Best source (priority: GBIF high/medium > Ecoregion high/medium > WCVP)
    CASE
        WHEN ceg.species_id IS NOT NULL AND ceg.envelope_quality IN ('high', 'medium') THEN 'gbif'
        WHEN cee.species_id IS NOT NULL AND cee.envelope_quality IN ('high', 'medium') THEN 'ecoregion'
        WHEN cew.species_id IS NOT NULL THEN 'wcvp'
        WHEN ceg.species_id IS NOT NULL THEN 'gbif'
        WHEN cee.species_id IS NOT NULL THEN 'ecoregion'
        ELSE 'none'
    END as best_source,

    -- Consensus temperature mean (weighted by quality)
    ROUND((
        COALESCE(ceg.temp_mean * CASE ceg.envelope_quality WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END, 0) +
        COALESCE(cew.temp_mean * CASE cew.envelope_quality WHEN 'high' THEN 2 WHEN 'medium' THEN 1.5 ELSE 1 END, 0) +
        COALESCE(cee.temp_mean * CASE cee.envelope_quality WHEN 'high' THEN 2.5 WHEN 'medium' THEN 1.5 ELSE 1 END, 0)
    ) / NULLIF(
        CASE WHEN ceg.species_id IS NOT NULL THEN CASE ceg.envelope_quality WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END ELSE 0 END +
        CASE WHEN cew.species_id IS NOT NULL THEN CASE cew.envelope_quality WHEN 'high' THEN 2 WHEN 'medium' THEN 1.5 ELSE 1 END ELSE 0 END +
        CASE WHEN cee.species_id IS NOT NULL THEN CASE cee.envelope_quality WHEN 'high' THEN 2.5 WHEN 'medium' THEN 1.5 ELSE 1 END ELSE 0 END
    , 0)::numeric, 2) as consensus_temp_mean,

    -- Consensus min/max (conservative: use extremes from all sources)
    LEAST(
        COALESCE(ceg.temp_min, 999),
        COALESCE(cew.temp_min, 999),
        COALESCE(cee.temp_min, 999)
    ) as consensus_temp_min,
    GREATEST(
        COALESCE(ceg.temp_max, -999),
        COALESCE(cew.temp_max, -999),
        COALESCE(cee.temp_max, -999)
    ) as consensus_temp_max,

    -- Consensus precipitation (simple average)
    ROUND((
        COALESCE(ceg.precip_mean, 0) +
        COALESCE(cew.precip_mean, 0) +
        COALESCE(cee.precip_mean, 0)
    ) / NULLIF(
        CASE WHEN ceg.species_id IS NOT NULL AND ceg.precip_mean IS NOT NULL THEN 1 ELSE 0 END +
        CASE WHEN cew.species_id IS NOT NULL AND cew.precip_mean IS NOT NULL THEN 1 ELSE 0 END +
        CASE WHEN cee.species_id IS NOT NULL AND cee.precip_mean IS NOT NULL THEN 1 ELSE 0 END
    , 0)::numeric, 2) as consensus_precip_mean,
    LEAST(
        COALESCE(ceg.precip_min, 99999),
        COALESCE(cew.precip_min, 99999),
        COALESCE(cee.precip_min, 99999)
    ) as consensus_precip_min,
    GREATEST(
        COALESCE(ceg.precip_max, 0),
        COALESCE(cew.precip_max, 0),
        COALESCE(cee.precip_max, 0)
    ) as consensus_precip_max,

    -- Temperature mean discrepancy (max difference between any two sources)
    GREATEST(
        ABS(COALESCE(ceg.temp_mean, cew.temp_mean, cee.temp_mean) - COALESCE(cew.temp_mean, ceg.temp_mean, cee.temp_mean)),
        ABS(COALESCE(ceg.temp_mean, cee.temp_mean, cew.temp_mean) - COALESCE(cee.temp_mean, ceg.temp_mean, cew.temp_mean)),
        ABS(COALESCE(cew.temp_mean, cee.temp_mean, ceg.temp_mean) - COALESCE(cee.temp_mean, cew.temp_mean, ceg.temp_mean))
    ) as temp_mean_discrepancy,

    -- Temperature range discrepancy
    GREATEST(
        ABS(COALESCE(ceg.temp_max - ceg.temp_min, 0) - COALESCE(cew.temp_max - cew.temp_min, 0)),
        ABS(COALESCE(ceg.temp_max - ceg.temp_min, 0) - COALESCE(cee.temp_max - cee.temp_min, 0)),
        ABS(COALESCE(cew.temp_max - cew.temp_min, 0) - COALESCE(cee.temp_max - cee.temp_min, 0))
    ) as temp_range_discrepancy,

    -- Precipitation mean discrepancy
    GREATEST(
        ABS(COALESCE(ceg.precip_mean, cew.precip_mean, cee.precip_mean) - COALESCE(cew.precip_mean, ceg.precip_mean, cee.precip_mean)),
        ABS(COALESCE(ceg.precip_mean, cee.precip_mean, cew.precip_mean) - COALESCE(cee.precip_mean, ceg.precip_mean, cew.precip_mean)),
        ABS(COALESCE(cew.precip_mean, cee.precip_mean, ceg.precip_mean) - COALESCE(cee.precip_mean, cew.precip_mean, ceg.precip_mean))
    ) as precip_mean_discrepancy,

    -- Overall agreement classification
    CASE
        WHEN (CASE WHEN ceg.species_id IS NOT NULL THEN 1 ELSE 0 END +
              CASE WHEN cew.species_id IS NOT NULL THEN 1 ELSE 0 END +
              CASE WHEN cee.species_id IS NOT NULL THEN 1 ELSE 0 END) <= 1 THEN 'single'
        WHEN GREATEST(
            ABS(COALESCE(ceg.temp_mean, cew.temp_mean) - COALESCE(cew.temp_mean, ceg.temp_mean)),
            ABS(COALESCE(ceg.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, ceg.temp_mean)),
            ABS(COALESCE(cew.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, cew.temp_mean))
        ) <= 2 THEN 'high'
        WHEN GREATEST(
            ABS(COALESCE(ceg.temp_mean, cew.temp_mean) - COALESCE(cew.temp_mean, ceg.temp_mean)),
            ABS(COALESCE(ceg.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, ceg.temp_mean)),
            ABS(COALESCE(cew.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, cew.temp_mean))
        ) <= 5 THEN 'medium'
        ELSE 'low'
    END as overall_agreement,

    -- Needs review if temp discrepancy > 5C
    GREATEST(
        ABS(COALESCE(ceg.temp_mean, cew.temp_mean) - COALESCE(cew.temp_mean, ceg.temp_mean)),
        ABS(COALESCE(ceg.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, ceg.temp_mean)),
        ABS(COALESCE(cew.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, cew.temp_mean))
    ) > 5 as needs_review,

    CASE
        WHEN GREATEST(
            ABS(COALESCE(ceg.temp_mean, cew.temp_mean) - COALESCE(cew.temp_mean, ceg.temp_mean)),
            ABS(COALESCE(ceg.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, ceg.temp_mean)),
            ABS(COALESCE(cew.temp_mean, cee.temp_mean) - COALESCE(cee.temp_mean, cew.temp_mean))
        ) > 5 THEN 'temp_mean difference > 5C between sources'
        ELSE NULL
    END as review_reason

FROM species s
LEFT JOIN climate_envelope_gbif ceg ON s.id = ceg.species_id
LEFT JOIN climate_envelope_wcvp cew ON s.id = cew.species_id
LEFT JOIN climate_envelope_ecoregion cee ON s.id = cee.species_id
WHERE ceg.species_id IS NOT NULL
   OR cew.species_id IS NOT NULL
   OR cee.species_id IS NOT NULL
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
    temp_range_discrepancy = EXCLUDED.temp_range_discrepancy,
    precip_mean_discrepancy = EXCLUDED.precip_mean_discrepancy,
    overall_agreement = EXCLUDED.overall_agreement,
    needs_review = EXCLUDED.needs_review,
    review_reason = EXCLUDED.review_reason,
    updated_at = CURRENT_TIMESTAMP;

-- Report 1: Source coverage summary
\echo ''
\echo '=== Source Coverage Summary ==='
SELECT
    n_sources,
    COUNT(*) as species_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM climate_envelope_analysis
GROUP BY n_sources
ORDER BY n_sources;

-- Report 2: Agreement distribution
\echo ''
\echo '=== Agreement Distribution ==='
SELECT
    overall_agreement,
    COUNT(*) as species_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct,
    ROUND(AVG(temp_mean_discrepancy), 2) as avg_temp_discrepancy
FROM climate_envelope_analysis
GROUP BY overall_agreement
ORDER BY
    CASE overall_agreement
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
        WHEN 'single' THEN 4
    END;

-- Report 3: Best source distribution
\echo ''
\echo '=== Best Source Selection ==='
SELECT
    best_source,
    COUNT(*) as species_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM climate_envelope_analysis
GROUP BY best_source
ORDER BY species_count DESC;

-- Report 4: Species needing review
\echo ''
\echo '=== Species Needing Review (Top 20 by Discrepancy) ==='
SELECT
    s.canonical_name,
    s.family,
    su.growth_form,
    cea.temp_mean_discrepancy,
    ceg.temp_mean as gbif_temp,
    cew.temp_mean as wcvp_temp,
    cee.temp_mean as ecoregion_temp,
    cea.review_reason
FROM climate_envelope_analysis cea
JOIN species s ON cea.species_id = s.id
LEFT JOIN species_unified su ON s.id = su.species_id
LEFT JOIN climate_envelope_gbif ceg ON cea.species_id = ceg.species_id
LEFT JOIN climate_envelope_wcvp cew ON cea.species_id = cew.species_id
LEFT JOIN climate_envelope_ecoregion cee ON cea.species_id = cee.species_id
WHERE cea.needs_review = TRUE
ORDER BY cea.temp_mean_discrepancy DESC
LIMIT 20;

-- Report 5: GBIF vs TreeGOER comparison (trees only)
\echo ''
\echo '=== GBIF vs TreeGOER Comparison (Trees with Both Sources) ==='
SELECT
    COUNT(*) as species_with_both,
    ROUND(AVG(ABS(ceg.temp_mean - cee.temp_mean))::numeric, 2) as avg_temp_diff,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ABS(ceg.temp_mean - cee.temp_mean))::numeric, 2) as median_temp_diff,
    COUNT(*) FILTER (WHERE ABS(ceg.temp_mean - cee.temp_mean) <= 2) as within_2c,
    COUNT(*) FILTER (WHERE ABS(ceg.temp_mean - cee.temp_mean) <= 5) as within_5c,
    COUNT(*) FILTER (WHERE ABS(ceg.temp_mean - cee.temp_mean) > 5) as beyond_5c
FROM climate_envelope_gbif ceg
JOIN climate_envelope_ecoregion cee ON ceg.species_id = cee.species_id
WHERE ceg.temp_mean IS NOT NULL AND cee.temp_mean IS NOT NULL;

-- Report 6: Coverage by growth form
\echo ''
\echo '=== Coverage by Growth Form ==='
SELECT
    COALESCE(su.growth_form, 'unknown') as growth_form,
    COUNT(DISTINCT su.species_id) as total_species,
    COUNT(DISTINCT cea.species_id) FILTER (WHERE cea.has_gbif) as with_gbif,
    COUNT(DISTINCT cea.species_id) FILTER (WHERE cea.has_wcvp) as with_wcvp,
    COUNT(DISTINCT cea.species_id) FILTER (WHERE cea.has_ecoregion) as with_ecoregion,
    COUNT(DISTINCT cea.species_id) FILTER (WHERE cea.n_sources >= 2) as multi_source,
    ROUND(100.0 * COUNT(DISTINCT cea.species_id) / NULLIF(COUNT(DISTINCT su.species_id), 0), 1) as coverage_pct
FROM species_unified su
LEFT JOIN climate_envelope_analysis cea ON su.species_id = cea.species_id
GROUP BY su.growth_form
ORDER BY total_species DESC;

-- Summary
\echo ''
\echo '=== Analysis Complete ==='
SELECT
    COUNT(*) as total_analyzed,
    COUNT(*) FILTER (WHERE needs_review) as needs_review,
    COUNT(*) FILTER (WHERE n_sources >= 2) as multi_source,
    COUNT(*) FILTER (WHERE overall_agreement = 'high') as high_agreement
FROM climate_envelope_analysis;
