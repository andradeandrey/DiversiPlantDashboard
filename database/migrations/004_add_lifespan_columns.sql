-- Migration: 004_add_lifespan_columns.sql
-- Description: Add lifespan and threat status columns for TRY and Practitioners data
-- Created: 2026-01-21
-- Author: Stickybit <dev@stickybit.com.br>

-- =============================================
-- NOVOS DADOS A INTEGRAR
-- =============================================
-- TRY: longevidade em anos (~4.4K espécies)
-- Practitioners: threat_status, establishment, habitat (~3.6K espécies BR)

BEGIN;

-- =============================================
-- 1. ADICIONAR COLUNAS A species_traits
-- =============================================

-- Lifespan em anos (de TRY)
ALTER TABLE species_traits
ADD COLUMN IF NOT EXISTS lifespan_years DECIMAL(10,2);

-- Threat status (de Practitioners, formato IUCN: CR, EN, VU, NT, LC)
ALTER TABLE species_traits
ADD COLUMN IF NOT EXISTS threat_status VARCHAR(50);

-- Establishment (endemic, native, introduced)
ALTER TABLE species_traits
ADD COLUMN IF NOT EXISTS establishment VARCHAR(50);

-- Habitat (descrição do habitat)
ALTER TABLE species_traits
ADD COLUMN IF NOT EXISTS habitat TEXT;

COMMENT ON COLUMN species_traits.lifespan_years IS 'Longevidade máxima da planta em anos (fonte: TRY)';
COMMENT ON COLUMN species_traits.threat_status IS 'Status de ameaça IUCN: CR, EN, VU, NT, LC (fonte: Practitioners)';
COMMENT ON COLUMN species_traits.establishment IS 'Tipo de ocorrência: endemic, native, introduced (fonte: Practitioners)';
COMMENT ON COLUMN species_traits.habitat IS 'Descrição do habitat (fonte: Practitioners)';

-- =============================================
-- 2. ADICIONAR COLUNAS A species_unified
-- =============================================

-- Lifespan consolidado
ALTER TABLE species_unified
ADD COLUMN IF NOT EXISTS lifespan_years DECIMAL(10,2);

ALTER TABLE species_unified
ADD COLUMN IF NOT EXISTS lifespan_source VARCHAR(20);

-- Threat status consolidado
ALTER TABLE species_unified
ADD COLUMN IF NOT EXISTS threat_status VARCHAR(50);

ALTER TABLE species_unified
ADD COLUMN IF NOT EXISTS threat_status_source VARCHAR(20);

COMMENT ON COLUMN species_unified.lifespan_years IS 'Longevidade consolidada (prioridade: try > practitioners)';
COMMENT ON COLUMN species_unified.lifespan_source IS 'Fonte do lifespan: try ou practitioners';
COMMENT ON COLUMN species_unified.threat_status IS 'Status de ameaça consolidado (prioridade: practitioners > iucn)';
COMMENT ON COLUMN species_unified.threat_status_source IS 'Fonte do threat_status: practitioners ou iucn';

-- =============================================
-- 3. ÍNDICES PARA QUERIES RÁPIDAS
-- =============================================

-- Índice para espécies ameaçadas
CREATE INDEX IF NOT EXISTS idx_unified_threatened
ON species_unified(species_id)
WHERE threat_status IN ('CR', 'EN', 'VU');

-- Índice para espécies longevas (>50 anos)
CREATE INDEX IF NOT EXISTS idx_unified_longlived
ON species_unified(species_id)
WHERE lifespan_years > 50;

-- Índice para pesquisa por threat_status
CREATE INDEX IF NOT EXISTS idx_unified_threat_status
ON species_unified(threat_status)
WHERE threat_status IS NOT NULL;

-- =============================================
-- 4. REGISTRAR NOVOS CRAWLERS
-- =============================================

INSERT INTO crawler_status (crawler_name, status)
VALUES
    ('try', 'idle'),
    ('practitioners', 'idle')
ON CONFLICT (crawler_name) DO NOTHING;

COMMIT;

-- =============================================
-- VERIFICAÇÃO
-- =============================================
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'species_unified'
-- AND column_name IN ('lifespan_years', 'threat_status');
