-- Migration 014: Fix residual non-standard growth_form values in species_unified
-- These are Portuguese compound forms from legacy practitioner data that were not
-- caught by the initial reprocessing (migration 012).

-- liana/volúvel/trepadeira → liana
UPDATE species_unified SET growth_form = 'liana'
WHERE growth_form ILIKE '%trepadeira%'
   OR growth_form ILIKE '%volúvel%'
   OR growth_form ILIKE '%voluvel%';

-- arbusto|árvore, arbusto|arvore → tree (conservative: if tree is an option, use tree)
UPDATE species_unified SET growth_form = 'tree'
WHERE growth_form ~ '^arbusto[|/].*[aá]rvore'
   OR growth_form ~ '[aá]rvore[|/].*arbusto';

-- arbusto|subarbusto|suculenta → shrub
UPDATE species_unified SET growth_form = 'shrub'
WHERE growth_form ILIKE '%arbusto%subarbusto%suculenta%'
   OR growth_form ILIKE '%subarbusto%arbusto%';

-- succulent (standalone) → other
UPDATE species_unified SET growth_form = 'other'
WHERE growth_form ILIKE 'succulent%'
   OR growth_form ILIKE 'suculenta%';

-- Catch-all: any remaining values with Portuguese plant terms
UPDATE species_unified SET growth_form = 'shrub'
WHERE growth_form ILIKE '%arbusto%'
  AND growth_form NOT IN ('graminoid','forb','subshrub','shrub','tree','scrambler','vine','liana','palm','bamboo','other');

-- Verify: should return 0 rows
-- SELECT DISTINCT growth_form, COUNT(*)
-- FROM species_unified
-- WHERE growth_form NOT IN ('graminoid','forb','subshrub','shrub','tree','scrambler','vine','liana','palm','bamboo','other')
--   AND growth_form IS NOT NULL
-- GROUP BY growth_form;
