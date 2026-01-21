-- Migration: 002_unified_schema.sql
-- Description: Create optimized tables for spatial queries, eliminating unnecessary JOINs
-- Created: 2026-01-19
-- Author: Stickybit <dev@stickybit.com.br>

-- =============================================
-- PROBLEMA ATUAL
-- =============================================
-- Query para árvores de São Paulo:
-- species (448K) → JOIN wcvp_distribution (2M) → JOIN species_traits (555K) → JOIN tdwg_level3
-- via wcvp_id (string) e múltiplos registros por espécie (wcvp, gift, treegoer, reflora)
-- ~444ms por query
--
-- SOLUÇÃO:
-- 1. species_unified: traits consolidados com prioridade
-- 2. species_regions: distribuição direta sem JOINs em wcvp_distribution
-- 3. species_geometry: polígonos PostGIS pré-calculados

-- =============================================
-- 1. TABELA species_unified - Traits Consolidados
-- =============================================
-- Consolida múltiplos registros de species_traits em um único registro por espécie
-- Prioridade de fontes: gift > reflora > wcvp > treegoer
-- GIFT é prioritário por usar definições mais consistentes (liana vs vine)
-- e seguir a lógica Climber.R de Renata (trait_1.2.2 + trait_1.4.2)

CREATE TABLE IF NOT EXISTS species_unified (
    species_id INTEGER PRIMARY KEY REFERENCES species(id) ON DELETE CASCADE,

    -- Traits consolidados (prioridade: gift > reflora > wcvp > treegoer)
    growth_form VARCHAR(50),
    growth_form_source VARCHAR(20),

    max_height_m DECIMAL(10,2),
    height_source VARCHAR(20),

    woodiness VARCHAR(50),
    nitrogen_fixer BOOLEAN,
    dispersal_syndrome VARCHAR(100),
    deciduousness VARCHAR(50),

    -- Flags para queries rápidas (STORED = calculado uma vez e armazenado)
    is_tree BOOLEAN GENERATED ALWAYS AS (growth_form = 'tree') STORED,
    is_shrub BOOLEAN GENERATED ALWAYS AS (growth_form = 'shrub') STORED,
    is_climber BOOLEAN GENERATED ALWAYS AS (growth_form IN ('climber', 'liana', 'vine')) STORED,
    is_herb BOOLEAN GENERATED ALWAYS AS (growth_form IN ('herb', 'forb')) STORED,
    is_palm BOOLEAN GENERATED ALWAYS AS (growth_form = 'palm') STORED,
    is_native_brazil BOOLEAN DEFAULT FALSE,

    -- Metadados
    sources_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE species_unified IS 'Traits consolidados de múltiplas fontes com prioridade: gift > reflora > wcvp > treegoer';
COMMENT ON COLUMN species_unified.growth_form_source IS 'Fonte do growth_form: reflora, wcvp, gift, ou treegoer';
COMMENT ON COLUMN species_unified.is_tree IS 'Flag calculada automaticamente para queries rápidas de árvores';

-- Índices parciais para queries rápidas (apenas onde TRUE)
CREATE INDEX IF NOT EXISTS idx_unified_tree ON species_unified(species_id) WHERE is_tree = TRUE;
CREATE INDEX IF NOT EXISTS idx_unified_shrub ON species_unified(species_id) WHERE is_shrub = TRUE;
CREATE INDEX IF NOT EXISTS idx_unified_climber ON species_unified(species_id) WHERE is_climber = TRUE;
CREATE INDEX IF NOT EXISTS idx_unified_herb ON species_unified(species_id) WHERE is_herb = TRUE;
CREATE INDEX IF NOT EXISTS idx_unified_palm ON species_unified(species_id) WHERE is_palm = TRUE;
CREATE INDEX IF NOT EXISTS idx_unified_growth ON species_unified(growth_form);
CREATE INDEX IF NOT EXISTS idx_unified_native_br ON species_unified(species_id) WHERE is_native_brazil = TRUE;

-- =============================================
-- 2. TABELA species_regions - Distribuição Geográfica Direta
-- =============================================
-- Substitui o padrão de JOIN: species → wcvp_distribution (via wcvp_id string)
-- Por: species → species_regions (via species_id integer)

CREATE TABLE IF NOT EXISTS species_regions (
    id SERIAL PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    tdwg_code VARCHAR(10) NOT NULL,

    -- Status de ocorrência
    is_native BOOLEAN DEFAULT TRUE,
    is_endemic BOOLEAN DEFAULT FALSE,
    is_introduced BOOLEAN DEFAULT FALSE,

    -- Fonte do dado
    source VARCHAR(20), -- 'wcvp', 'reflora', 'gbif'

    -- Constraint de unicidade
    UNIQUE(species_id, tdwg_code)
);

COMMENT ON TABLE species_regions IS 'Distribuição geográfica por código TDWG Level 3 - elimina JOINs com wcvp_distribution';
COMMENT ON COLUMN species_regions.is_native IS 'Espécie é nativa nesta região';
COMMENT ON COLUMN species_regions.is_endemic IS 'Espécie é endêmica (APENAS nesta região)';

-- Índices para queries de filtragem geográfica
CREATE INDEX IF NOT EXISTS idx_regions_tdwg ON species_regions(tdwg_code);
CREATE INDEX IF NOT EXISTS idx_regions_species ON species_regions(species_id);
CREATE INDEX IF NOT EXISTS idx_regions_native ON species_regions(tdwg_code) WHERE is_native = TRUE;
CREATE INDEX IF NOT EXISTS idx_regions_endemic ON species_regions(tdwg_code) WHERE is_endemic = TRUE;
CREATE INDEX IF NOT EXISTS idx_regions_introduced ON species_regions(tdwg_code) WHERE is_introduced = TRUE;

-- Índice composto para a query mais comum
CREATE INDEX IF NOT EXISTS idx_regions_tdwg_species ON species_regions(tdwg_code, species_id);

-- =============================================
-- 3. TABELA species_geometry - Polígonos de Range (PostGIS)
-- =============================================
-- Armazena a união dos polígonos TDWG onde cada espécie ocorre
-- Permite queries espaciais diretas: ST_Contains(native_range, ponto)

CREATE TABLE IF NOT EXISTS species_geometry (
    species_id INTEGER PRIMARY KEY REFERENCES species(id) ON DELETE CASCADE,

    -- União dos polígonos TDWG onde a espécie ocorre
    native_range GEOMETRY(MultiPolygon, 4326),  -- apenas nativas
    full_range GEOMETRY(MultiPolygon, 4326),    -- inclui introduzidas

    -- Bounding box para queries rápidas
    bbox GEOMETRY(Polygon, 4326),

    -- Centroid para visualização em mapas
    centroid GEOMETRY(Point, 4326),

    -- Área total em km²
    native_area_km2 DECIMAL(12,2),
    full_area_km2 DECIMAL(12,2),

    -- Número de regiões
    native_regions_count INTEGER DEFAULT 0,
    full_regions_count INTEGER DEFAULT 0,

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE species_geometry IS 'Geometrias PostGIS pré-calculadas para ranges de espécies';
COMMENT ON COLUMN species_geometry.native_range IS 'União dos polígonos TDWG onde a espécie é nativa';
COMMENT ON COLUMN species_geometry.full_range IS 'União dos polígonos TDWG (nativas + introduzidas)';
COMMENT ON COLUMN species_geometry.bbox IS 'Bounding box para filtro inicial rápido';

-- Índices espaciais GIST para queries PostGIS
CREATE INDEX IF NOT EXISTS idx_species_geom_native ON species_geometry USING GIST(native_range);
CREATE INDEX IF NOT EXISTS idx_species_geom_full ON species_geometry USING GIST(full_range);
CREATE INDEX IF NOT EXISTS idx_species_geom_bbox ON species_geometry USING GIST(bbox);
CREATE INDEX IF NOT EXISTS idx_species_geom_centroid ON species_geometry USING GIST(centroid);

-- =============================================
-- FUNÇÕES AUXILIARES
-- =============================================

-- Função para determinar a fonte prioritária de um trait
-- Prioridade: gift > reflora > wcvp > treegoer
CREATE OR REPLACE FUNCTION get_priority_source(
    reflora_value TEXT,
    wcvp_value TEXT,
    gift_value TEXT,
    treegoer_value TEXT
) RETURNS TEXT AS $$
BEGIN
    IF gift_value IS NOT NULL AND gift_value != '' THEN
        RETURN 'gift';
    ELSIF reflora_value IS NOT NULL AND reflora_value != '' THEN
        RETURN 'reflora';
    ELSIF wcvp_value IS NOT NULL AND wcvp_value != '' THEN
        RETURN 'wcvp';
    ELSIF treegoer_value IS NOT NULL AND treegoer_value != '' THEN
        RETURN 'treegoer';
    ELSE
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Função para obter o valor prioritário de um trait
-- Prioridade: gift > reflora > wcvp > treegoer
CREATE OR REPLACE FUNCTION get_priority_value(
    reflora_value TEXT,
    wcvp_value TEXT,
    gift_value TEXT,
    treegoer_value TEXT
) RETURNS TEXT AS $$
BEGIN
    RETURN COALESCE(
        NULLIF(gift_value, ''),
        NULLIF(reflora_value, ''),
        NULLIF(wcvp_value, ''),
        NULLIF(treegoer_value, '')
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger para atualizar last_updated automaticamente
CREATE OR REPLACE FUNCTION update_unified_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_unified_updated
    BEFORE UPDATE ON species_unified
    FOR EACH ROW
    EXECUTE FUNCTION update_unified_timestamp();

CREATE TRIGGER trigger_geometry_updated
    BEFORE UPDATE ON species_geometry
    FOR EACH ROW
    EXECUTE FUNCTION update_unified_timestamp();

-- =============================================
-- VIEWS PARA COMPATIBILIDADE
-- =============================================

-- View que replica o comportamento antigo para queries existentes
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

COMMENT ON VIEW v_species_with_regions IS 'View consolidada para compatibilidade com queries antigas';

-- =============================================
-- QUERY DE EXEMPLO OTIMIZADA
-- =============================================
-- ANTES: 4 JOINs, ~444ms
-- SELECT COUNT(DISTINCT s.id)
-- FROM species s
-- JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
-- JOIN species_traits st ON s.id = st.species_id
-- WHERE wd.tdwg_code = 'BZL' AND st.growth_form = 'tree';

-- DEPOIS: 2 JOINs, ~50ms esperado
-- SELECT COUNT(*)
-- FROM species_unified su
-- JOIN species_regions sr ON su.species_id = sr.species_id
-- WHERE sr.tdwg_code = 'BZL' AND su.is_tree = TRUE;

-- OU usando PostGIS diretamente (sem precisar saber o código TDWG):
-- SELECT COUNT(*)
-- FROM species_unified su
-- JOIN species_geometry sg ON su.species_id = sg.species_id
-- WHERE su.is_tree = TRUE
--   AND ST_Contains(sg.native_range, ST_SetSRID(ST_Point(-46.6333, -23.5505), 4326));
