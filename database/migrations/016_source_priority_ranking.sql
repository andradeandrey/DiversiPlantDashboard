-- Migration 016: Source priority ranking table (A6)
-- Configurable priority per attribute instead of hardcoded CASE statements.
-- Lower number = higher priority.

CREATE TABLE IF NOT EXISTS source_priority (
    id SERIAL PRIMARY KEY,
    attribute VARCHAR(50) NOT NULL,    -- 'growth_form', 'max_height_m', 'threat_status', 'lifespan_years', etc.
    source VARCHAR(50) NOT NULL,       -- 'gift', 'reflora', 'wcvp', 'treegoer', 'practitioners', 'try', 'cncflora', etc.
    priority INTEGER NOT NULL DEFAULT 99,
    notes TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(attribute, source)
);

-- Default priorities (matching current hardcoded logic)
-- growth_form: gift > reflora > wcvp > treegoer > practitioners
INSERT INTO source_priority (attribute, source, priority, notes) VALUES
    ('growth_form', 'gift', 1, 'GIFT uses liana/vine distinction from Climber.R'),
    ('growth_form', 'reflora', 2, 'Brazilian flora authority'),
    ('growth_form', 'wcvp', 3, 'Global taxonomy reference'),
    ('growth_form', 'treegoer', 4, 'Tree validation >80% species'),
    ('growth_form', 'practitioners', 5, 'Field data from botanists'),
    ('growth_form', 'ecocrop', 6, 'FAO cultivated species')
ON CONFLICT (attribute, source) DO NOTHING;

-- max_height_m: practitioners > gift > reflora > wcvp
-- Practitioners have field-measured heights, more reliable than database averages
INSERT INTO source_priority (attribute, source, priority, notes) VALUES
    ('max_height_m', 'practitioners', 1, 'Field-measured heights from botanists'),
    ('max_height_m', 'gift', 2, 'GIFT database heights'),
    ('max_height_m', 'reflora', 3, 'Flora do Brasil heights'),
    ('max_height_m', 'wcvp', 4, 'WCVP heights'),
    ('max_height_m', 'treegoer', 5, 'TreeGOER heights')
ON CONFLICT (attribute, source) DO NOTHING;

-- threat_status: cncflora > practitioners > reflora > wcvp > iucn
-- CNCFlora is the Brazilian authority; practitioners have field assessments
INSERT INTO source_priority (attribute, source, priority, notes) VALUES
    ('threat_status', 'cncflora', 1, 'CNC Flora 2021 — Brazilian authority for threat assessment'),
    ('threat_status', 'practitioners', 2, 'Field assessments from botanists'),
    ('threat_status', 'reflora', 3, 'Flora do Brasil threat data'),
    ('threat_status', 'wcvp', 4, 'WCVP threat data'),
    ('threat_status', 'iucn', 5, 'IUCN Red List — global, may differ from national')
ON CONFLICT (attribute, source) DO NOTHING;

-- lifespan_years: try > practitioners
INSERT INTO source_priority (attribute, source, priority, notes) VALUES
    ('lifespan_years', 'try', 1, 'TRY database — largest plant trait database'),
    ('lifespan_years', 'practitioners', 2, 'Practitioner estimates')
ON CONFLICT (attribute, source) DO NOTHING;

-- stratum: practitioners > gift
INSERT INTO source_priority (attribute, source, priority, notes) VALUES
    ('stratum', 'practitioners', 1, 'Field observations of stratum'),
    ('stratum', 'gift', 2, 'GIFT stratum data')
ON CONFLICT (attribute, source) DO NOTHING;

-- plant_use: wcups > ecocrop > practitioners
INSERT INTO source_priority (attribute, source, priority, notes) VALUES
    ('plant_use', 'wcups', 1, 'World Checklist of Useful Plant Species (Kew)'),
    ('plant_use', 'ecocrop', 2, 'FAO EcoCrop cultivated species'),
    ('plant_use', 'practitioners', 3, 'Practitioner use data')
ON CONFLICT (attribute, source) DO NOTHING;

-- common_names priorities per language
INSERT INTO source_priority (attribute, source, priority, notes) VALUES
    ('common_name_pt', 'practitioners', 1, 'Curated Portuguese names from botanists'),
    ('common_name_pt', 'reflora', 2, 'Flora do Brasil names'),
    ('common_name_pt', 'wfo', 3, 'World Flora Online'),
    ('common_name_pt', 'wcvp', 4, 'WCVP names'),
    ('common_name_en', 'practitioners', 1, 'Curated English names from botanists'),
    ('common_name_en', 'wcvp', 2, 'WCVP names'),
    ('common_name_en', 'wfo', 3, 'World Flora Online'),
    ('common_name_en', 'ecocrop', 4, 'EcoCrop names')
ON CONFLICT (attribute, source) DO NOTHING;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_source_priority_attr ON source_priority(attribute, priority);
