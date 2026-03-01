-- Audit: Data conflicts between sources
-- Run this to identify where different sources disagree

-- 1. Growth form conflicts (different sources → different growth forms)
SELECT
    s.canonical_name,
    string_agg(st.source || ':' || st.growth_form, ' | ' ORDER BY COALESCE(sp.priority, 99)) as values_by_priority,
    su.growth_form as unified_value,
    su.growth_form_source as chosen_source,
    COUNT(DISTINCT st.growth_form) as n_distinct_values
FROM species_traits st
JOIN species s ON st.species_id = s.id
LEFT JOIN species_unified su ON s.id = su.species_id
LEFT JOIN source_priority sp ON sp.attribute = 'growth_form' AND sp.source = st.source
WHERE st.growth_form IS NOT NULL
GROUP BY s.id, s.canonical_name, su.growth_form, su.growth_form_source
HAVING COUNT(DISTINCT st.growth_form) > 1
ORDER BY COUNT(DISTINCT st.growth_form) DESC, s.canonical_name
LIMIT 50;

-- 2. Threat status conflicts
SELECT
    s.canonical_name,
    string_agg(st.source || ':' || st.threat_status, ' | ' ORDER BY COALESCE(sp.priority, 99)) as values_by_priority,
    su.threat_status as unified_value,
    COUNT(DISTINCT st.threat_status) as n_distinct_values
FROM species_traits st
JOIN species s ON st.species_id = s.id
LEFT JOIN species_unified su ON s.id = su.species_id
LEFT JOIN source_priority sp ON sp.attribute = 'threat_status' AND sp.source = st.source
WHERE st.threat_status IS NOT NULL
GROUP BY s.id, s.canonical_name, su.threat_status
HAVING COUNT(DISTINCT st.threat_status) > 1
ORDER BY COUNT(DISTINCT st.threat_status) DESC
LIMIT 50;

-- 3. Max height conflicts (>30% difference between sources)
SELECT
    s.canonical_name,
    string_agg(st.source || ':' || st.max_height_m::text, ' | ' ORDER BY COALESCE(sp.priority, 99)) as values_by_priority,
    su.max_height_m as unified_value,
    su.height_source as chosen_source,
    MAX(st.max_height_m) - MIN(st.max_height_m) as height_diff,
    ROUND((MAX(st.max_height_m) - MIN(st.max_height_m)) / NULLIF(AVG(st.max_height_m), 0) * 100, 1) as pct_diff
FROM species_traits st
JOIN species s ON st.species_id = s.id
LEFT JOIN species_unified su ON s.id = su.species_id
LEFT JOIN source_priority sp ON sp.attribute = 'max_height_m' AND sp.source = st.source
WHERE st.max_height_m IS NOT NULL
GROUP BY s.id, s.canonical_name, su.max_height_m, su.height_source
HAVING COUNT(DISTINCT st.max_height_m) > 1
  AND (MAX(st.max_height_m) - MIN(st.max_height_m)) / NULLIF(AVG(st.max_height_m), 0) > 0.3
ORDER BY pct_diff DESC
LIMIT 50;

-- 4. Summary statistics
SELECT 'growth_form conflicts' as metric,
       COUNT(*) as species_count
FROM (
    SELECT species_id FROM species_traits
    WHERE growth_form IS NOT NULL
    GROUP BY species_id HAVING COUNT(DISTINCT growth_form) > 1
) sub
UNION ALL
SELECT 'threat_status conflicts',
       COUNT(*)
FROM (
    SELECT species_id FROM species_traits
    WHERE threat_status IS NOT NULL
    GROUP BY species_id HAVING COUNT(DISTINCT threat_status) > 1
) sub
UNION ALL
SELECT 'height conflicts (>30% diff)',
       COUNT(*)
FROM (
    SELECT species_id FROM species_traits
    WHERE max_height_m IS NOT NULL
    GROUP BY species_id
    HAVING COUNT(DISTINCT max_height_m) > 1
      AND (MAX(max_height_m) - MIN(max_height_m)) / NULLIF(AVG(max_height_m), 0) > 0.3
) sub;

-- 5. Source priority table (current config)
SELECT * FROM source_priority ORDER BY attribute, priority;
