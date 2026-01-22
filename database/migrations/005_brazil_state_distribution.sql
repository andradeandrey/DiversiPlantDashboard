-- Migration 005: Add Brazilian state-level distribution from REFLORA
-- This provides more granular distribution data than TDWG Level 3

-- Table for Brazilian state distribution
CREATE TABLE IF NOT EXISTS species_distribution_brazil (
    id SERIAL PRIMARY KEY,
    species_id INTEGER REFERENCES species(id) ON DELETE CASCADE,
    state_code VARCHAR(5) NOT NULL,  -- BR-SC, BR-SP, etc.
    establishment VARCHAR(20),        -- NATIVA, CULTIVADA, NATURALIZADA
    is_endemic BOOLEAN DEFAULT FALSE,
    phytogeographic_domain TEXT[],    -- Amazônia, Mata Atlântica, Cerrado, etc.
    source VARCHAR(20) DEFAULT 'reflora',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(species_id, state_code)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_brazil_dist_species ON species_distribution_brazil(species_id);
CREATE INDEX IF NOT EXISTS idx_brazil_dist_state ON species_distribution_brazil(state_code);
CREATE INDEX IF NOT EXISTS idx_brazil_dist_endemic ON species_distribution_brazil(is_endemic) WHERE is_endemic = TRUE;
CREATE INDEX IF NOT EXISTS idx_brazil_dist_native ON species_distribution_brazil(establishment) WHERE establishment = 'NATIVA';

-- Mapping table: Brazilian states to TDWG Level 3
CREATE TABLE IF NOT EXISTS brazil_state_tdwg_map (
    state_code VARCHAR(5) PRIMARY KEY,  -- BR-SC
    state_name VARCHAR(50),              -- Santa Catarina
    tdwg_code VARCHAR(5)                 -- BZS
);

-- Populate mapping
INSERT INTO brazil_state_tdwg_map (state_code, state_name, tdwg_code) VALUES
    -- North (BZN)
    ('BR-AC', 'Acre', 'BZN'),
    ('BR-AM', 'Amazonas', 'BZN'),
    ('BR-AP', 'Amapá', 'BZN'),
    ('BR-PA', 'Pará', 'BZN'),
    ('BR-RO', 'Rondônia', 'BZN'),
    ('BR-RR', 'Roraima', 'BZN'),
    ('BR-TO', 'Tocantins', 'BZN'),
    -- Northeast (BZE)
    ('BR-AL', 'Alagoas', 'BZE'),
    ('BR-BA', 'Bahia', 'BZE'),
    ('BR-CE', 'Ceará', 'BZE'),
    ('BR-MA', 'Maranhão', 'BZE'),
    ('BR-PB', 'Paraíba', 'BZE'),
    ('BR-PE', 'Pernambuco', 'BZE'),
    ('BR-PI', 'Piauí', 'BZE'),
    ('BR-RN', 'Rio Grande do Norte', 'BZE'),
    ('BR-SE', 'Sergipe', 'BZE'),
    -- Central-West (BZC)
    ('BR-DF', 'Distrito Federal', 'BZC'),
    ('BR-GO', 'Goiás', 'BZC'),
    ('BR-MS', 'Mato Grosso do Sul', 'BZC'),
    ('BR-MT', 'Mato Grosso', 'BZC'),
    -- Southeast (BZL)
    ('BR-ES', 'Espírito Santo', 'BZL'),
    ('BR-MG', 'Minas Gerais', 'BZL'),
    ('BR-RJ', 'Rio de Janeiro', 'BZL'),
    ('BR-SP', 'São Paulo', 'BZL'),
    -- South (BZS)
    ('BR-PR', 'Paraná', 'BZS'),
    ('BR-RS', 'Rio Grande do Sul', 'BZS'),
    ('BR-SC', 'Santa Catarina', 'BZS')
ON CONFLICT (state_code) DO NOTHING;

-- View to easily query species by state with TDWG mapping
CREATE OR REPLACE VIEW v_species_brazil_distribution AS
SELECT
    s.id as species_id,
    s.canonical_name,
    s.family,
    sdb.state_code,
    bst.state_name,
    bst.tdwg_code,
    sdb.establishment,
    sdb.is_endemic,
    sdb.phytogeographic_domain
FROM species s
JOIN species_distribution_brazil sdb ON s.id = sdb.species_id
JOIN brazil_state_tdwg_map bst ON sdb.state_code = bst.state_code;

COMMENT ON TABLE species_distribution_brazil IS 'Brazilian state-level species distribution from REFLORA';
COMMENT ON TABLE brazil_state_tdwg_map IS 'Mapping between Brazilian state codes and TDWG Level 3 regions';
