-- DiversiPlant Database Schema
-- PostgreSQL 16 + PostGIS 3.4

-- Habilitar PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- =============================================
-- TABELAS CORE
-- =============================================

CREATE TABLE species (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL UNIQUE,
    genus VARCHAR(100),
    family VARCHAR(100),
    wcvp_id VARCHAR(50),
    gbif_taxon_key BIGINT,
    gift_work_id INTEGER,
    reflora_id VARCHAR(100),
    iucn_taxon_id INTEGER,
    taxonomic_status VARCHAR(50), -- 'accepted', 'synonym', 'unresolved'
    accepted_name_id INTEGER REFERENCES species(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_species_canonical ON species(canonical_name);
CREATE INDEX idx_species_family ON species(family);
CREATE INDEX idx_species_genus ON species(genus);

CREATE TABLE species_traits (
    id SERIAL PRIMARY KEY,
    species_id INTEGER REFERENCES species(id) ON DELETE CASCADE,
    growth_form VARCHAR(50),
    max_height_m DECIMAL(10,2),
    stratum VARCHAR(20),
    life_form VARCHAR(100),
    woodiness VARCHAR(50),
    nitrogen_fixer BOOLEAN,
    dispersal_syndrome VARCHAR(100),
    deciduousness VARCHAR(50),
    source VARCHAR(50), -- 'gift', 'wcvp', 'practitioners'
    confidence DECIMAL(3,2),
    -- Raw GIFT trait values for audit (Climber.R logic)
    _gift_trait_1_2_2 VARCHAR(100), -- Original growth form from GIFT
    _gift_trait_1_4_2 VARCHAR(100), -- Original climber type from GIFT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_traits_species ON species_traits(species_id);
CREATE INDEX idx_traits_growth_form ON species_traits(growth_form);

CREATE TABLE common_names (
    id SERIAL PRIMARY KEY,
    species_id INTEGER REFERENCES species(id) ON DELETE CASCADE,
    common_name VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL, -- 'pt', 'en'
    source VARCHAR(100),
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(species_id, common_name, language)
);

CREATE INDEX idx_common_names_species ON common_names(species_id);
CREATE INDEX idx_common_names_lang ON common_names(language);

-- =============================================
-- TABELAS GEOGRAFICAS
-- =============================================

CREATE TABLE ecoregions (
    id SERIAL PRIMARY KEY,
    eco_id INTEGER UNIQUE,
    eco_name VARCHAR(255),
    biome_name VARCHAR(255),
    biome_num INTEGER,
    realm VARCHAR(50),
    geom GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX idx_ecoregions_geom ON ecoregions USING GIST(geom);
CREATE INDEX idx_ecoregions_biome ON ecoregions(biome_name);

CREATE TABLE tdwg_level3 (
    id SERIAL PRIMARY KEY,
    level3_code VARCHAR(10) UNIQUE,
    level3_name VARCHAR(255),
    level2_code VARCHAR(10),
    continent VARCHAR(50),
    geom GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX idx_tdwg_geom ON tdwg_level3 USING GIST(geom);
CREATE INDEX idx_tdwg_code ON tdwg_level3(level3_code);

CREATE TABLE species_distribution (
    id SERIAL PRIMARY KEY,
    species_id INTEGER REFERENCES species(id) ON DELETE CASCADE,
    tdwg_code VARCHAR(10),
    native BOOLEAN DEFAULT FALSE,
    endemic BOOLEAN DEFAULT FALSE,
    introduced BOOLEAN DEFAULT FALSE,
    source VARCHAR(50),
    UNIQUE(species_id, tdwg_code)
);

CREATE INDEX idx_distribution_species ON species_distribution(species_id);
CREATE INDEX idx_distribution_tdwg ON species_distribution(tdwg_code);

-- WCVP Distribution (dados brutos do WCVP para JOINs via taxon_id/wcvp_id)
CREATE TABLE wcvp_distribution (
    id SERIAL PRIMARY KEY,
    taxon_id VARCHAR(50) NOT NULL,  -- wcvp plant_name_id
    tdwg_code VARCHAR(10) NOT NULL,
    establishment_means VARCHAR(20), -- 'native', 'introduced'
    endemic VARCHAR(5),              -- '0' or '1'
    introduced VARCHAR(5),           -- '0' or '1'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(taxon_id, tdwg_code)
);

CREATE INDEX idx_wcvp_dist_taxon ON wcvp_distribution(taxon_id);
CREATE INDEX idx_wcvp_dist_tdwg ON wcvp_distribution(tdwg_code);
CREATE INDEX idx_wcvp_dist_native ON wcvp_distribution(tdwg_code)
    WHERE establishment_means = 'native';

-- =============================================
-- TABELA DE CLIMA (WorldClim Bio Variables)
-- =============================================

CREATE TABLE tdwg_climate (
    id SERIAL PRIMARY KEY,
    tdwg_code VARCHAR(10) NOT NULL UNIQUE REFERENCES tdwg_level3(level3_code),
    -- Temperature variables (°C, stored as actual values)
    bio1_mean DECIMAL(6,2),   -- Annual Mean Temperature
    bio1_min DECIMAL(6,2),
    bio1_max DECIMAL(6,2),
    bio2_mean DECIMAL(6,2),   -- Mean Diurnal Range
    bio3_mean DECIMAL(6,2),   -- Isothermality (%)
    bio4_mean DECIMAL(8,2),   -- Temperature Seasonality (std dev * 100)
    bio5_mean DECIMAL(6,2),   -- Max Temp of Warmest Month
    bio6_mean DECIMAL(6,2),   -- Min Temp of Coldest Month
    bio7_mean DECIMAL(6,2),   -- Temperature Annual Range
    bio8_mean DECIMAL(6,2),   -- Mean Temp of Wettest Quarter
    bio9_mean DECIMAL(6,2),   -- Mean Temp of Driest Quarter
    bio10_mean DECIMAL(6,2),  -- Mean Temp of Warmest Quarter
    bio11_mean DECIMAL(6,2),  -- Mean Temp of Coldest Quarter
    -- Precipitation variables (mm)
    bio12_mean DECIMAL(8,2),  -- Annual Precipitation
    bio12_min DECIMAL(8,2),
    bio12_max DECIMAL(8,2),
    bio13_mean DECIMAL(8,2),  -- Precipitation of Wettest Month
    bio14_mean DECIMAL(8,2),  -- Precipitation of Driest Month
    bio15_mean DECIMAL(6,2),  -- Precipitation Seasonality (CV)
    bio16_mean DECIMAL(8,2),  -- Precipitation of Wettest Quarter
    bio17_mean DECIMAL(8,2),  -- Precipitation of Driest Quarter
    bio18_mean DECIMAL(8,2),  -- Precipitation of Warmest Quarter
    bio19_mean DECIMAL(8,2),  -- Precipitation of Coldest Quarter
    -- Derived classifications
    koppen_zone VARCHAR(10),      -- Köppen climate classification
    whittaker_biome VARCHAR(50),  -- Whittaker biome from temp/precip
    aridity_index DECIMAL(6,3),   -- bio12 / (bio1 + 10) * 10
    -- Metadata
    pixel_count INTEGER,       -- Number of valid pixels used
    resolution VARCHAR(10),    -- WorldClim resolution used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tdwg_climate_code ON tdwg_climate(tdwg_code);
CREATE INDEX idx_tdwg_climate_biome ON tdwg_climate(whittaker_biome);
CREATE INDEX idx_tdwg_climate_koppen ON tdwg_climate(koppen_zone);

-- Trigger para atualizar timestamp
CREATE TRIGGER trigger_tdwg_climate_updated_at
    BEFORE UPDATE ON tdwg_climate
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================
-- TABELAS DE CRAWLERS
-- =============================================

CREATE TABLE crawler_status (
    id SERIAL PRIMARY KEY,
    crawler_name VARCHAR(50) UNIQUE,
    status VARCHAR(20) DEFAULT 'idle',
    last_run TIMESTAMP,
    last_success TIMESTAMP,
    records_processed INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    next_scheduled TIMESTAMP
);

CREATE TABLE crawler_logs (
    id SERIAL PRIMARY KEY,
    crawler_name VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(10), -- 'ERROR', 'WARNING', 'INFO', 'DEBUG'
    message TEXT,
    details JSONB
);
CREATE INDEX idx_crawler_logs_ts ON crawler_logs(timestamp DESC);
CREATE INDEX idx_crawler_logs_name ON crawler_logs(crawler_name);
CREATE INDEX idx_crawler_logs_level ON crawler_logs(level);

CREATE TABLE crawler_runs (
    id SERIAL PRIMARY KEY,
    crawler_name VARCHAR(50),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20),
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX idx_crawler_runs_name ON crawler_runs(crawler_name);
CREATE INDEX idx_crawler_runs_started ON crawler_runs(started_at DESC);

-- =============================================
-- TABELAS DE METRICAS
-- =============================================

CREATE TABLE user_access_log (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    ip_address INET,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    page VARCHAR(100),
    action VARCHAR(50),
    details JSONB
);

CREATE INDEX idx_access_log_ts ON user_access_log(timestamp DESC);
CREATE INDEX idx_access_log_session ON user_access_log(session_id);

-- =============================================
-- DADOS INICIAIS
-- =============================================

-- Dados iniciais dos crawlers
INSERT INTO crawler_status (crawler_name, status) VALUES
    ('reflora', 'idle'),
    ('gbif', 'idle'),
    ('gift', 'idle'),
    ('wcvp', 'idle'),
    ('worldclim', 'idle'),
    ('treegoer', 'idle'),
    ('iucn', 'idle'),
    ('try', 'idle'),
    ('practitioners', 'idle');

-- =============================================
-- FUNCOES AUXILIARES
-- =============================================

-- Funcao para atualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para species
CREATE TRIGGER trigger_species_updated_at
    BEFORE UPDATE ON species
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Funcao para buscar ecorregiao por coordenadas
CREATE OR REPLACE FUNCTION get_ecoregion_by_coords(lat DOUBLE PRECISION, lon DOUBLE PRECISION)
RETURNS TABLE(eco_name VARCHAR, biome_name VARCHAR, biome_num INTEGER, realm VARCHAR) AS $$
BEGIN
    RETURN QUERY
    SELECT e.eco_name, e.biome_name, e.biome_num, e.realm
    FROM ecoregions e
    WHERE ST_Contains(e.geom, ST_SetSRID(ST_Point(lon, lat), 4326))
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Funcao para buscar TDWG por coordenadas
CREATE OR REPLACE FUNCTION get_tdwg_by_coords(lat DOUBLE PRECISION, lon DOUBLE PRECISION)
RETURNS TABLE(level3_code VARCHAR, level3_name VARCHAR, continent VARCHAR) AS $$
BEGIN
    RETURN QUERY
    SELECT t.level3_code, t.level3_name, t.continent
    FROM tdwg_level3 t
    WHERE ST_Contains(t.geom, ST_SetSRID(ST_Point(lon, lat), 4326))
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;
