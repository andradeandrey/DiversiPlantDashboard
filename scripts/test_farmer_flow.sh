#!/bin/bash
# DiversiPlant - Teste de Fluxo do Agricultor com Filtragem Geográfica
# Uso: ./scripts/test_farmer_flow.sh [lat] [lon] [cidade]
# Exemplo: ./scripts/test_farmer_flow.sh -27.60 -48.65 "Florianópolis, SC"
#
# Opções:
#   --old    Usar queries antigas (wcvp_distribution JOIN)
#   --new    Usar queries otimizadas (species_regions + species_unified)
#   --both   Comparar performance de ambas (padrão)

LAT=${1:--27.60}
LON=${2:--48.65}
CIDADE=${3:-"Florianópolis, SC"}
MODE=${4:---both}

echo "======================================================================"
echo "DiversiPlant - Simulacao de Uso por Agricultor"
echo "======================================================================"
echo ""
echo "LOCALIZACAO: $CIDADE ($LAT, $LON)"
echo ""

# Descobrir região TDWG via PostGIS
echo "REGIAO TDWG (via PostGIS):"
TDWG_INFO=$(docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -A -F'|' -c "
SELECT level3_code, level3_name
FROM tdwg_level3
WHERE ST_Contains(geom, ST_SetSRID(ST_Point($LON, $LAT), 4326))
LIMIT 1;")

TDWG_CODE=$(echo "$TDWG_INFO" | cut -d'|' -f1)
TDWG_NAME=$(echo "$TDWG_INFO" | cut -d'|' -f2)

# Se não encontrou dentro, buscar região mais próxima (tolerância de 0.1 graus ~ 11km)
if [ -z "$TDWG_CODE" ]; then
    echo "   Ponto fora dos limites exatos, buscando regiao mais proxima..."
    TDWG_INFO=$(docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -A -F'|' -c "
    SELECT level3_code, level3_name, ROUND(ST_Distance(geom, ST_SetSRID(ST_Point($LON, $LAT), 4326))::numeric * 111, 2) as dist_km
    FROM tdwg_level3
    WHERE ST_DWithin(geom, ST_SetSRID(ST_Point($LON, $LAT), 4326), 0.1)
    ORDER BY geom <-> ST_SetSRID(ST_Point($LON, $LAT), 4326)
    LIMIT 1;")

    TDWG_CODE=$(echo "$TDWG_INFO" | cut -d'|' -f1)
    TDWG_NAME=$(echo "$TDWG_INFO" | cut -d'|' -f2)
    TDWG_DIST=$(echo "$TDWG_INFO" | cut -d'|' -f3)

    if [ -n "$TDWG_CODE" ]; then
        echo "   Regiao mais proxima encontrada a ${TDWG_DIST}km"
    fi
fi

if [ -z "$TDWG_CODE" ]; then
    echo "Coordenadas fora das regioes TDWG conhecidas (mesmo com tolerancia)"
    exit 1
fi

echo "   Codigo: $TDWG_CODE"
echo "   Nome: $TDWG_NAME"
echo ""

# =============================================
# Verificar se tabelas novas existem
# =============================================
NEW_TABLES_EXIST=$(docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -A -c "
SELECT COUNT(*) FROM information_schema.tables
WHERE table_name IN ('species_unified', 'species_regions');")

if [ "$NEW_TABLES_EXIST" != "2" ]; then
    echo "AVISO: Tabelas otimizadas nao encontradas. Usando queries antigas."
    MODE="--old"
fi

# =============================================
# QUERIES OTIMIZADAS (species_unified + species_regions)
# =============================================
if [ "$MODE" = "--new" ] || [ "$MODE" = "--both" ]; then
    echo ""
    echo "======================================================================"
    echo "QUERIES OTIMIZADAS (species_unified + species_regions)"
    echo "======================================================================"

    echo ""
    echo "ESPECIES NA REGIAO $TDWG_NAME (OTIMIZADO):"
    docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
    EXPLAIN ANALYZE
    SELECT COUNT(*)
    FROM species_unified su
    JOIN species_regions sr ON su.species_id = sr.species_id
    WHERE sr.tdwg_code = '$TDWG_CODE' AND su.is_tree = TRUE;"

    echo ""
    echo "CONTAGEM POR TIPO:"
    docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
    SELECT
        'Total na regiao' as metrica,
        COUNT(*)::text as valor
    FROM species_regions sr
    WHERE sr.tdwg_code = '$TDWG_CODE'
    UNION ALL
    SELECT
        'Arvores',
        COUNT(*)::text
    FROM species_unified su
    JOIN species_regions sr ON su.species_id = sr.species_id
    WHERE sr.tdwg_code = '$TDWG_CODE'
      AND su.is_tree = TRUE
    UNION ALL
    SELECT
        'Arbustos',
        COUNT(*)::text
    FROM species_unified su
    JOIN species_regions sr ON su.species_id = sr.species_id
    WHERE sr.tdwg_code = '$TDWG_CODE'
      AND su.is_shrub = TRUE
    UNION ALL
    SELECT
        'Ervas',
        COUNT(*)::text
    FROM species_unified su
    JOIN species_regions sr ON su.species_id = sr.species_id
    WHERE sr.tdwg_code = '$TDWG_CODE'
      AND su.is_herb = TRUE
    UNION ALL
    SELECT
        'Trepadeiras',
        COUNT(*)::text
    FROM species_unified su
    JOIN species_regions sr ON su.species_id = sr.species_id
    WHERE sr.tdwg_code = '$TDWG_CODE'
      AND su.is_climber = TRUE
    ORDER BY 1;"

    echo ""
    echo "ARVORES DA REGIAO (amostra - OTIMIZADO):"
    docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
    SELECT s.canonical_name as especie,
           s.family as familia,
           su.growth_form_source as fonte,
           COALESCE(cn.common_name, '-') as nome_popular
    FROM species s
    JOIN species_unified su ON s.id = su.species_id
    JOIN species_regions sr ON s.id = sr.species_id
    LEFT JOIN common_names cn ON s.id = cn.species_id AND cn.language = 'pt'
    WHERE sr.tdwg_code = '$TDWG_CODE'
      AND su.is_tree = TRUE
    ORDER BY RANDOM()
    LIMIT 12;"

    echo ""
    echo "ARVORES NATIVAS DO BRASIL NA REGIAO:"
    docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
    SELECT s.canonical_name as especie,
           s.family as familia,
           COALESCE(cn.common_name, '-') as nome_popular
    FROM species s
    JOIN species_unified su ON s.id = su.species_id
    JOIN species_regions sr ON s.id = sr.species_id
    LEFT JOIN common_names cn ON s.id = cn.species_id AND cn.language = 'pt'
    WHERE sr.tdwg_code = '$TDWG_CODE'
      AND su.is_tree = TRUE
      AND su.is_native_brazil = TRUE
    ORDER BY RANDOM()
    LIMIT 12;"

fi

# =============================================
# QUERIES ANTIGAS (wcvp_distribution JOIN) - para comparação
# =============================================
if [ "$MODE" = "--old" ] || [ "$MODE" = "--both" ]; then
    echo ""
    echo "======================================================================"
    echo "QUERIES ANTIGAS (wcvp_distribution JOIN)"
    echo "======================================================================"

    echo ""
    echo "ESPECIES NA REGIAO $TDWG_NAME (ANTIGO):"
    docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
    EXPLAIN ANALYZE
    SELECT COUNT(DISTINCT s.id)
    FROM species s
    JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
    JOIN species_traits st ON s.id = st.species_id
    WHERE wd.tdwg_code = '$TDWG_CODE'
      AND st.growth_form = 'tree';" 2>/dev/null || echo "(wcvp_distribution nao encontrada)"

    echo ""
    echo "CONTAGEM POR TIPO (ANTIGO):"
    docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
    SELECT
        'Total na regiao' as metrica,
        COUNT(DISTINCT s.id)::text as valor
    FROM species s
    JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
    WHERE wd.tdwg_code = '$TDWG_CODE'
    UNION ALL
    SELECT
        'Arvores',
        COUNT(DISTINCT s.id)::text
    FROM species s
    JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
    JOIN species_traits st ON s.id = st.species_id
    WHERE wd.tdwg_code = '$TDWG_CODE'
      AND st.growth_form = 'tree'
    UNION ALL
    SELECT
        'Arbustos',
        COUNT(DISTINCT s.id)::text
    FROM species s
    JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
    JOIN species_traits st ON s.id = st.species_id
    WHERE wd.tdwg_code = '$TDWG_CODE'
      AND st.growth_form = 'shrub'
    UNION ALL
    SELECT
        'Ervas',
        COUNT(DISTINCT s.id)::text
    FROM species s
    JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
    JOIN species_traits st ON s.id = st.species_id
    WHERE wd.tdwg_code = '$TDWG_CODE'
      AND st.growth_form IN ('herb', 'forb')
    ORDER BY 1;" 2>/dev/null || echo "(wcvp_distribution nao encontrada)"

    echo ""
    echo "ARVORES DA REGIAO (amostra - ANTIGO):"
    docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
    SELECT s.canonical_name as especie,
           s.family as familia,
           COALESCE(cn.common_name, '-') as nome_popular
    FROM species s
    JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
    JOIN species_traits st ON s.id = st.species_id
    LEFT JOIN common_names cn ON s.id = cn.species_id AND cn.language = 'pt'
    WHERE wd.tdwg_code = '$TDWG_CODE'
      AND st.growth_form = 'tree'
    ORDER BY RANDOM()
    LIMIT 12;" 2>/dev/null || echo "(wcvp_distribution nao encontrada)"
fi

# =============================================
# QUERY PostGIS DIRETO (usando species_geometry)
# =============================================
if [ "$MODE" = "--new" ] || [ "$MODE" = "--both" ]; then
    echo ""
    echo "======================================================================"
    echo "QUERY PostGIS DIRETA (sem precisar saber codigo TDWG)"
    echo "======================================================================"

    GEOM_EXISTS=$(docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -A -c "
    SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'species_geometry';")

    if [ "$GEOM_EXISTS" = "1" ]; then
        echo ""
        echo "ARVORES que ocorrem no ponto ($LAT, $LON) - usando ST_DWithin com tolerancia:"
        docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
        EXPLAIN ANALYZE
        SELECT s.canonical_name as especie,
               s.family as familia
        FROM species s
        JOIN species_unified su ON s.id = su.species_id
        JOIN species_geometry sg ON s.id = sg.species_id
        WHERE su.is_tree = TRUE
          AND ST_DWithin(sg.native_range, ST_SetSRID(ST_Point($LON, $LAT), 4326), 0.05)
        ORDER BY RANDOM()
        LIMIT 10;" 2>/dev/null || echo "(species_geometry vazia ou sem dados)"

        echo ""
        echo "Amostra de arvores (PostGIS direto):"
        docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
        SELECT s.canonical_name as especie,
               s.family as familia,
               COALESCE(cn.common_name, '-') as nome_popular
        FROM species s
        JOIN species_unified su ON s.id = su.species_id
        JOIN species_geometry sg ON s.id = sg.species_id
        LEFT JOIN common_names cn ON s.id = cn.species_id AND cn.language = 'pt'
        WHERE su.is_tree = TRUE
          AND ST_DWithin(sg.native_range, ST_SetSRID(ST_Point($LON, $LAT), 4326), 0.05)
        ORDER BY RANDOM()
        LIMIT 12;" 2>/dev/null || echo "(species_geometry vazia ou sem dados)"
    else
        echo "species_geometry nao encontrada"
    fi
fi

# =============================================
# RESUMO COMPARATIVO
# =============================================
echo ""
echo "======================================================================"
echo "COMPARATIVO (Regiao vs Global)"
echo "======================================================================"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT 'species' as tabela, COUNT(*)::text as registros FROM species
UNION ALL SELECT 'species_unified', COUNT(*)::text FROM species_unified
UNION ALL SELECT 'species_regions', COUNT(*)::text FROM species_regions
UNION ALL SELECT 'species_geometry', COUNT(*)::text FROM species_geometry
UNION ALL SELECT 'species_traits', COUNT(*)::text FROM species_traits
ORDER BY 1;" 2>/dev/null

echo ""
echo "======================================================================"
echo "Dados filtrados por localizacao usando PostGIS!"
echo "======================================================================"
