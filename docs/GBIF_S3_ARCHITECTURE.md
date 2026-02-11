# Arquitetura GBIF S3 e Pipeline de Extração

## Dados no S3

O GBIF disponibiliza dados de ocorrências no AWS S3 como **Parquet files**:

```
s3://gbif-open-data-us-east-1/occurrence/2024-10-01/occurrence.parquet/
├── 000000  (~100MB cada)
├── 000001
├── 000002
├── ...
└── 002770  (total ~2771 arquivos, ~270GB)
```

Cada arquivo contém **milhões de registros** de ocorrências de todas as espécies (não só plantas).

### Campos Principais

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `gbifid` | BIGINT | ID único da ocorrência |
| `specieskey` | BIGINT | Chave taxonômica (usamos para JOIN) |
| `decimallatitude` | DOUBLE | Latitude |
| `decimallongitude` | DOUBLE | Longitude |
| `coordinateuncertaintyinmeters` | INT | Precisão em metros |
| `year` | INT | Ano da coleta |
| `countrycode` | VARCHAR | Código do país |
| `kingdom` | VARCHAR | Reino (filtramos por 'Plantae') |

## Consulta DuckDB

O script usa **DuckDB** para consultar S3 diretamente (sem baixar):

```sql
SELECT
    occ.gbifid,
    sk.species_id,          -- nosso ID interno
    occ.decimallatitude,
    occ.decimallongitude,
    occ.coordinateuncertaintyinmeters,
    occ.year,
    occ.countrycode
FROM read_parquet('s3://gbif.../000000', 's3://gbif.../000001', ...)  -- arquivos S3
INNER JOIN species_keys sk ON occ.specieskey = sk.gbif_taxon_key     -- só nossas species
WHERE
    occ.kingdom = 'Plantae'                    -- só plantas
    AND occ.decimallatitude IS NOT NULL       -- com coordenadas
    AND occ.coordinateuncertaintyinmeters <= 10000  -- precisão ≤10km
    AND occ.year >= 1970                      -- dados recentes
```

## Pipeline de Batches

```
┌─────────────────────────────────────────────────────────────────┐
│ BATCH MODE (--species-limit 11500 --max-files 1000)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: EXPORT                                                │
│  ├── Query PostgreSQL: species SEM envelope + COM gbif_key      │
│  ├── LIMIT 11500 (5% do total)                                  │
│  └── Output: species_keys.parquet                               │
│                                                                 │
│  Phase 2: EXTRACT                                               │
│  ├── DuckDB query S3 (arquivos 0-999 ou 1000-1999)             │
│  ├── INNER JOIN com species_keys (só nossas species)           │
│  ├── Filtros: Plantae, coords válidas, uncertainty ≤10km       │
│  ├── MAX 500 ocorrências por species (melhores primeiro)       │
│  └── Output: occurrences_extract.parquet                        │
│                                                                 │
│  Phase 3: LOAD                                                  │
│  ├── COPY para PostgreSQL (staging table)                       │
│  ├── INSERT ON CONFLICT DO NOTHING (evita duplicatas)          │
│  └── ~100k rows por chunk                                       │
│                                                                 │
│  Phase 4: CLIMATE                                               │
│  ├── Para cada coordenada única                                │
│  ├── get_climate_json_at_point(lat, lon) → WorldClim rasters   │
│  └── UPDATE gbif_occurrences SET bio1, bio5, bio6...           │
│                                                                 │
│  Phase 5: ENVELOPE                                              │
│  ├── Agrupa por species_id                                     │
│  ├── HAVING COUNT(*) >= 10 (threshold)                         │
│  ├── Calcula: MIN, MAX, AVG, PERCENTILE de temp/precip         │
│  └── UPSERT em climate_envelope_gbif                           │
│                                                                 │
│  → Próximo batch (species que ganharam envelope são excluídas) │
└─────────────────────────────────────────────────────────────────┘
```

## Comandos

### Rodar batch com arquivos 0-999
```bash
source .venv/bin/activate
DATABASE_URL="postgresql://diversiplant:diversiplant_dev@localhost:5432/diversiplant" \
python scripts/load_gbif_s3.py --batch-mode --species-limit 11500 --max-files 1000 --start-file 0
```

### Rodar batch com arquivos 1000-1999
```bash
source .venv/bin/activate
DATABASE_URL="postgresql://diversiplant:diversiplant_dev@localhost:5432/diversiplant" \
python scripts/load_gbif_s3.py --batch-mode --species-limit 11500 --max-files 1000 --start-file 1000
```

### Ver status
```bash
source .venv/bin/activate
DATABASE_URL="postgresql://diversiplant:diversiplant_dev@localhost:5432/diversiplant" \
python scripts/load_gbif_s3.py --status
```

## Por que dividir em arquivos 0-999 e 1000-1999?

1. **Rate limiting**: S3 bloqueia queries muito longas (~200GB de uma vez)
2. **Distribuição**: Species diferentes estão em arquivos diferentes
3. **Resumabilidade**: Se falhar, não perde tudo

## Parâmetros do Script

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| `--batch-mode` | false | Processa em batches até terminar |
| `--species-limit` | 11500 | Species por batch (~5% do total) |
| `--max-files` | todos | Limite de arquivos S3 a escanear |
| `--start-file` | 0 | Arquivo inicial (para escanear ranges diferentes) |
| `--phase` | todos | Rodar fase específica (export/extract/load/climate/envelope) |
| `--force` | false | Forçar re-execução mesmo se arquivos existem |
| `--status` | false | Mostrar status e sair |

## Constantes Importantes

```python
# scripts/load_gbif_s3.py

MAX_UNCERTAINTY_M = 10000          # Precisão máxima aceita (10km)
MIN_YEAR = 1970                    # Ano mínimo da coleta
MAX_OCCURRENCES_PER_SPECIES = 500  # Máximo de ocorrências por species
MIN_OCCURRENCES_FOR_ENVELOPE = 10  # Mínimo para criar envelope (era 20)
```

## Schema PostgreSQL

### Tabela: gbif_occurrences
```sql
CREATE TABLE gbif_occurrences (
    gbif_id BIGINT PRIMARY KEY,
    species_id INTEGER REFERENCES species(id),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    coordinate_uncertainty_m INTEGER,
    year INTEGER,
    country_code VARCHAR(2),
    bio1 DECIMAL(6,2),   -- Mean Annual Temperature
    bio5 DECIMAL(6,2),   -- Max Temp Warmest Month
    bio6 DECIMAL(6,2),   -- Min Temp Coldest Month
    bio7 DECIMAL(6,2),   -- Temperature Annual Range
    bio12 DECIMAL(8,2),  -- Annual Precipitation
    bio15 DECIMAL(6,2)   -- Precipitation Seasonality
);
```

### Tabela: climate_envelope_gbif
```sql
CREATE TABLE climate_envelope_gbif (
    species_id INTEGER PRIMARY KEY REFERENCES species(id),
    temp_mean DECIMAL,
    temp_p05 DECIMAL,
    temp_p95 DECIMAL,
    temp_min DECIMAL,
    temp_max DECIMAL,
    precip_mean DECIMAL,
    precip_p05 DECIMAL,
    precip_p95 DECIMAL,
    precip_min DECIMAL,
    precip_max DECIMAL,
    n_occurrences INTEGER,
    n_countries INTEGER,
    envelope_quality VARCHAR,  -- 'high', 'medium', 'low'
    updated_at TIMESTAMP
);
```

## Status Típico

```
=== GBIF S3 Loader Status ===

  Species pending GBIF envelope: 218,349
  GBIF occurrences total: 1,160,568
    With climate: 1,154,300
  GBIF envelopes: 14,400
    high: 2,524
    medium: 2,202
    low: 9,674

  Coverage by growth form:
    graminoid: 36.4%
    aquatic: 9.9%
    other: 7.6%
    forb: 5.6%
    subshrub: 2.7%
    shrub: 1.2%
    herb: 0.8%
    tree: 0.6%
```
