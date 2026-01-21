# Migração: Schema Unificado para Queries Espaciais

**Data**: 2026-01-19
**Autor**: Stickybit (dev@stickybit.com.br)

---

## Objetivo

Criar tabelas otimizadas para queries espaciais, eliminando JOINs desnecessários e melhorando a performance de ~444ms para ~50ms.

---

## Problema Anterior

```
Query para árvores de São Paulo:
species (448K) → JOIN wcvp_distribution (2M) → JOIN species_traits (555K) → JOIN tdwg_level3
                     ↓                              ↓
               via wcvp_id (string)          múltiplos registros por espécie
               ~444ms por query              (wcvp, gift, treegoer, reflora)
```

**Issues identificados**:
1. `species_traits` tem registros duplicados de múltiplas fontes (555K traits para 448K espécies)
2. `species_distribution` estava vazia (13 registros) - usávamos `wcvp_distribution` via JOIN
3. Não havia geometria pré-calculada para ranges de espécies
4. Queries requeriam 4+ JOINs para filtrar por localização

---

## Solução Implementada

### Arquivos Criados

| Arquivo | Descrição |
|---------|-----------|
| `database/migrations/002_unified_schema.sql` | DDL das novas tabelas, índices e funções auxiliares |
| `database/migrations/003_populate_unified.sql` | Scripts de migração para popular as tabelas |

### Arquivos Modificados

| Arquivo | Alterações |
|---------|------------|
| `scripts/test_farmer_flow.sh` | Suporte a queries antigas e novas com modos `--old`, `--new`, `--both` |
| `.claude/commands/db-migrate.md` | Instruções para aplicar as novas migrações |

---

## Novas Tabelas

### 1. `species_unified` - Traits Consolidados

Consolida múltiplos registros de `species_traits` em um único registro por espécie.

```sql
CREATE TABLE species_unified (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),

    -- Traits consolidados (prioridade: gift > reflora > wcvp > treegoer)
    growth_form VARCHAR(50),
    growth_form_source VARCHAR(20),
    max_height_m DECIMAL(10,2),
    height_source VARCHAR(20),
    woodiness VARCHAR(50),
    nitrogen_fixer BOOLEAN,
    dispersal_syndrome VARCHAR(100),
    deciduousness VARCHAR(50),

    -- Flags geradas automaticamente (STORED)
    is_tree BOOLEAN GENERATED ALWAYS AS (growth_form = 'tree') STORED,
    is_shrub BOOLEAN GENERATED ALWAYS AS (growth_form = 'shrub') STORED,
    is_climber BOOLEAN GENERATED ALWAYS AS (growth_form = 'climber') STORED,
    is_herb BOOLEAN GENERATED ALWAYS AS (growth_form IN ('herb', 'forb')) STORED,
    is_palm BOOLEAN GENERATED ALWAYS AS (growth_form = 'palm') STORED,
    is_native_brazil BOOLEAN DEFAULT FALSE,

    -- Metadados
    sources_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Prioridade de fontes**:
1. GIFT (definições mais consistentes: liana vs vine, lógica Climber.R)
2. REFLORA (fallback para espécies brasileiras sem dados GIFT)
3. WCVP (usa 'climber' genérico, sem distinção liana/vine)
4. TreeGOER (última opção para validação de árvores)

### 2. `species_regions` - Distribuição Geográfica Direta

Substitui o padrão de JOIN via `wcvp_id` (string) por relação direta via `species_id` (integer).

```sql
CREATE TABLE species_regions (
    id SERIAL PRIMARY KEY,
    species_id INTEGER REFERENCES species(id) ON DELETE CASCADE,
    tdwg_code VARCHAR(10) NOT NULL,

    -- Status de ocorrência
    is_native BOOLEAN DEFAULT TRUE,
    is_endemic BOOLEAN DEFAULT FALSE,
    is_introduced BOOLEAN DEFAULT FALSE,

    -- Fonte do dado
    source VARCHAR(20), -- 'wcvp', 'reflora', 'gbif'

    UNIQUE(species_id, tdwg_code)
);
```

### 3. `species_geometry` - Polígonos PostGIS

Armazena a união dos polígonos TDWG onde cada espécie ocorre.

```sql
CREATE TABLE species_geometry (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),

    -- União dos polígonos TDWG
    native_range GEOMETRY(MultiPolygon, 4326),  -- apenas nativas
    full_range GEOMETRY(MultiPolygon, 4326),    -- inclui introduzidas

    -- Para queries rápidas
    bbox GEOMETRY(Polygon, 4326),
    centroid GEOMETRY(Point, 4326),

    -- Área em km²
    native_area_km2 DECIMAL(12,2),
    full_area_km2 DECIMAL(12,2),

    -- Contagem de regiões
    native_regions_count INTEGER DEFAULT 0,
    full_regions_count INTEGER DEFAULT 0,

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Comparativo de Queries

### Query Antiga (4 JOINs, ~444ms)

```sql
SELECT COUNT(DISTINCT s.id)
FROM species s
JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
JOIN species_traits st ON s.id = st.species_id
WHERE wd.tdwg_code = 'BZL' AND st.growth_form = 'tree';
```

### Query Nova (2 JOINs, ~50ms)

```sql
SELECT COUNT(*)
FROM species_unified su
JOIN species_regions sr ON su.species_id = sr.species_id
WHERE sr.tdwg_code = 'BZL' AND su.is_tree = TRUE;
```

### Query PostGIS Direta (sem precisar saber código TDWG)

```sql
SELECT COUNT(*)
FROM species_unified su
JOIN species_geometry sg ON su.species_id = sg.species_id
WHERE su.is_tree = TRUE
  AND ST_Contains(sg.native_range, ST_SetSRID(ST_Point(-46.6333, -23.5505), 4326));
```

---

## Como Aplicar

### 1. Aplicar Schema

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
psql -h localhost -U diversiplant -d diversiplant -f database/migrations/002_unified_schema.sql
```

### 2. Popular Tabelas

```bash
psql -h localhost -U diversiplant -d diversiplant -f database/migrations/003_populate_unified.sql
```

### 3. Verificar Migração

```bash
psql -h localhost -U diversiplant -d diversiplant -c "
SELECT 'species_unified' as tabela, COUNT(*) FROM species_unified
UNION ALL SELECT 'species_regions', COUNT(*) FROM species_regions
UNION ALL SELECT 'species_geometry', COUNT(*) FROM species_geometry;"
```

### 4. Testar Performance

```bash
./scripts/test_farmer_flow.sh -27.5954 -48.5480 "Florianópolis, SC" --both
```

---

## Índices Criados

### species_unified
- `idx_unified_tree` - Parcial onde `is_tree = TRUE`
- `idx_unified_shrub` - Parcial onde `is_shrub = TRUE`
- `idx_unified_climber` - Parcial onde `is_climber = TRUE`
- `idx_unified_herb` - Parcial onde `is_herb = TRUE`
- `idx_unified_palm` - Parcial onde `is_palm = TRUE`
- `idx_unified_growth` - Por `growth_form`
- `idx_unified_native_br` - Parcial onde `is_native_brazil = TRUE`

### species_regions
- `idx_regions_tdwg` - Por `tdwg_code`
- `idx_regions_species` - Por `species_id`
- `idx_regions_native` - Parcial onde `is_native = TRUE`
- `idx_regions_endemic` - Parcial onde `is_endemic = TRUE`
- `idx_regions_introduced` - Parcial onde `is_introduced = TRUE`
- `idx_regions_tdwg_species` - Composto `(tdwg_code, species_id)`

### species_geometry
- `idx_species_geom_native` - GIST em `native_range`
- `idx_species_geom_full` - GIST em `full_range`
- `idx_species_geom_bbox` - GIST em `bbox`
- `idx_species_geom_centroid` - GIST em `centroid`

---

## Configuração Git

```bash
git config user.name "Stickybit"
git config user.email "dev@stickybit.com.br"
git config alias.sc 'commit --author="Stickybit <dev@stickybit.com.br>"'
```

---

## Fluxo de Dados dos Crawlers

### Tabelas Escritas por Cada Crawler

| Crawler | species | species_traits | common_names | wcvp_distribution | Contribui para Unified |
|---------|---------|----------------|--------------|-------------------|------------------------|
| GBIF | metadata | - | vernacular | - | N/A (metadata only) |
| GIFT | id, genus | growth_form, height | - | - | species_unified (priority 1) |
| REFLORA | id, family | growth_form (pt) | vernacular PT | - | species_unified (priority 2) |
| WCVP | id, family | growth_form | - | taxon_id, tdwg | species_unified (priority 3) + species_regions |
| TreeGOER | canonical | growth_form='tree' | - | - | species_unified (priority 4) |
| IUCN | iucn_id | conservation | vernacular | - | N/A (conservation only) |
| WorldClim | - | - | - | - | N/A (climate raster) |

### Prioridade de Fontes para Consolidação

```
1. GIFT     - Definições mais consistentes (liana vs vine, lógica Climber.R)
2. REFLORA  - Fallback para espécies brasileiras sem dados GIFT
3. WCVP     - Usa 'climber' genérico, sem distinção liana/vine
4. TreeGOER - Última opção para validação de árvores
```

**Motivação da prioridade GIFT**: A definição de growth_form no GIFT é mais coerente com as funcionalidades do DiversiPlant porque distingue **liana** (trepadeira lenhosa) de **vine** (trepadeira herbácea) e usa a lógica Climber.R de Renata que combina `trait_1.2.2` + `trait_1.4.2`.

### Comandos CLI para Crawlers

```bash
# Rodar crawler específico
python -m crawlers.run --source wcvp --mode full

# Rodar crawler com refresh das tabelas unificadas
python -m crawlers.run --source wcvp --refresh-unified

# Apenas refresh das tabelas unificadas (sem rodar crawlers)
python -m crawlers.run --only-refresh

# Rodar todos os crawlers
python -m crawlers.run --source all --mode incremental
```

### Atualização das Tabelas Unificadas

Após qualquer crawler rodar, as tabelas unificadas podem ser atualizadas:

1. **Via CLI**: `python -m crawlers.run --only-refresh`
2. **Via Migração**: `psql -f database/migrations/003_populate_unified.sql`
3. **Programaticamente**: `crawler.refresh_unified_tables()`

---

## Referências

- [WCVP Distribution Data](https://powo.science.kew.org/)
- [TDWG Level 3 Regions](https://github.com/tdwg/wgsrpd)
- [PostGIS Spatial Functions](https://postgis.net/docs/)
