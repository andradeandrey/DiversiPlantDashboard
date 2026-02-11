-- Migration: 012_update_growth_form_booleans.sql
-- Description: Update GENERATED ALWAYS columns on species_unified to reflect
--              the 11 standardized growth form values from Renata's mapping.
--              Old: tree, shrub, climber/liana/vine, herb/forb, palm
--              New: tree, shrub+subshrub, liana+vine+scrambler, forb+graminoid, palm
-- Created: 2026-02-09
-- Author: Stickybit <dev@stickybit.com.br>

-- =============================================
-- Drop dependent views (will be recreated below)
-- =============================================
DROP VIEW IF EXISTS v_species_with_regions;

-- =============================================
-- Drop existing partial indices (depend on generated columns)
-- =============================================
DROP INDEX IF EXISTS idx_unified_tree;
DROP INDEX IF EXISTS idx_unified_shrub;
DROP INDEX IF EXISTS idx_unified_climber;
DROP INDEX IF EXISTS idx_unified_herb;
DROP INDEX IF EXISTS idx_unified_palm;

-- =============================================
-- Drop existing GENERATED ALWAYS columns
-- (Cannot ALTER generated columns, must drop and recreate)
-- =============================================
ALTER TABLE species_unified
  DROP COLUMN IF EXISTS is_tree,
  DROP COLUMN IF EXISTS is_shrub,
  DROP COLUMN IF EXISTS is_climber,
  DROP COLUMN IF EXISTS is_herb,
  DROP COLUMN IF EXISTS is_palm;

-- =============================================
-- Recreate with updated definitions for 11 growth forms
-- =============================================
ALTER TABLE species_unified
  ADD COLUMN is_tree BOOLEAN GENERATED ALWAYS AS (growth_form = 'tree') STORED,
  ADD COLUMN is_shrub BOOLEAN GENERATED ALWAYS AS (growth_form IN ('shrub', 'subshrub')) STORED,
  ADD COLUMN is_climber BOOLEAN GENERATED ALWAYS AS (growth_form IN ('liana', 'vine', 'scrambler')) STORED,
  ADD COLUMN is_herb BOOLEAN GENERATED ALWAYS AS (growth_form IN ('forb', 'graminoid')) STORED,
  ADD COLUMN is_palm BOOLEAN GENERATED ALWAYS AS (growth_form = 'palm') STORED;

-- =============================================
-- Recreate partial indices
-- =============================================
CREATE INDEX idx_unified_tree ON species_unified(species_id) WHERE is_tree = TRUE;
CREATE INDEX idx_unified_shrub ON species_unified(species_id) WHERE is_shrub = TRUE;
CREATE INDEX idx_unified_climber ON species_unified(species_id) WHERE is_climber = TRUE;
CREATE INDEX idx_unified_herb ON species_unified(species_id) WHERE is_herb = TRUE;
CREATE INDEX idx_unified_palm ON species_unified(species_id) WHERE is_palm = TRUE;

-- =============================================
-- Recreate v_species_with_regions view
-- =============================================
CREATE OR REPLACE VIEW v_species_with_regions AS
SELECT
    s.id,
    s.canonical_name,
    s.genus,
    s.family,
    s.wcvp_id,
    su.growth_form,
    su.max_height_m,
    su.is_tree,
    su.is_shrub,
    su.is_native_brazil,
    sr.tdwg_code,
    sr.is_native,
    sr.is_endemic,
    sr.is_introduced,
    t.level3_name as region_name
FROM species s
LEFT JOIN species_unified su ON s.id = su.species_id
LEFT JOIN species_regions sr ON s.id = sr.species_id
LEFT JOIN tdwg_level3 t ON sr.tdwg_code = t.level3_code;
