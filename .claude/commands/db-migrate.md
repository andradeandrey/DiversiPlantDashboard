---
name: db-migrate
description: Aplica migrações do banco de dados
---

# Migrações do Banco de Dados

Aplica o schema e migrações pendentes ao banco PostgreSQL.

## Verificar Conexão

```bash
psql -h localhost -U diversiplant -d diversiplant -c "SELECT version();"
```

## Verificar PostGIS

```bash
psql -h localhost -U diversiplant -d diversiplant -c "SELECT PostGIS_version();"
```

## Aplicar Schema Inicial

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
psql -h localhost -U diversiplant -d diversiplant -f database/schema.sql
```

## Verificar Tabelas Criadas

```bash
psql -h localhost -U diversiplant -d diversiplant -c "\dt"
```

## Verificar Status dos Crawlers

```bash
psql -h localhost -U diversiplant -d diversiplant -c "SELECT * FROM crawler_status;"
```

## Listar Migrações Disponíveis

```bash
ls -la /Users/andreyandrade/Code/DiversiPlantDashboard-sticky/database/migrations/
```

## Aplicar Migrações de Schema Unificado

As migrações 002 e 003 criam e populam as tabelas otimizadas para queries espaciais.

### Migração 002: Criar Tabelas Unificadas

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
psql -h localhost -U diversiplant -d diversiplant -f database/migrations/002_unified_schema.sql
```

Esta migração cria:
- `species_unified`: Traits consolidados (prioridade: gift > reflora > wcvp > treegoer)
- `species_regions`: Distribuição geográfica por código TDWG (elimina JOINs com wcvp_distribution)
- `species_geometry`: Polígonos PostGIS pré-calculados para ranges de espécies

### Migração 003: Popular Tabelas

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
psql -h localhost -U diversiplant -d diversiplant -f database/migrations/003_populate_unified.sql
```

Esta migração:
1. Popula `species_regions` a partir de `wcvp_distribution`
2. Popula `species_unified` com traits consolidados (com prioridade de fontes)
3. Gera geometrias PostGIS para `species_geometry`

### Verificar Migração

```bash
psql -h localhost -U diversiplant -d diversiplant -c "
SELECT 'species_unified' as tabela, COUNT(*) FROM species_unified
UNION ALL SELECT 'species_regions', COUNT(*) FROM species_regions
UNION ALL SELECT 'species_geometry', COUNT(*) FROM species_geometry;"
```

### Testar Query Otimizada

```bash
# Query antiga (~444ms com 4 JOINs)
psql -h localhost -U diversiplant -d diversiplant -c "
EXPLAIN ANALYZE
SELECT COUNT(DISTINCT s.id)
FROM species s
JOIN wcvp_distribution wd ON s.wcvp_id = wd.taxon_id
JOIN species_traits st ON s.id = st.species_id
WHERE wd.tdwg_code = 'BZL' AND st.growth_form = 'tree';"

# Query nova (~50ms com 2 JOINs)
psql -h localhost -U diversiplant -d diversiplant -c "
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM species_unified su
JOIN species_regions sr ON su.species_id = sr.species_id
WHERE sr.tdwg_code = 'BZL' AND su.is_tree = TRUE;"
```

## Criar Nova Migração

Para criar uma nova migração, crie um arquivo em `database/migrations/` com o formato:
`NNN_description.sql` (onde NNN é o próximo número sequencial)

Exemplo:
```bash
touch /Users/andreyandrade/Code/DiversiPlantDashboard-sticky/database/migrations/004_add_new_column.sql
```
