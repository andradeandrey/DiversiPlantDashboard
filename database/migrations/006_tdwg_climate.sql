-- Migration 006: Add WorldClim climate data per TDWG region
-- Stores all 19 bioclimatic variables (bio1-bio19) for each TDWG Level 3 region

-- Check if update_updated_at function exists, create if not
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Table for WorldClim bioclimatic data per TDWG region
CREATE TABLE IF NOT EXISTS tdwg_climate (
    id SERIAL PRIMARY KEY,
    tdwg_code VARCHAR(10) NOT NULL UNIQUE,

    -- Temperature variables (°C)
    bio1_mean DECIMAL(6,2),   -- Annual Mean Temperature
    bio1_min DECIMAL(6,2),    -- Min within region
    bio1_max DECIMAL(6,2),    -- Max within region
    bio2_mean DECIMAL(6,2),   -- Mean Diurnal Range
    bio3_mean DECIMAL(6,2),   -- Isothermality (%)
    bio4_mean DECIMAL(12,2),  -- Temperature Seasonality (std dev * 100)
    bio5_mean DECIMAL(6,2),   -- Max Temp of Warmest Month
    bio6_mean DECIMAL(6,2),   -- Min Temp of Coldest Month
    bio7_mean DECIMAL(6,2),   -- Temperature Annual Range
    bio8_mean DECIMAL(6,2),   -- Mean Temp of Wettest Quarter
    bio9_mean DECIMAL(6,2),   -- Mean Temp of Driest Quarter
    bio10_mean DECIMAL(6,2),  -- Mean Temp of Warmest Quarter
    bio11_mean DECIMAL(6,2),  -- Mean Temp of Coldest Quarter

    -- Precipitation variables (mm)
    bio12_mean DECIMAL(10,2), -- Annual Precipitation
    bio12_min DECIMAL(10,2),  -- Min within region
    bio12_max DECIMAL(10,2),  -- Max within region
    bio13_mean DECIMAL(10,2), -- Precipitation of Wettest Month
    bio14_mean DECIMAL(10,2), -- Precipitation of Driest Month
    bio15_mean DECIMAL(10,2), -- Precipitation Seasonality (CV)
    bio16_mean DECIMAL(10,2), -- Precipitation of Wettest Quarter
    bio17_mean DECIMAL(10,2), -- Precipitation of Driest Quarter
    bio18_mean DECIMAL(10,2), -- Precipitation of Warmest Quarter
    bio19_mean DECIMAL(10,2), -- Precipitation of Coldest Quarter

    -- Derived classifications
    koppen_zone VARCHAR(10),       -- Köppen climate classification (Af, Am, BWh, Cfb, etc.)
    whittaker_biome VARCHAR(50),   -- Whittaker biome from temp/precip
    aridity_index DECIMAL(10,3),   -- P / (T + 10) * 10

    -- Metadata
    pixel_count INTEGER,       -- Number of valid pixels used in calculation
    resolution VARCHAR(10),    -- WorldClim resolution used (10m, 5m, 2.5m, 30s)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tdwg_climate_code ON tdwg_climate(tdwg_code);
CREATE INDEX IF NOT EXISTS idx_tdwg_climate_biome ON tdwg_climate(whittaker_biome);
CREATE INDEX IF NOT EXISTS idx_tdwg_climate_koppen ON tdwg_climate(koppen_zone);
CREATE INDEX IF NOT EXISTS idx_tdwg_climate_temp ON tdwg_climate(bio1_mean);
CREATE INDEX IF NOT EXISTS idx_tdwg_climate_precip ON tdwg_climate(bio12_mean);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trigger_tdwg_climate_updated_at ON tdwg_climate;
CREATE TRIGGER trigger_tdwg_climate_updated_at
    BEFORE UPDATE ON tdwg_climate
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- View to join species with climate data via distribution
CREATE OR REPLACE VIEW v_species_climate AS
SELECT
    s.id as species_id,
    s.canonical_name,
    s.family,
    sd.tdwg_code,
    sd.native,
    c.bio1_mean as temp_mean,
    c.bio1_min as temp_min,
    c.bio1_max as temp_max,
    c.bio12_mean as precip_mean,
    c.bio12_min as precip_min,
    c.bio12_max as precip_max,
    c.bio4_mean as temp_seasonality,
    c.bio15_mean as precip_seasonality,
    c.whittaker_biome,
    c.koppen_zone,
    c.aridity_index
FROM species s
JOIN species_distribution sd ON s.id = sd.species_id
LEFT JOIN tdwg_climate c ON sd.tdwg_code = c.tdwg_code;

-- Aggregate view for species climate envelope
CREATE OR REPLACE VIEW v_species_climate_envelope AS
SELECT
    s.id as species_id,
    s.canonical_name,
    s.family,
    COUNT(DISTINCT sd.tdwg_code) as n_regions,
    AVG(c.bio1_mean) as temp_mean_avg,
    MIN(c.bio1_min) as temp_absolute_min,
    MAX(c.bio1_max) as temp_absolute_max,
    AVG(c.bio12_mean) as precip_mean_avg,
    MIN(c.bio12_min) as precip_absolute_min,
    MAX(c.bio12_max) as precip_absolute_max,
    AVG(c.aridity_index) as aridity_avg,
    MODE() WITHIN GROUP (ORDER BY c.whittaker_biome) as dominant_biome,
    MODE() WITHIN GROUP (ORDER BY c.koppen_zone) as dominant_koppen
FROM species s
JOIN species_distribution sd ON s.id = sd.species_id AND sd.native = TRUE
LEFT JOIN tdwg_climate c ON sd.tdwg_code = c.tdwg_code
WHERE c.bio1_mean IS NOT NULL
GROUP BY s.id, s.canonical_name, s.family;

COMMENT ON TABLE tdwg_climate IS 'WorldClim bioclimatic variables (bio1-bio19) aggregated per TDWG Level 3 region';
COMMENT ON VIEW v_species_climate IS 'Species distribution with climate data per region';
COMMENT ON VIEW v_species_climate_envelope IS 'Aggregated climate envelope per species (native distribution only)';
