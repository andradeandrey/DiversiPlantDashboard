---
name: check-data
description: Verifica qualidade dos dados no banco
---

# Verificação de Qualidade dos Dados

Executa consultas para verificar integridade e cobertura dos dados.

## Estatísticas Gerais

```bash
psql -d diversiplant -c "
SELECT
    (SELECT COUNT(*) FROM species) as total_species,
    (SELECT COUNT(*) FROM species_traits) as total_traits,
    (SELECT COUNT(*) FROM common_names) as total_common_names,
    (SELECT COUNT(DISTINCT species_id) FROM species_traits) as species_with_traits;
"
```

## Espécies Sem Growth Form

```bash
psql -d diversiplant -c "
SELECT s.canonical_name, s.family
FROM species s
LEFT JOIN species_traits st ON s.id = st.species_id
WHERE st.growth_form IS NULL
LIMIT 20;
"
```

## Cobertura de Nomes Comuns por Idioma

```bash
psql -d diversiplant -c "
SELECT
    language,
    COUNT(*) as count,
    COUNT(DISTINCT species_id) as unique_species
FROM common_names
GROUP BY language
ORDER BY count DESC;
"
```

## Status dos Crawlers

```bash
psql -d diversiplant -c "
SELECT
    crawler_name,
    status,
    last_success,
    records_processed,
    error_count,
    NOW() - last_success as time_since_last_run
FROM crawler_status
ORDER BY last_success DESC NULLS LAST;
"
```

## Erros Recentes

```bash
psql -d diversiplant -c "
SELECT timestamp, crawler_name, message
FROM crawler_logs
WHERE level = 'ERROR'
ORDER BY timestamp DESC
LIMIT 10;
"
```

## Cobertura por Família

```bash
psql -d diversiplant -c "
SELECT
    family,
    COUNT(*) as species_count,
    COUNT(st.growth_form) as with_growth_form
FROM species s
LEFT JOIN species_traits st ON s.id = st.species_id
GROUP BY family
ORDER BY species_count DESC
LIMIT 20;
"
```
