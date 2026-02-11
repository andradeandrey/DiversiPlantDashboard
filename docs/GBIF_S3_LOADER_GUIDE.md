# GBIF S3 Parquet Loader - Guia Completo

## Status Atual (2026-01-27)

### O que ja foi feito
- Script `scripts/load_gbif_s3.py` criado e funcional (1236 linhas)
- Virtual environment `.venv/` criado com dependencias: `sqlalchemy duckdb pyarrow psycopg2-binary numpy`
- Phase 1 (export) executada com sucesso: **229,072 species keys** exportadas para `data/gbif_s3/species_keys.parquet`
- Phase 2 (extract) **NAO INICIADA** - foi interrompida antes de comecar

### O que falta executar
1. **Phase 2: extract** - Query S3 Parquet via DuckDB (10-30 min, scan ~200GB no S3)
2. **Phase 3: load** - Carregar ocorrencias no PostgreSQL (5-15 min)
3. **Phase 4: climate** - Extrair clima WorldClim por ponto (BOTTLENECK: 8-24h)
4. **Phase 5: envelope** - Calcular envelopes por especie (5-10 min)

---

## Como Executar

### Ambiente
```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
source .venv/bin/activate
export DATABASE_URL="postgresql://diversiplant:diversiplant_dev@localhost:5432/diversiplant"
```

### Docker PostgreSQL
Container: `diversiplant-db` na porta 5432
- User: `diversiplant`
- Password: `diversiplant_dev`
- Database: `diversiplant`

### Verificar status
```bash
python3 scripts/load_gbif_s3.py --status
```

### Executar todas as fases
```bash
python3 scripts/load_gbif_s3.py 2>&1 | tee logs/gbif_s3.log
```

### Executar fase especifica
```bash
python3 scripts/load_gbif_s3.py --phase extract
python3 scripts/load_gbif_s3.py --phase load
python3 scripts/load_gbif_s3.py --phase climate --batch-size 10000
python3 scripts/load_gbif_s3.py --phase envelope
```

### Opcoes uteis
```bash
--snapshot 2024-10-01      # Snapshot GBIF especifico (default: 2024-10-01)
--memory-limit 8GB         # Mais memoria para DuckDB
--duckdb-batch-size 5000   # Processar species em batches (se OOM)
--batch-size 10000         # Batch size para extracao de clima
--force                    # Forcar re-execucao mesmo com arquivos existentes
--no-unique-coords         # Desabilitar otimizacao de coords unicas
--dry-run                  # Preview sem executar
--verbose                  # Logs detalhados
```

---

## Arquitetura do Pipeline

### Phase 1: Export (species_keys.parquet)
- Query PostgreSQL: species sem envelope GBIF + com gbif_taxon_key
- Output: `data/gbif_s3/species_keys.parquet`
- Resumibilidade: LEFT JOIN exclui species ja processadas

### Phase 2: Extract (occurrences_extract.parquet)
- DuckDB query contra S3: `s3://gbif-open-data-us-east-1/occurrence/{date}/occurrence.parquet/*`
- INNER JOIN em `specieskey = gbif_taxon_key` (inteiro, sem ambiguidade)
- Filtros: Plantae, lat/lon validos, uncertainty <= 10km, year >= 1970
- Sampling: MAX 500 por especie (melhores primeiro por uncertainty ASC, year DESC)
- Output: `data/gbif_s3/occurrences_extract.parquet`
- Resumibilidade: Skip se arquivo ja existe

### Phase 3: Load (PostgreSQL)
- Staging table + COPY FROM + INSERT ON CONFLICT DO NOTHING
- Chunks de 100k linhas
- Resumibilidade: ON CONFLICT (gbif_id) DO NOTHING

### Phase 4: Climate (WorldClim extraction)
- Usa `get_climate_json_at_point(lat, lon)` do PostgreSQL
- Otimizacao: extrai por coordenada unica primeiro (60-80% menos chamadas)
- Depois UPDATE por JOIN de volta
- Resumibilidade: WHERE bio1 IS NULL
- **BOTTLENECK**: 8-24h dependendo do volume

### Phase 5: Envelope (SQL aggregation)
- PERCENTILE_CONT para P05, P95
- MIN/MAX/AVG para bio vars
- COUNT DISTINCT country_code
- Quality: high >= 100, medium >= 50, low < 50
- Atualiza `climate_envelope_analysis` via `update_envelope_analysis()`
- Resumibilidade: ON CONFLICT (species_id) DO UPDATE

---

## Dados do GBIF S3

- **Bucket**: `s3://gbif-open-data-us-east-1/occurrence/YYYY-MM-DD/occurrence.parquet/*`
- **Tamanho**: ~200GB total, ~2000 arquivos Parquet por snapshot
- **Acesso**: Anonimo (sem credenciais)
- **Colunas usadas**: gbifid, specieskey, species, decimallatitude, decimallongitude, coordinateuncertaintyinmeters, year, countrycode, kingdom

---

## Tabelas PostgreSQL Envolvidas

### gbif_occurrences
```sql
CREATE TABLE gbif_occurrences (
    id SERIAL PRIMARY KEY,
    species_id INTEGER REFERENCES species(id),
    gbif_id BIGINT UNIQUE,
    latitude DECIMAL(10,6) NOT NULL,
    longitude DECIMAL(10,6) NOT NULL,
    coordinate_uncertainty_m INTEGER,
    year INTEGER,
    country_code VARCHAR(2),
    bio1 DECIMAL(6,2),   -- Annual Mean Temperature
    bio5 DECIMAL(6,2),   -- Max Temp Warmest Month
    bio6 DECIMAL(6,2),   -- Min Temp Coldest Month
    bio7 DECIMAL(6,2),   -- Temp Annual Range
    bio12 DECIMAL(8,2),  -- Annual Precipitation
    bio15 DECIMAL(6,2),  -- Precipitation Seasonality
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### climate_envelope_gbif
```sql
CREATE TABLE climate_envelope_gbif (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),
    temp_mean DECIMAL(6,2),
    temp_p05 DECIMAL(6,2),
    temp_p95 DECIMAL(6,2),
    temp_min DECIMAL(6,2),
    temp_max DECIMAL(6,2),
    cold_month_mean DECIMAL(6,2),
    cold_month_p05 DECIMAL(6,2),
    warm_month_mean DECIMAL(6,2),
    warm_month_p95 DECIMAL(6,2),
    precip_mean DECIMAL(8,2),
    precip_p05 DECIMAL(8,2),
    precip_p95 DECIMAL(8,2),
    precip_min DECIMAL(8,2),
    precip_max DECIMAL(8,2),
    precip_seasonality DECIMAL(6,2),
    n_occurrences INTEGER,
    n_countries INTEGER,
    year_range VARCHAR(20),
    envelope_quality VARCHAR(10),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### climate_envelope_analysis
Tabela de comparacao multi-source (GBIF + WCVP + Ecoregion).
Populada via funcao `update_envelope_analysis(species_id)`.

---

## Constantes / Filtros de Qualidade

```python
MAX_UNCERTAINTY_M = 10000          # 10km max coordinate uncertainty
MIN_YEAR = 1970                    # Occurrences desde 1970
MAX_OCCURRENCES_PER_SPECIES = 500  # Sampling max por especie
MIN_OCCURRENCES_FOR_ENVELOPE = 20  # Minimo para calcular envelope
CLIMATE_BIO_VARS = ['bio1', 'bio5', 'bio6', 'bio7', 'bio12', 'bio15']
```

---

## Performance Esperada

| Fase | Dados | Tempo | Memoria |
|------|-------|-------|---------|
| 1. Export keys | 229k linhas | <5s | Minimo |
| 2. S3 extract | ~20-30GB do S3 | 10-30 min | 4GB DuckDB |
| 3. PG load | ~30-50M linhas | 5-15 min | ~500MB |
| 4. Climate | unique coords ST_Value | **8-24h** | ~1GB |
| 5. Envelopes | 1 query agregacao | 5-10 min | ~2GB |

---

## Resultados Esperados

Apos execucao completa:
- ~30-50M ocorrencias na tabela `gbif_occurrences`
- ~200k+ envelopes na tabela `climate_envelope_gbif`
- Cobertura: ~70-90% das especies com gbif_taxon_key

---

## Arquivos Relacionados

| Arquivo | Descricao |
|---------|-----------|
| `scripts/load_gbif_s3.py` | Script principal (1236 linhas) |
| `data/gbif_s3/species_keys.parquet` | Species keys exportadas (229k) |
| `data/gbif_s3/occurrences_extract.parquet` | Ocorrencias extraidas (a gerar) |
| `database/migrations/010_climate_envelope_system.sql` | Schema das tabelas |
| `crawlers/gbif_occurrences.py` | Crawler API (referencia, rate-limited) |
| `crawlers/base.py` | Base class com DB pattern |
| `.venv/` | Virtual environment Python 3.14 |
| `docker-compose.yml` | Docker config (PostgreSQL) |
| `.env` | Variaveis de ambiente |

---

## Contexto do Projeto

O DiversiPlant Dashboard e um sistema de recomendacao de plantas para diversidade funcional.
O GBIF S3 Loader e parte do sistema de climate envelopes multi-source:

1. **WCVP envelopes**: 362,016 especies (ja populado)
2. **Ecoregion envelopes**: 46,767 especies (ja populado)
3. **GBIF envelopes**: 229,072 pendentes (este script)

O climate envelope de cada especie define a faixa climatica onde ela ocorre naturalmente,
usado pelo algoritmo de recomendacao para filtrar plantas adaptadas a uma regiao especifica.

### Plano completo
O plano completo do sistema esta em:
`/Users/andreyandrade/.claude/plans/mossy-dreaming-brooks.md`

### Proximo passo apos GBIF S3
Implementar o backend Go (recommendation.go) e frontend (index.html) do sistema de recomendacao.
