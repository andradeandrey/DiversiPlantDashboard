-- Migration: 003_populate_unified.sql
-- Description: Populate unified tables from existing data
-- Created: 2026-01-19
-- Author: Stickybit <dev@stickybit.com.br>
-- Dependencies: 002_unified_schema.sql

-- =============================================
-- PASSO 0: Verificar pré-requisitos
-- =============================================
DO $$
BEGIN
    -- Verificar se PostGIS está habilitado
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
        RAISE EXCEPTION 'PostGIS extension is required. Run: CREATE EXTENSION postgis;';
    END IF;

    -- Verificar se tabelas base existem
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'species') THEN
        RAISE EXCEPTION 'Table species does not exist';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'species_traits') THEN
        RAISE EXCEPTION 'Table species_traits does not exist';
    END IF;

    RAISE NOTICE 'Prerequisites check passed';
END $$;

-- =============================================
-- PASSO 1: Popular species_regions a partir de wcvp_distribution
-- =============================================
-- wcvp_distribution contém distribuição via JOIN em s.wcvp_id = wd.taxon_id
-- Criamos registros diretos via species_id para eliminar o JOIN

DO $$
DECLARE
    v_count INTEGER;
    v_has_endemic BOOLEAN;
BEGIN
    RAISE NOTICE 'Step 1: Populating species_regions from wcvp_distribution...';

    -- Verificar se wcvp_distribution existe
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'wcvp_distribution') THEN

        -- Verificar se a coluna endemic existe (estrutura nova vs antiga)
        SELECT EXISTS(
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'wcvp_distribution' AND column_name = 'endemic'
        ) INTO v_has_endemic;

        IF v_has_endemic THEN
            -- Estrutura nova com colunas endemic/introduced
            INSERT INTO species_regions (species_id, tdwg_code, is_native, is_endemic, is_introduced, source)
            SELECT DISTINCT
                s.id,
                wd.tdwg_code,
                CASE
                    WHEN wd.establishment_means = 'native' THEN TRUE
                    WHEN wd.establishment_means IS NULL THEN TRUE
                    ELSE FALSE
                END as is_native,
                COALESCE(wd.endemic::boolean, FALSE) as is_endemic,
                CASE
                    WHEN wd.establishment_means = 'introduced' THEN TRUE
                    ELSE FALSE
                END as is_introduced,
                'wcvp'
            FROM species s
            JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
            WHERE wd.tdwg_code IS NOT NULL
              AND LENGTH(TRIM(wd.tdwg_code)) > 0
            ON CONFLICT (species_id, tdwg_code) DO UPDATE SET
                is_native = EXCLUDED.is_native,
                is_endemic = EXCLUDED.is_endemic,
                is_introduced = EXCLUDED.is_introduced,
                source = EXCLUDED.source;
        ELSE
            -- Estrutura antiga apenas com establishment_means
            INSERT INTO species_regions (species_id, tdwg_code, is_native, is_endemic, is_introduced, source)
            SELECT DISTINCT
                s.id,
                wd.tdwg_code,
                CASE
                    WHEN LOWER(wd.establishment_means) LIKE '%native%' THEN TRUE
                    WHEN LOWER(wd.establishment_means) LIKE '%introduced%' THEN FALSE
                    WHEN wd.establishment_means IS NULL THEN TRUE
                    ELSE TRUE
                END as is_native,
                FALSE as is_endemic,  -- não temos esta informação
                CASE
                    WHEN LOWER(wd.establishment_means) LIKE '%introduced%' THEN TRUE
                    WHEN LOWER(wd.establishment_means) LIKE '%cultivated%' THEN TRUE
                    ELSE FALSE
                END as is_introduced,
                'wcvp'
            FROM species s
            JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
            WHERE wd.tdwg_code IS NOT NULL
              AND LENGTH(TRIM(wd.tdwg_code)) > 0
            ON CONFLICT (species_id, tdwg_code) DO UPDATE SET
                is_native = EXCLUDED.is_native,
                is_introduced = EXCLUDED.is_introduced,
                source = EXCLUDED.source;
        END IF;

        GET DIAGNOSTICS v_count = ROW_COUNT;
        RAISE NOTICE 'Inserted/updated % records from wcvp_distribution', v_count;

    ELSE
        RAISE NOTICE 'wcvp_distribution table not found, skipping...';
    END IF;

    -- Também popular a partir de species_distribution existente (se houver dados)
    IF EXISTS (SELECT 1 FROM species_distribution LIMIT 1) THEN

        INSERT INTO species_regions (species_id, tdwg_code, is_native, is_endemic, is_introduced, source)
        SELECT
            sd.species_id,
            sd.tdwg_code,
            COALESCE(sd.native, TRUE),
            COALESCE(sd.endemic, FALSE),
            COALESCE(sd.introduced, FALSE),
            COALESCE(sd.source, 'legacy')
        FROM species_distribution sd
        WHERE sd.tdwg_code IS NOT NULL
        ON CONFLICT (species_id, tdwg_code) DO NOTHING;  -- não sobrescrever WCVP

        GET DIAGNOSTICS v_count = ROW_COUNT;
        RAISE NOTICE 'Inserted % records from species_distribution', v_count;

    END IF;

END $$;

-- =============================================
-- PASSO 2: Popular species_unified com traits consolidados (OTIMIZADO)
-- =============================================
-- Prioridade de fontes: gift > reflora > wcvp > treegoer
-- GIFT é prioritário por usar definições mais consistentes (liana vs vine)
-- e seguir a lógica Climber.R de Renata (trait_1.2.2 + trait_1.4.2)
-- Usa CTEs ao invés de subqueries correlacionadas para performance O(n) vs O(n*m)

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    RAISE NOTICE 'Step 2: Populating species_unified with consolidated traits...';
    RAISE NOTICE 'Using optimized CTEs for better performance...';

    -- Inserir species_unified usando CTEs otimizadas
    WITH
    -- Adicionar prioridade às fontes
    traits_with_priority AS (
        SELECT
            species_id,
            source,
            growth_form,
            max_height_m,
            woodiness,
            nitrogen_fixer,
            dispersal_syndrome,
            deciduousness,
            lifespan_years,      -- TRY data
            threat_status,       -- Practitioners data
            CASE source
                WHEN 'gift' THEN 1       -- Prioridade 1: GIFT (liana/vine distinction)
                WHEN 'reflora' THEN 2    -- Prioridade 2: REFLORA (espécies BR)
                WHEN 'wcvp' THEN 3       -- Prioridade 3: WCVP (taxonomia referência)
                WHEN 'treegoer' THEN 4   -- Prioridade 4: TreeGOER (validação árvores)
                WHEN 'practitioners' THEN 5 -- Prioridade 5: Practitioners (threat/habitat)
                WHEN 'try' THEN 6        -- Prioridade 6: TRY (lifespan)
                ELSE 7
            END as source_priority
        FROM species_traits
        WHERE source IS NOT NULL
    ),

    -- Melhor growth_form por prioridade
    best_growth_form AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            growth_form,
            source as growth_form_source
        FROM traits_with_priority
        WHERE growth_form IS NOT NULL
        ORDER BY species_id, source_priority
    ),

    -- Melhor max_height por prioridade
    best_height AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            max_height_m,
            source as height_source
        FROM traits_with_priority
        WHERE max_height_m IS NOT NULL
        ORDER BY species_id, source_priority
    ),

    -- Primeiro woodiness disponível
    best_woodiness AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            woodiness
        FROM traits_with_priority
        WHERE woodiness IS NOT NULL
        ORDER BY species_id, source_priority
    ),

    -- Primeiro nitrogen_fixer disponível
    best_nitrogen AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            nitrogen_fixer
        FROM traits_with_priority
        WHERE nitrogen_fixer IS NOT NULL
        ORDER BY species_id, source_priority
    ),

    -- Primeiro dispersal_syndrome disponível
    best_dispersal AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            dispersal_syndrome
        FROM traits_with_priority
        WHERE dispersal_syndrome IS NOT NULL
        ORDER BY species_id, source_priority
    ),

    -- Primeiro deciduousness disponível
    best_deciduousness AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            deciduousness
        FROM traits_with_priority
        WHERE deciduousness IS NOT NULL
        ORDER BY species_id, source_priority
    ),

    -- Contagem de fontes por espécie
    sources_count AS (
        SELECT
            species_id,
            COUNT(DISTINCT source) as cnt
        FROM traits_with_priority
        GROUP BY species_id
    ),

    -- Melhor lifespan por prioridade (try > practitioners)
    best_lifespan AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            lifespan_years,
            source as lifespan_source
        FROM traits_with_priority
        WHERE lifespan_years IS NOT NULL
        ORDER BY species_id,
            CASE source
                WHEN 'try' THEN 1
                WHEN 'practitioners' THEN 2
                ELSE 10
            END
    ),

    -- Melhor threat_status por prioridade (practitioners > iucn)
    best_threat_status AS (
        SELECT DISTINCT ON (species_id)
            species_id,
            threat_status,
            source as threat_status_source
        FROM traits_with_priority
        WHERE threat_status IS NOT NULL
        ORDER BY species_id,
            CASE source
                WHEN 'practitioners' THEN 1
                WHEN 'iucn' THEN 2
                ELSE 10
            END
    ),

    -- Espécies nativas do Brasil
    native_brazil AS (
        SELECT DISTINCT species_id
        FROM species_regions
        WHERE tdwg_code LIKE 'BZ%' AND is_native = TRUE
    ),

    -- Todas as espécies com traits
    species_with_traits AS (
        SELECT DISTINCT species_id FROM traits_with_priority
    )

    INSERT INTO species_unified (
        species_id,
        growth_form,
        growth_form_source,
        max_height_m,
        height_source,
        woodiness,
        nitrogen_fixer,
        dispersal_syndrome,
        deciduousness,
        lifespan_years,
        lifespan_source,
        threat_status,
        threat_status_source,
        is_native_brazil,
        sources_count
    )
    SELECT
        swt.species_id,
        bgf.growth_form,
        bgf.growth_form_source,
        bh.max_height_m,
        bh.height_source,
        bw.woodiness,
        bn.nitrogen_fixer,
        bd.dispersal_syndrome,
        bdec.deciduousness,
        bl.lifespan_years,
        bl.lifespan_source,
        bts.threat_status,
        bts.threat_status_source,
        COALESCE(nb.species_id IS NOT NULL, FALSE) as is_native_brazil,
        COALESCE(sc.cnt, 0) as sources_count
    FROM species_with_traits swt
    LEFT JOIN best_growth_form bgf ON swt.species_id = bgf.species_id
    LEFT JOIN best_height bh ON swt.species_id = bh.species_id
    LEFT JOIN best_woodiness bw ON swt.species_id = bw.species_id
    LEFT JOIN best_nitrogen bn ON swt.species_id = bn.species_id
    LEFT JOIN best_dispersal bd ON swt.species_id = bd.species_id
    LEFT JOIN best_deciduousness bdec ON swt.species_id = bdec.species_id
    LEFT JOIN best_lifespan bl ON swt.species_id = bl.species_id
    LEFT JOIN best_threat_status bts ON swt.species_id = bts.species_id
    LEFT JOIN sources_count sc ON swt.species_id = sc.species_id
    LEFT JOIN native_brazil nb ON swt.species_id = nb.species_id
    ON CONFLICT (species_id) DO UPDATE SET
        growth_form = EXCLUDED.growth_form,
        growth_form_source = EXCLUDED.growth_form_source,
        max_height_m = EXCLUDED.max_height_m,
        height_source = EXCLUDED.height_source,
        woodiness = EXCLUDED.woodiness,
        nitrogen_fixer = EXCLUDED.nitrogen_fixer,
        dispersal_syndrome = EXCLUDED.dispersal_syndrome,
        deciduousness = EXCLUDED.deciduousness,
        lifespan_years = EXCLUDED.lifespan_years,
        lifespan_source = EXCLUDED.lifespan_source,
        threat_status = EXCLUDED.threat_status,
        threat_status_source = EXCLUDED.threat_status_source,
        is_native_brazil = EXCLUDED.is_native_brazil,
        sources_count = EXCLUDED.sources_count,
        last_updated = CURRENT_TIMESTAMP;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Inserted/updated % records in species_unified', v_count;

END $$;

-- =============================================
-- PASSO 3: Gerar geometrias de range (PostGIS)
-- =============================================
-- Une os polígonos TDWG onde cada espécie ocorre

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    RAISE NOTICE 'Step 3: Generating species geometry from TDWG regions...';

    -- Verificar se tdwg_level3 tem geometrias
    IF NOT EXISTS (SELECT 1 FROM tdwg_level3 WHERE geom IS NOT NULL LIMIT 1) THEN
        RAISE NOTICE 'tdwg_level3 has no geometries, skipping species_geometry population';
        RETURN;
    END IF;

    -- Inserir geometrias de range nativo
    INSERT INTO species_geometry (
        species_id,
        native_range,
        full_range,
        bbox,
        centroid,
        native_area_km2,
        full_area_km2,
        native_regions_count,
        full_regions_count
    )
    SELECT
        sr_native.species_id,
        -- Native range (união dos polígonos onde is_native = TRUE)
        ST_Multi(ST_Union(t_native.geom)) as native_range,
        -- Full range (união de todos os polígonos)
        ST_Multi(ST_Union(t_all.geom)) as full_range,
        -- Bounding box
        ST_Envelope(ST_Union(t_all.geom)) as bbox,
        -- Centroid
        ST_Centroid(ST_Union(t_all.geom)) as centroid,
        -- Área nativa em km² (usando projeção igual-área)
        ROUND(ST_Area(ST_Transform(ST_Union(t_native.geom), 3857)) / 1000000, 2) as native_area_km2,
        -- Área total em km²
        ROUND(ST_Area(ST_Transform(ST_Union(t_all.geom), 3857)) / 1000000, 2) as full_area_km2,
        -- Contagem de regiões nativas
        COUNT(DISTINCT CASE WHEN sr_native.is_native THEN sr_native.tdwg_code END) as native_regions_count,
        -- Contagem total de regiões
        COUNT(DISTINCT sr_native.tdwg_code) as full_regions_count
    FROM species_regions sr_native
    LEFT JOIN tdwg_level3 t_native ON sr_native.tdwg_code = t_native.level3_code AND sr_native.is_native = TRUE
    LEFT JOIN species_regions sr_all ON sr_native.species_id = sr_all.species_id
    LEFT JOIN tdwg_level3 t_all ON sr_all.tdwg_code = t_all.level3_code
    WHERE t_native.geom IS NOT NULL OR t_all.geom IS NOT NULL
    GROUP BY sr_native.species_id
    HAVING ST_Union(t_native.geom) IS NOT NULL OR ST_Union(t_all.geom) IS NOT NULL
    ON CONFLICT (species_id) DO UPDATE SET
        native_range = EXCLUDED.native_range,
        full_range = EXCLUDED.full_range,
        bbox = EXCLUDED.bbox,
        centroid = EXCLUDED.centroid,
        native_area_km2 = EXCLUDED.native_area_km2,
        full_area_km2 = EXCLUDED.full_area_km2,
        native_regions_count = EXCLUDED.native_regions_count,
        full_regions_count = EXCLUDED.full_regions_count,
        last_updated = CURRENT_TIMESTAMP;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Generated geometry for % species', v_count;

END $$;

-- =============================================
-- PASSO 4: Atualizar is_native_brazil após geometrias
-- =============================================
-- Agora que species_regions está populada, atualizar flag de nativo do Brasil

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    RAISE NOTICE 'Step 4: Updating is_native_brazil flag...';

    UPDATE species_unified su
    SET is_native_brazil = TRUE
    WHERE EXISTS (
        SELECT 1 FROM species_regions sr
        WHERE sr.species_id = su.species_id
          AND sr.tdwg_code LIKE 'BZ%'
          AND sr.is_native = TRUE
    )
    AND is_native_brazil = FALSE;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Updated % records with is_native_brazil = TRUE', v_count;

END $$;

-- =============================================
-- PASSO 5: Análise e estatísticas
-- =============================================

DO $$
DECLARE
    v_species_total INTEGER;
    v_unified_total INTEGER;
    v_regions_total INTEGER;
    v_geometry_total INTEGER;
    v_trees INTEGER;
    v_shrubs INTEGER;
    v_native_br INTEGER;
    v_with_lifespan INTEGER;
    v_with_threat INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_species_total FROM species;
    SELECT COUNT(*) INTO v_unified_total FROM species_unified;
    SELECT COUNT(*) INTO v_regions_total FROM species_regions;
    SELECT COUNT(*) INTO v_geometry_total FROM species_geometry;
    SELECT COUNT(*) INTO v_trees FROM species_unified WHERE is_tree = TRUE;
    SELECT COUNT(*) INTO v_shrubs FROM species_unified WHERE is_shrub = TRUE;
    SELECT COUNT(*) INTO v_native_br FROM species_unified WHERE is_native_brazil = TRUE;
    SELECT COUNT(*) INTO v_with_lifespan FROM species_unified WHERE lifespan_years IS NOT NULL;
    SELECT COUNT(*) INTO v_with_threat FROM species_unified WHERE threat_status IS NOT NULL;

    RAISE NOTICE '';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'MIGRATION SUMMARY';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'species (base):         %', v_species_total;
    RAISE NOTICE 'species_unified:        %', v_unified_total;
    RAISE NOTICE 'species_regions:        %', v_regions_total;
    RAISE NOTICE 'species_geometry:       %', v_geometry_total;
    RAISE NOTICE '--------------------------------------------';
    RAISE NOTICE 'Trees:                  %', v_trees;
    RAISE NOTICE 'Shrubs:                 %', v_shrubs;
    RAISE NOTICE 'Native to Brazil:       %', v_native_br;
    RAISE NOTICE 'With lifespan data:     %', v_with_lifespan;
    RAISE NOTICE 'With threat status:     %', v_with_threat;
    RAISE NOTICE '============================================';
END $$;

-- =============================================
-- VACUUM ANALYZE para otimizar índices
-- =============================================
-- Executar após a migração para otimizar performance

-- VACUUM ANALYZE species_unified;
-- VACUUM ANALYZE species_regions;
-- VACUUM ANALYZE species_geometry;
