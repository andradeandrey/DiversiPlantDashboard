# Climate Pipeline — Methodology, Decisions & Limitations

## Overview

DiversiPlant uses bioclimatic matching to recommend species suitable for a given
location. The pipeline has three stages: data acquisition, envelope construction,
and real-time scoring.

```
WorldClim 2.1          WCVP Distributions        GBIF/TreeGOER Occurrences
   (raster)               (TDWG L3)                  (lat/lon / ecoregion)
       ↓                      ↓                            ↓
 tdwg_climate ←──── species_regions ───→ species_climate_envelope
       ↓                                        ↓
 get_bioclim_at_coords()            calculate_climate_match()
       ↓                                        ↓
    User point                           Suitability score 0–1
```

## 1. Data Sources

### WorldClim 2.1 (BIO1–BIO19)
- **Resolution**: 10 arc-min (~18 km at equator)
- **Storage**: PostGIS rasters in `worldclim_rasters` table
- **Usage**: Zonal statistics per TDWG Level 3 region → `tdwg_climate`
- **Variables used in scoring**: BIO1, BIO5, BIO6, BIO12, BIO15

### WCVP Distribution (Kew)
- **Table**: `species_regions` (1.36M records)
- **Granularity**: TDWG Level 3 (~370 botanical countries)
- **Fields**: `is_native`, `is_endemic` (derived: species in exactly 1 TDWG region)
- **Limitation**: Region-level granularity means species envelope = average of entire
  botanical countries. A species native to "Brazil South" gets the climate average of
  Paraná + Santa Catarina + Rio Grande do Sul, even if it only occurs in highland areas.

### EcoCrop (FAO)
- **Table**: `climate_envelope_ecocrop` (~2,568 cultivated species)
- **Data**: Optimal/absolute temperature and rainfall ranges
- **Limitation**: Only covers agricultural/cultivated species. Ranges are expert-curated,
  not occurrence-derived.

### GBIF S3 Occurrences
- **Table**: `climate_envelope_gbif` (~14,410 species)
- **Data**: Percentile-based envelopes (P05–P95) from individual coordinates
- **Quality**: Highest precision (lat/lon → WorldClim pixel), but lowest coverage

### TreeGOER / Ecoregions
- **Table**: `climate_envelope_ecoregion` (~46,054 species)
- **Data**: Climate derived from ecoregion centroids
- **Quality**: Medium precision, good coverage for trees

## 2. Climate Envelope Construction

### WCVP-based (primary)
Built in Migration 009 (updated in 015):

```sql
INSERT INTO species_climate_envelope
SELECT s.id,
    AVG(c.bio1_mean),           -- temp_mean
    MIN(c.bio1_min),            -- temp_min (coldest pixel in native range)
    MAX(c.bio1_max),            -- temp_max
    AVG(c.bio12_mean),          -- precip_mean
    AVG(c.bio15_mean),          -- precip_seasonality
    MIN(c.bio6_mean),           -- cold_month_min
    MAX(c.bio5_mean),           -- warm_month_max
FROM species s
JOIN species_regions sr ON ... AND sr.is_native = TRUE
JOIN tdwg_climate c ON sr.tdwg_code = c.tdwg_code
GROUP BY s.id
HAVING COUNT(DISTINCT sr.tdwg_code) >= 1   -- Was >= 2 before fix A2
```

**Key decision**: Lowered threshold from 2 to 1 TDWG region to include narrow-range
species (herbs, vines, epiphytes that only occur in 1 botanical country). This
increased coverage from 157,984 → 362,016 species.

### Unified View (prioritized)
Migration 011 creates `species_climate_envelope_unified`:

**Priority**: GBIF > TreeGOER/Ecoregion > WCVP

Rationale: Individual occurrence coordinates (GBIF) give the most precise climate
estimate. Ecoregion centroids are more precise than TDWG region averages.

## 3. Scoring Function

`calculate_climate_match(species_id, bio1, bio5, bio6, bio12, bio15) → DECIMAL|NULL`

### Weights
| Component              | Weight | Logic                                    |
|------------------------|--------|------------------------------------------|
| Temperature mean       | 25%    | Linear decay, ±10°C tolerance            |
| Temperature extremes   | 25%    | HARD FILTER: 0 if lethal, else full      |
| Precipitation match    | 20%    | Relative to species mean                 |
| Precip. seasonality    | 15%    | Linear decay, ±50 CV tolerance           |
| Cold hardiness         | 15%    | Frost tolerance check                    |

### Return values
- **NULL**: No envelope data → treated as "unknown" (passes filter)
- **0**: Outside lethal temperature bounds (BIO5/BIO6 ±3°C)
- **0.01–0.99**: Partial suitability
- **1.0**: Perfect match (theoretically possible but unlikely)

### Ecoregion tab filter
```sql
WHERE calculate_climate_match(...) IS NULL      -- pass: no data
   OR calculate_climate_match(...) >= :threshold -- pass: above threshold
```
Default threshold: 0.3 (30% suitability)

## 4. Known Limitations

### L1: TDWG granularity
WCVP distributions use TDWG Level 3 (~370 regions). A species in "BZS" (Brazil South)
could inhabit only coastal lowlands, but its envelope includes the entire region's
climate range. This inflates tolerance bounds.

**Mitigation**: Use GBIF/TreeGOER envelopes when available (higher precision).

### L2: Missing envelopes for cultivated species
Cultivated species (oregano, ginger, rosemary) have no WCVP distribution for the
cultivation region, only for native range. Climate suitability is computed against
native range, which may differ from cultivation range.

**Mitigation**: EcoCrop fills this gap with expert-curated tolerance ranges for
~2,568 cultivated species.

### L3: Climate stationarity assumption
WorldClim 2.1 uses 1970–2000 averages. Current climate may differ significantly,
especially for temperature extremes (BIO5, BIO6).

**Mitigation**: The ±3°C buffer in the hard filter partially compensates.

### L4: No microclimate data
Urban heat islands, elevation-dependent lapse rates, and irrigated areas are not
captured by 10 arc-min resolution rasters.

### L5: Single envelope per species
Each species has one climate envelope from its native range. No distinction between
subspecies, varieties, or local adaptations (ecotypes).

### L6: Precipitation seasonality mismatch
BIO15 (coefficient of variation) treats monsoonal and bimodal rainfall patterns
identically. A species adapted to two dry seasons may score poorly in a region with
one long dry season, despite similar total rainfall.

## 5. Workarounds Implemented

| Fix   | Problem                                | Solution                                    |
|-------|----------------------------------------|---------------------------------------------|
| A2-F1 | `calculate_climate_match()` returned 0 | Changed to return NULL for missing envelopes|
|       | for missing envelopes                  |                                             |
| A2-F2 | HAVING >= 2 excluded narrow-range spp  | Lowered to >= 1 TDWG region                 |
| A2-F3 | Threshold filter excluded score=0      | NULL bypasses filter (unknown ≠ unsuitable) |
| M015  | EcoCrop species had no WCVP envelope   | EcoCrop maps to species_climate_envelope    |
| M011  | Only WCVP data used, ignoring GBIF     | Unified view with GBIF > eco > WCVP        |

## 6. Coverage Statistics

As of March 2026:

| Source           | Species with envelope | Precision |
|------------------|-----------------------|-----------|
| WCVP             | ~362,016              | Low       |
| TreeGOER         | ~46,054               | Medium    |
| GBIF S3          | ~14,410               | High      |
| EcoCrop          | ~2,568                | Expert    |
| **Total unique** | **~362,016**          |           |

## 7. Files Reference

| File                                    | Purpose                              |
|-----------------------------------------|--------------------------------------|
| `crawlers/worldclim.py`                 | WorldClim data download & processing |
| `crawlers/populate_tdwg_climate.py`     | TDWG region climate population       |
| `crawlers/ecocrop.py`                   | EcoCrop cultivated species data      |
| `database/migrations/006_*`             | tdwg_climate table                   |
| `database/migrations/009_*`             | climate envelope + scoring function  |
| `database/migrations/010_*`             | Multi-source envelope tables         |
| `database/migrations/011_*`             | Unified prioritized view             |
| `database/migrations/015_*`             | NULL fix + 1-region threshold        |
| `admin_tabs/tab_ecoregion.py`           | Ecoregion species with climate score |
| `database/connection.py`                | `get_bioclim_at_coords()` etc.       |
