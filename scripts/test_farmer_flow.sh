#!/bin/bash
# DiversiPlant - Teste de Fluxo do Agricultor com Filtragem Geográfica
# Uso: ./scripts/test_farmer_flow.sh [lat] [lon] [cidade]
# Exemplo: ./scripts/test_farmer_flow.sh -27.5954 -48.5480 "Florianópolis, SC"

LAT=${1:--27.5954}
LON=${2:--48.5480}
CIDADE=${3:-"Florianópolis, SC"}

echo "======================================================================"
echo "🌱 DiversiPlant - Simulação de Uso por Agricultor"
echo "======================================================================"
echo ""
echo "📍 LOCALIZAÇÃO: $CIDADE ($LAT, $LON)"
echo ""

# Descobrir região TDWG via PostGIS
echo "🗺️  REGIÃO TDWG (via PostGIS):"
TDWG_INFO=$(docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -A -F'|' -c "
SELECT level3_code, level3_name
FROM tdwg_level3
WHERE ST_Contains(geom, ST_SetSRID(ST_Point($LON, $LAT), 4326))
LIMIT 1;")

TDWG_CODE=$(echo "$TDWG_INFO" | cut -d'|' -f1)
TDWG_NAME=$(echo "$TDWG_INFO" | cut -d'|' -f2)

if [ -z "$TDWG_CODE" ]; then
    echo "❌ Coordenadas fora das regiões TDWG conhecidas"
    exit 1
fi

echo "   Código: $TDWG_CODE"
echo "   Nome: $TDWG_NAME"
echo ""

# Contar espécies NA REGIÃO
echo "📊 ESPÉCIES NA REGIÃO $TDWG_NAME:"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT
    'Total na região' as metrica,
    COUNT(DISTINCT s.id)::text as valor
FROM species s
JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
WHERE wd.tdwg_code = '$TDWG_CODE'
UNION ALL
SELECT
    'Árvores',
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
ORDER BY 1;"

echo ""
echo "🌳 ÁRVORES DA REGIÃO (amostra para agrofloresta):"
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
LIMIT 12;"

echo ""
echo "🍎 ESPÉCIES DA REGIÃO COM NOMES POPULARES:"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT cn.common_name as nome_popular,
       s.canonical_name as especie,
       s.family as familia
FROM species s
JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
JOIN common_names cn ON s.id = cn.species_id
WHERE wd.tdwg_code = '$TDWG_CODE'
  AND cn.language = 'pt'
ORDER BY RANDOM()
LIMIT 12;"

echo ""
echo "🌿 ARBUSTOS DA REGIÃO (para sub-bosque):"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT s.canonical_name as especie,
       s.family as familia
FROM species s
JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
JOIN species_traits st ON s.id = st.species_id
WHERE wd.tdwg_code = '$TDWG_CODE'
  AND st.growth_form = 'shrub'
ORDER BY RANDOM()
LIMIT 8;"

echo ""
echo "📈 COMPARATIVO (Região vs Global):"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT 'Árvores $TDWG_NAME' as metrica,
       COUNT(DISTINCT s.id)::text as valor
FROM species s
JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
JOIN species_traits st ON s.id = st.species_id
WHERE wd.tdwg_code = '$TDWG_CODE' AND st.growth_form = 'tree'
UNION ALL
SELECT 'Árvores Global', COUNT(DISTINCT species_id)::text
FROM species_traits WHERE growth_form = 'tree'
UNION ALL
SELECT 'Espécies $TDWG_NAME', COUNT(DISTINCT s.id)::text
FROM species s
JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
WHERE wd.tdwg_code = '$TDWG_CODE'
UNION ALL
SELECT 'Espécies Global', COUNT(*)::text FROM species
ORDER BY 1;"

echo ""
echo "======================================================================"
echo "✅ Dados filtrados por localização usando PostGIS!"
echo "======================================================================"
