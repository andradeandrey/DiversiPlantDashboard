# Documentação: TDWG vs PostGIS - Quando Usar Cada Método

---

## Comparação Rápida

| Aspecto | TDWG (Região) | PostGIS (Geometria) |
|---------|---------------|---------------------|
| **Performance** | ~89ms | ~2.6s |
| **Precisão** | Região inteira | Raio específico |
| **Uso recomendado** | Produção | Análise/Pesquisa |
| **Dados base** | species_regions | species_geometry |

---

## Método TDWG (Recomendado para Produção)

### O que é
- Usa regiões TDWG Level 3 (369 regiões globais, 5 no Brasil)
- Cada espécie tem um registro em `species_regions` para cada região onde ocorre
- Baseado no padrão Darwin Core (WGSRPD)

### Como funciona
```
Coordenadas → Identifica região TDWG → Busca espécies nessa região
   (-27.5, -48.5)        BZS              8.954 espécies
```

### Quando usar
- Interface do usuário final (agricultores, pesquisadores)
- APIs de produção com requisitos de performance
- Listagens de espécies por região
- Filtros de nativo/introduzido/endêmico
- Relatórios padronizados (conformidade Darwin Core)

### Vantagens
- **Rápido**: ~89ms por query
- **Padronizado**: Compatível com GBIF, WCVP, literatura científica
- **Dados curados**: Baseado em distribuição oficial do WCVP
- **Filtros semânticos**: is_native, is_endemic, is_introduced

### Limitações
- Resolução geográfica fixa (regiões grandes)
- Brasil tem apenas 5 regiões (BZC, BZE, BZL, BZN, BZS)
- Não diferencia sub-regiões dentro de um estado

### Query exemplo
```sql
-- Via API: /api/species?tdwg_code=BZS&growth_form=tree
SELECT s.canonical_name, s.family, su.growth_form
FROM species s
JOIN species_unified su ON s.id = su.species_id
JOIN species_regions sr ON s.id = sr.species_id
WHERE sr.tdwg_code = 'BZS' AND su.is_tree = TRUE;
```

---

## Método PostGIS (Para Análises Avançadas)

### O que é
- Usa geometria real (polígonos MultiPolygon) do range de cada espécie
- Cada espécie tem um polígono em `species_geometry` = união de todas suas regiões TDWG
- Permite queries espaciais precisas (ST_DWithin, ST_Intersects, etc.)

### Como funciona
```
Coordenadas → Query espacial direta → Espécies cujo range inclui o ponto
 (-27.5, -48.5)    ST_DWithin(0.1°)       8.482 espécies
```

### Quando usar
- Análises de sobreposição de ranges
- Pesquisa científica que precisa de precisão espacial
- Visualização de mapas com polígonos de distribuição
- Queries customizadas (buffer, intersecção, área)
- Comparação de métodos (validação de dados)

### Vantagens
- **Flexível**: Qualquer operação espacial do PostGIS
- **Preciso**: Usa geometria real, não apenas código de região
- **Sem lookup prévio**: Não precisa identificar região primeiro
- **Análises avançadas**: Área de distribuição, centroide, sobreposição

### Limitações
- **Lento**: ~2.6s por query (30x mais lento que TDWG)
- **Resolução limitada**: Geometria ainda é baseada em TDWG Level 3
- **Sem filtros semânticos**: Não diferencia nativo/introduzido diretamente

### Query exemplo
```sql
-- Via API: POST /api/query
SELECT s.canonical_name, s.family, su.growth_form
FROM species s
JOIN species_unified su ON s.id = su.species_id
JOIN species_geometry sg ON s.id = sg.species_id
WHERE ST_DWithin(sg.native_range, ST_SetSRID(ST_Point(-48.5480, -27.5954), 4326), 0.1)
  AND su.is_tree = TRUE;
```

---

## Diferença nos Resultados (Florianópolis)

| Método | Count | Motivo |
|--------|-------|--------|
| TDWG (BZS) | 8.954 | Todas as espécies da região Brazil South |
| PostGIS (0.1°) | 8.482 | Espécies cujo polígono está a ≤11km do ponto |

**Por que a diferença?**
- TDWG inclui espécies de toda a região BZS (RS, SC, PR)
- PostGIS com ST_DWithin(0.1°) exclui espécies cujo range não "toca" o ponto
- Algumas espécies ocorrem em BZS mas em sub-regiões distantes de Florianópolis

---

## Recomendação por Caso de Uso

### Agricultor buscando espécies para plantar
→ **TDWG** (rápido, lista completa da região)

### Pesquisador analisando distribuição de uma espécie
→ **PostGIS** (pode visualizar o polígono, calcular área)

### API pública com muitos requests
→ **TDWG** (performance é crítica)

### Dashboard de análise interna
→ **Ambos** (comparação lado a lado, como implementado)

### Exportação para GBIF/Darwin Core
→ **TDWG** (padrão internacional)

### Modelagem de nicho climático
→ **PostGIS** (precisa de geometria real para cruzar com WorldClim)

---

## Futuro: Quando PostGIS será essencial

1. **Filtragem climática**: Cruzar range da espécie com dados WorldClim
2. **Modelagem de adequação**: Identificar espécies viáveis fora de sua região nativa
3. **Análise de fragmentação**: Calcular conectividade de habitats
4. **Projeções de mudança climática**: Modelar shift de ranges

---

## Respostas às Questões Comuns

### Q1: Conformidade Darwin Core

**Resposta**: Sim, utilizamos o padrão TDWG WGSRPD (World Geographical Scheme for Recording Plant Distributions), que é o sistema oficial do Darwin Core para distribuição de plantas.

- Referência: https://dwc.tdwg.org/terms/#location
- Mapeamento: `dwc:locationID` → `species_regions.tdwg_code`

### Q2: Sistema Geográfico (Apenas Level 3?)

**Resposta**: Sim, usamos exclusivamente **TDWG Level 3**.

- Total: 369 regiões globais
- Brasil: 5 regiões (BZC, BZE, BZL, BZN, BZS)
- Fonte: https://github.com/tdwg/wgsrpd

### Q3: Fontes de Dados

| Fonte | Papel | Dados |
|-------|-------|-------|
| **WCVP** | PRIMÁRIA para distribuição | Espécie → Região TDWG + status nativo/introduzido |
| **GIFT** | PRIORITÁRIA para growth_form | Definição mais consistente globalmente + lógica Climber.R |
| **REFLORA** | SECUNDÁRIA para growth_form | Fallback para espécies brasileiras sem dados GIFT |
| **WCVP** | TERCIÁRIA para growth_form | Desambiguação (usa "climber" genérico) |
| **TreeGOER** | Validação de árvores | Última opção para desambiguação |
| **GBIF** | NÃO USADO para listas | Apenas registros de ocorrência |

### Q4: Nativo vs Introduzido vs Ocorrência

**O que retornamos HOJE**:
- Espécies NATIVAS da região (segundo WCVP)
- Espécies INTRODUZIDAS na região (segundo WCVP)
- NÃO são registros de ocorrência GBIF

**Distinção importante**:
- WCVP: "Espécie X é NATIVA da região Y" (curado por taxonomistas)
- GBIF: "Espécie X foi OBSERVADA no ponto Z" (pode ser cultivo, erro, escape)

### Q5: O que os números significam

Para Florianópolis (região TDWG: BZS - Brazil South):
- **1.175 árvores**: Espécies com growth_form='tree' E registro WCVP para BZS
- **3.058 arbustos**: Espécies com growth_form='shrub' E registro WCVP para BZS

Estas são espécies que **ocorrem naturalmente** na região (nativas + naturalizadas), NÃO são "climaticamente adaptadas".

### Q6: "Climaticamente Adaptadas" - Escopo Futuro

**O que temos HOJE**: Espécies que ocorrem naturalmente na região TDWG

**O que NÃO temos**: Espécies que seriam climaticamente viáveis mas não ocorrem lá

**Para implementar "climaticamente adaptadas" precisamos**:
1. Dados climáticos por espécie (envelope climático)
2. WorldClim bioclim vars para a localização
3. Algoritmo de matching climático

---

## Prioridade de Fontes para Growth Form

### Nova Ordem (Implementada)

| Prioridade | Fonte | Condição | Justificativa |
|------------|-------|----------|---------------|
| 1 | **GIFT** + Climber.R | Sempre preferido | Distinção liana vs vine |
| 2 | **REFLORA** | Apenas se GIFT vazio | Espécies brasileiras |
| 3 | **WCVP** | Apenas se ambíguo | Taxonomia referência |
| 4 | **TreeGOER** | Última opção | Validação árvores |

### Diferenças Entre Fontes

| Fonte | Trepadeiras | Ervas |
|-------|-------------|-------|
| GIFT | liana (5,072) + vine (2,094) | forb (91,912) |
| REFLORA | vine (3,564) | forb (16,427) |
| WCVP | climber (10,282) | herb (81,094) |

---

## Histórico: Migração do Schema (Concluída 2026-01-20)

### Tabelas Criadas e Populadas

| Tabela | Registros | Status |
|--------|-----------|--------|
| species_unified | 328,269 | Completo |
| species_regions | 1,358,240 | Completo |
| species_geometry | 362,631 | Completo |

### Performance Alcançada

- Query TDWG: **~89ms** (era ~444ms)
- Query PostGIS direto: **~5.8s** (funcional, pode ser otimizado)
