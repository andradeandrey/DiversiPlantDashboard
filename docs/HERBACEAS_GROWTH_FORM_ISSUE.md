# Problema: Poucas Herbáceas nas Recomendações

**Data**: 2026-02-04
**Problema identificado**: Milho (Zea mays) e outras herbáceas não aparecem nas recomendações
**Causa raiz**: 3 problemas distintos

---

## Problema 1: Classificação de Growth Forms

### Situação Atual

O sistema classifica plantas herbáceas em **3 categorias diferentes**:

| Growth Form | Espécies | Com Climate Envelope | Cobertura |
|-------------|----------|----------------------|-----------|
| **forb** | 95.643 | 53.254 | 55.7% |
| **herb** | 33.077 | 13.868 | 41.9% |
| **graminoid** | 4.546 | 3.452 | 75.9% |
| **TOTAL** | **133.266** | **70.574** | **52.9%** |

### Definições Botânicas

- **Herb** (sensu stricto): Herbáceas de folha larga, não lenhosas
- **Forb**: Herbáceas floridas excluindo gramíneas (também são herbs!)
- **Graminoid**: Gramíneas e ciperáceas (Poaceae, Cyperaceae)

**Na prática**: forb + herb + graminoid = TODAS as herbáceas sensu lato

### Impacto

Quando usuário filtra por `growth_forms: ["herb"]`, obtém apenas **33.077 espécies** (25% do total de herbáceas).

**Deveria** incluir também forb e graminoid para ter as **133.266 espécies** herbáceas.

---

## Problema 2: Espécies Introduzidas Filtradas

### Caso: Milho (Zea mays)

```sql
SELECT
    s.canonical_name,
    s.family,
    su.growth_form,
    sr.tdwg_code,
    sr.is_native,
    sr.is_introduced
FROM species s
JOIN species_unified su ON s.id = su.species_id
JOIN species_regions sr ON s.id = sr.species_id
WHERE s.canonical_name = 'Zea mays'
  AND sr.tdwg_code = 'BZS';
```

**Resultado**:
```
canonical_name | family  | growth_form | tdwg_code | is_native | is_introduced
---------------+---------+-------------+-----------+-----------+--------------
Zea mays       | Poaceae | graminoid   | BZS       | FALSE     | TRUE
```

### Filtro Atual no Código

**query-explorer/recommendation.go:374**:
```go
WHERE sr.is_native = TRUE
```

**Consequência**: Milho (e todas as espécies cultivadas introduzidas) **NUNCA** aparecem nas recomendações.

### Espécies Afetadas

Muitas espécies agrícolas importantes são introduzidas:
- Zea mays (milho)
- Triticum aestivum (trigo)
- Oryza sativa (arroz)
- Solanum tuberosum (batata)
- Glycine max (soja)
- etc.

---

## Problema 3: Climate Envelope do Milho

Apesar dos problemas acima, o milho **TEM** climate envelope:

```sql
SELECT
    s.canonical_name,
    sce.envelope_source,
    sce.temp_mean,
    sce.precip_mean
FROM species s
JOIN species_climate_envelope_unified sce ON s.id = sce.species_id
WHERE s.canonical_name = 'Zea mays';
```

**Resultado**:
```
canonical_name | envelope_source | temp_mean | precip_mean
---------------+-----------------+-----------+-------------
Zea mays       | wcvp            | 20.45     | 1407.88
```

✅ Tem envelope climático (fonte WCVP)
❌ Nunca é retornado devido aos filtros

---

## Soluções Propostas

### Solução 1: Expandir Filtro de Growth Forms

**No frontend**: Quando usuário seleciona "Herbs", incluir automaticamente forb e graminoid.

**Implementação**:
```javascript
// query-explorer/static/index.html
function expandGrowthForms(selectedForms) {
    const expanded = [...selectedForms];

    // Se selecionou "herb", adicionar forb e graminoid
    if (selectedForms.includes('herb')) {
        if (!expanded.includes('forb')) expanded.push('forb');
        if (!expanded.includes('graminoid')) expanded.push('graminoid');
    }

    return expanded;
}
```

**Ou criar categoria agrupada**:
```javascript
const GROWTH_FORM_GROUPS = {
    'herbaceous': ['herb', 'forb', 'graminoid'],  // Todas herbáceas
    'woody': ['tree', 'shrub', 'subshrub'],        // Todas lenhosas
    'climbers': ['climber', 'liana', 'vine']       // Todas trepadeiras
};
```

### Solução 2: Permitir Espécies Introduzidas (Opcional)

**Adicionar parâmetro no request**:
```json
{
    "tdwg_code": "BZS",
    "n_species": 20,
    "preferences": {
        "growth_forms": ["herb", "forb", "graminoid"],
        "include_introduced": true  // ← NOVO
    }
}
```

**No backend** (recommendation.go):
```go
whereClause := "WHERE 1=1"

if !req.Preferences.IncludeIntroduced {
    whereClause += " AND sr.is_native = TRUE"
} else {
    // Aceitar nativas OU introduzidas
    whereClause += " AND (sr.is_native = TRUE OR sr.is_introduced = TRUE)"
}
```

### Solução 3: Normalizar Growth Forms no Banco

**Criar campo adicional `is_herbaceous`**:

```sql
ALTER TABLE species_unified
ADD COLUMN is_herbaceous BOOLEAN;

UPDATE species_unified
SET is_herbaceous = (growth_form IN ('herb', 'forb', 'graminoid'));

CREATE INDEX idx_species_unified_herbaceous
ON species_unified(is_herbaceous);
```

**Vantagens**:
- Query mais simples: `WHERE su.is_herbaceous = TRUE`
- Semanticamente claro
- Performance melhor (índice boolean)

---

## Recomendação Final

### Curto Prazo (Implementar AGORA)

1. **Expandir automaticamente "herb" → ["herb", "forb", "graminoid"]** no frontend
2. **Adicionar opção "Include Introduced Species"** com default FALSE

### Médio Prazo

1. **Adicionar campo `is_herbaceous`** ao schema
2. **Criar grupos de growth forms** (herbaceous, woody, climbers)
3. **Documentar diferenças** entre herb/forb/graminoid para usuários

### Longo Prazo

1. **Revisar classificação de growth forms** usando fontes mais recentes
2. **Considerar hierarquia de traits** (herb ⊃ forb, herb ⊃ graminoid)

---

## Impacto Esperado

### Antes (atual)

```sql
-- Filtro: growth_forms = ["herb"], is_native = TRUE
SELECT COUNT(*) FROM species_unified su
JOIN species_regions sr ON su.species_id = sr.species_id
WHERE su.growth_form = 'herb'
  AND sr.is_native = TRUE;
-- Resultado: ~25.000 espécies
```

### Depois (com fix)

```sql
-- Filtro: growth_forms = ["herb", "forb", "graminoid"], is_native = TRUE
SELECT COUNT(*) FROM species_unified su
JOIN species_regions sr ON su.species_id = sr.species_id
WHERE su.growth_form IN ('herb', 'forb', 'graminoid')
  AND sr.is_native = TRUE;
-- Resultado: ~100.000 espécies (4x mais!)
```

### Com introduced (opcional)

```sql
-- Filtro: herbaceous, include_introduced = TRUE
SELECT COUNT(*) FROM species_unified su
JOIN species_regions sr ON su.species_id = sr.species_id
WHERE su.growth_form IN ('herb', 'forb', 'graminoid')
  AND (sr.is_native = TRUE OR sr.is_introduced = TRUE);
-- Resultado: ~120.000+ espécies
```

---

## Exemplos de Espécies que Passarão a Aparecer

### Com expansão herb → [herb, forb, graminoid]

- Zea mays (milho) - graminoid, introduced
- Manihot esculenta (mandioca) - forb, native
- Ipomoea batatas (batata-doce) - forb, introduced
- Phaseolus vulgaris (feijão) - forb, native/introduced
- Capsicum annuum (pimentão) - forb, native

### Apenas com include_introduced = TRUE

- Triticum aestivum (trigo) - graminoid, introduced
- Oryza sativa (arroz) - graminoid, introduced
- Lactuca sativa (alface) - forb, introduced

### Casos Especiais: Espécies Não Registradas no Brasil

**Solanum lycopersicum (Tomate)**:
- ❌ **NÃO aparecerá** mesmo com fixes acima
- Growth form: forb
- WCVP: Registrado apenas em Peru (nativo), Colômbia, Equador, Venezuela (introduzido)
- **Não está em nenhuma região TDWG do Brasil** (BZ*)
- GBIF: **~114.496 ocorrências globais** (API live, fev/2026), **93.512** no snapshot S3 2024-10-01 (scan completo)
  - Top países: EUA (2.153), Afeganistão (886), Espanha (683), Alemanha (633), Bélgica (594)
  - Apenas ~37% dos registros possuem coordenadas; ~19% com qualidade (incerteza ≤10km)
  - Ocorrências no Brasil: muito poucas (não aparece entre os top 15 países)
- Climate envelope: ✅ (GBIF source, temp=11.54°C, precip=803mm)
- **Problema**: Ausência de registro WCVP no Brasil impede recomendação

**Thymus vulgaris (Tomilho)**:
- ❌ **NÃO aparecerá** mesmo com fixes acima
- Growth form: subshrub (não herbácea)
- WCVP: Registrado em 17 regiões (Europa, Ásia), **nenhuma na América do Sul**
- GBIF: Apenas 1 ocorrência global, **nenhuma no Brasil**
- Climate envelope: ✅ (WCVP source, temp=12.84°C, precip=731mm)
- **Problema**: Espécie não naturalizada no Brasil, apenas cultivada

---

## Queries de Verificação

### Contar herbáceas por categoria

```sql
SELECT
    su.growth_form,
    COUNT(*) as total_species,
    COUNT(*) FILTER (WHERE sr.is_native = TRUE) as native,
    COUNT(*) FILTER (WHERE sr.is_introduced = TRUE) as introduced
FROM species_unified su
JOIN species_regions sr ON su.species_id = sr.species_id
WHERE su.growth_form IN ('herb', 'forb', 'graminoid')
  AND sr.tdwg_code = 'BZS'
GROUP BY su.growth_form;
```

### Verificar espécies agrícolas importantes

```sql
SELECT
    s.canonical_name,
    s.family,
    su.growth_form,
    sr.is_native,
    sr.is_introduced,
    sce.temp_mean,
    sce.envelope_source
FROM species s
JOIN species_unified su ON s.id = su.species_id
JOIN species_regions sr ON s.id = sr.species_id
LEFT JOIN species_climate_envelope_unified sce ON s.id = sce.species_id
WHERE s.canonical_name IN (
    'Zea mays',
    'Triticum aestivum',
    'Oryza sativa',
    'Glycine max',
    'Phaseolus vulgaris'
)
AND sr.tdwg_code = 'BZS';
```

---

## Problema 4: Dados WCVP Incompletos para Espécies Cultivadas

### Situação

Muitas espécies cultivadas globalmente **não têm registro WCVP** nas regiões onde são amplamente plantadas.

**Exemplos**:
- Tomate (Solanum lycopersicum): Cultivado em todo Brasil, mas WCVP só registra Peru, Colômbia, Equador, Venezuela
- Tomilho (Thymus vulgaris): Cultivado globalmente, mas WCVP não registra América do Sul

### Por Que Isso Acontece?

**WCVP foca em distribuição NATURAL** (nativa ou naturalizada):
- ✅ Registra: Espécies nativas, espécies naturalizadas (estabelecidas na natureza)
- ❌ NÃO registra: Espécies apenas cultivadas (não estabelecidas espontaneamente)

**Tomate no Brasil**:
- Amplamente cultivado em hortas, fazendas, estufas
- **Não é naturalizado** (não cresce espontaneamente na natureza)
- Logo, WCVP não o lista como presente no Brasil

### Impacto no Sistema de Recomendação

Query atual:
```sql
WHERE sr.tdwg_code = 'BZS'  -- Precisa estar no WCVP para a região
  AND sr.is_native = TRUE
```

**Resultado**: Espécies cultivadas mas não naturalizadas **nunca aparecem**.

### Soluções Possíveis

#### Solução 1: Usar GBIF como Fonte Suplementar

```sql
-- Se espécie NÃO está no WCVP para região, verificar GBIF
WITH wcvp_species AS (
    SELECT species_id FROM species_regions sr
    WHERE sr.tdwg_code = 'BZS' AND sr.is_native = TRUE
),
gbif_species AS (
    SELECT DISTINCT go.species_id
    FROM gbif_occurrences go
    WHERE go.country_code = 'BR'
      AND go.species_id NOT IN (SELECT species_id FROM wcvp_species)
    GROUP BY go.species_id
    HAVING COUNT(*) >= 10  -- Mínimo 10 ocorrências
)
SELECT * FROM wcvp_species
UNION
SELECT * FROM gbif_species;
```

**Vantagens**:
- Captura espécies cultivadas com ocorrências GBIF
- Baseado em dados reais de herbário/observação

**Desvantagens**:
- Tomate tem apenas 1 ocorrência BR no GBIF (insuficiente)
- Muitas cultivadas não têm dados GBIF suficientes

#### Solução 2: Lista Manual de Espécies Agrícolas

Criar tabela `agricultural_species`:

```sql
CREATE TABLE agricultural_species (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),
    common_use VARCHAR(50),  -- 'vegetable', 'fruit', 'herb', 'grain'
    cultivation_intensity VARCHAR(20),  -- 'widespread', 'common', 'rare'
    regions_cultivated VARCHAR[],  -- ['BZN', 'BZS', 'BZE', 'BZC', 'BZL']
    source VARCHAR(50)  -- 'FAO', 'expert_knowledge', etc
);

-- Popular com espécies conhecidas
INSERT INTO agricultural_species VALUES
(14, 'vegetable', 'widespread', ARRAY['BZN','BZS','BZE','BZC','BZL'], 'FAO'),  -- Tomate
-- ... outras espécies
```

**Vantagens**:
- Controle total sobre espécies agrícolas
- Pode incluir metadados (uso, intensidade)

**Desvantagens**:
- Trabalho manual de curadoria
- Precisa manutenção

#### Solução 3: Toggle "Modo Agrícola"

No request, adicionar flag:

```json
{
    "tdwg_code": "BZS",
    "agricultural_mode": true,  // ← NOVO
    "include_introduced": true
}
```

**Quando `agricultural_mode = true`**:
- Incluir espécies de `agricultural_species` para a região
- Ignorar requisito `sr.is_native = TRUE`
- Priorizar espécies com `cultivation_intensity = 'widespread'`

### Recomendação

**Curto prazo**: Documentar limitação (espécies cultivadas podem não aparecer)

**Médio prazo**: Implementar Solução 2 (lista manual) com top 100 espécies agrícolas

**Longo prazo**: Integrar com base de dados FAO de cultivos por país

---

## Conclusão

O problema de "poucas herbáceas" tem **4 causas distintas**:

1. ❌ **Classificação fragmentada**: herb/forb/graminoid tratados separadamente
2. ❌ **Filtro de nativas**: Exclui todas as espécies introduzidas (incluindo cultivos)
3. ❌ **Dados WCVP incompletos**: Espécies cultivadas não naturalizadas não aparecem
4. ✅ **Climate envelopes**: Existem e estão corretos

**Fix prioritário**: Expandir automaticamente "herb" para incluir forb e graminoid.

**Fix opcional**: Adicionar toggle "Include introduced species" para contextos agrícolas.

**Fix para espécies cultivadas**: Criar tabela `agricultural_species` com curadoria manual das principais espécies agrícolas brasileiras.
