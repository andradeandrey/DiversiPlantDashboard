-- Migration 017: Species uses table for WCUPS and other use data (M2)
--
-- Stores standardized plant use categories per species.
-- WCUPS uses EBDCS Level 1 codes:
--   ME = Materials, MA = Medicines, EU = Environmental Uses,
--   HF = Human Food, GS = Gene Sources, AF = Animal Food,
--   PO = Poisons, SU = Social Uses, FU = Fuels, IF = Invertebrate Food
--
-- Other sources (ecocrop, practitioners) can also write here.

CREATE TABLE IF NOT EXISTS species_uses (
    id SERIAL PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    use_code VARCHAR(10) NOT NULL,       -- EBDCS code: ME, MA, EU, HF, GS, AF, PO, SU, FU, IF
    use_label VARCHAR(50),               -- Human-readable: 'Materials', 'Medicines', etc.
    is_cwr BOOLEAN DEFAULT FALSE,        -- Crop Wild Relative flag (WCUPS)
    source VARCHAR(50) NOT NULL,         -- 'wcups', 'ecocrop', 'practitioners'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(species_id, use_code, source)
);

CREATE INDEX IF NOT EXISTS idx_species_uses_species ON species_uses(species_id);
CREATE INDEX IF NOT EXISTS idx_species_uses_code ON species_uses(use_code);
CREATE INDEX IF NOT EXISTS idx_species_uses_source ON species_uses(source);
