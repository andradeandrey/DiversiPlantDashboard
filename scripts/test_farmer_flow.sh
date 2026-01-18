#!/bin/bash
# DiversiPlant - Teste de Fluxo do Agricultor
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

echo "📊 TOTAL DE ESPÉCIES:"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -c "SELECT COUNT(*) FROM species;"

echo ""
echo "📊 POR FORMA DE CRESCIMENTO:"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT growth_form, COUNT(*) as qtd
FROM species_traits
WHERE growth_form IS NOT NULL
GROUP BY growth_form
ORDER BY qtd DESC
LIMIT 10;"

echo ""
echo "🌳 ÁRVORES NATIVAS DO BRASIL (amostra para agrofloresta):"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT s.canonical_name as especie,
       s.family as familia,
       COALESCE(cn.common_name, '-') as nome_popular
FROM species s
JOIN species_traits st ON s.id = st.species_id
LEFT JOIN common_names cn ON s.id = cn.species_id AND cn.language = 'pt'
WHERE st.growth_form = 'tree'
  AND s.reflora_id IS NOT NULL
ORDER BY RANDOM()
LIMIT 12;"

echo ""
echo "🍎 ESPÉCIES COM NOMES POPULARES EM PORTUGUÊS:"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT cn.common_name as nome_popular,
       s.canonical_name as especie,
       s.family as familia
FROM species s
JOIN common_names cn ON s.id = cn.species_id
WHERE cn.language = 'pt'
ORDER BY RANDOM()
LIMIT 12;"

echo ""
echo "🌿 ARBUSTOS NATIVOS (para sub-bosque):"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT s.canonical_name as especie,
       s.family as familia
FROM species s
JOIN species_traits st ON s.id = st.species_id
WHERE st.growth_form = 'shrub'
  AND s.reflora_id IS NOT NULL
ORDER BY RANDOM()
LIMIT 8;"

echo ""
echo "📈 QUALIDADE DOS DADOS:"
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT 'Espécies totais' as metrica, COUNT(*)::text as valor FROM species
UNION ALL SELECT 'Árvores', COUNT(*)::text FROM species_traits WHERE growth_form = 'tree'
UNION ALL SELECT 'Com REFLORA (Brasil)', COUNT(*)::text FROM species WHERE reflora_id IS NOT NULL
UNION ALL SELECT 'Com traits GIFT', COUNT(*)::text FROM species WHERE gift_work_id IS NOT NULL
UNION ALL SELECT 'Nomes em português', COUNT(DISTINCT species_id)::text FROM common_names WHERE language = 'pt'
ORDER BY 1;"

echo ""
echo "======================================================================"
echo "✅ Dados prontos para uso pelo agricultor!"
echo "======================================================================"
