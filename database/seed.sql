-- DiversiPlant Database Seed Data
-- Sample data for development and testing

-- =============================================
-- SAMPLE SPECIES (Brazilian Atlantic Forest)
-- =============================================

INSERT INTO species (canonical_name, genus, family, taxonomic_status) VALUES
    ('Araucaria angustifolia', 'Araucaria', 'Araucariaceae', 'accepted'),
    ('Euterpe edulis', 'Euterpe', 'Arecaceae', 'accepted'),
    ('Cedrela fissilis', 'Cedrela', 'Meliaceae', 'accepted'),
    ('Tabebuia cassinoides', 'Tabebuia', 'Bignoniaceae', 'accepted'),
    ('Passiflora edulis', 'Passiflora', 'Passifloraceae', 'accepted'),
    ('Ipomoea batatas', 'Ipomoea', 'Convolvulaceae', 'accepted'),
    ('Manihot esculenta', 'Manihot', 'Euphorbiaceae', 'accepted'),
    ('Musa paradisiaca', 'Musa', 'Musaceae', 'accepted'),
    ('Ananas comosus', 'Ananas', 'Bromeliaceae', 'accepted'),
    ('Theobroma cacao', 'Theobroma', 'Malvaceae', 'accepted'),
    ('Coffea arabica', 'Coffea', 'Rubiaceae', 'accepted'),
    ('Inga edulis', 'Inga', 'Fabaceae', 'accepted'),
    ('Bauhinia forficata', 'Bauhinia', 'Fabaceae', 'accepted'),
    ('Solanum lycopersicum', 'Solanum', 'Solanaceae', 'accepted'),
    ('Phaseolus vulgaris', 'Phaseolus', 'Fabaceae', 'accepted')
ON CONFLICT (canonical_name) DO NOTHING;

-- =============================================
-- SAMPLE TRAITS
-- =============================================

INSERT INTO species_traits (species_id, growth_form, max_height_m, stratum, nitrogen_fixer, source, _gift_trait_1_2_2, _gift_trait_1_4_2) VALUES
    ((SELECT id FROM species WHERE canonical_name = 'Araucaria angustifolia'), 'tree', 35.0, 'emergent', FALSE, 'gift', 'tree', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Euterpe edulis'), 'palm', 15.0, 'canopy', FALSE, 'gift', 'palm', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Cedrela fissilis'), 'tree', 30.0, 'canopy', FALSE, 'gift', 'tree', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Tabebuia cassinoides'), 'tree', 20.0, 'canopy', FALSE, 'gift', 'tree', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Passiflora edulis'), 'vine', 10.0, 'understory', FALSE, 'gift', 'herb', 'vine'),
    ((SELECT id FROM species WHERE canonical_name = 'Ipomoea batatas'), 'vine', 3.0, 'ground', FALSE, 'gift', 'herb', 'vine'),
    ((SELECT id FROM species WHERE canonical_name = 'Manihot esculenta'), 'shrub', 3.0, 'shrub', FALSE, 'gift', 'shrub', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Musa paradisiaca'), 'forb', 6.0, 'understory', FALSE, 'gift', 'herb', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Ananas comosus'), 'forb', 1.5, 'ground', FALSE, 'gift', 'herb', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Theobroma cacao'), 'tree', 8.0, 'understory', FALSE, 'gift', 'tree', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Coffea arabica'), 'shrub', 5.0, 'shrub', FALSE, 'gift', 'shrub', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Inga edulis'), 'tree', 15.0, 'canopy', TRUE, 'gift', 'tree', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Bauhinia forficata'), 'liana', 10.0, 'understory', TRUE, 'gift', 'shrub', 'liana'),
    ((SELECT id FROM species WHERE canonical_name = 'Solanum lycopersicum'), 'forb', 2.0, 'ground', FALSE, 'gift', 'herb', 'self-supporting'),
    ((SELECT id FROM species WHERE canonical_name = 'Phaseolus vulgaris'), 'vine', 3.0, 'ground', TRUE, 'gift', 'herb', 'vine')
ON CONFLICT DO NOTHING;

-- =============================================
-- SAMPLE COMMON NAMES (PT-BR)
-- =============================================

INSERT INTO common_names (species_id, common_name, language, source, verified) VALUES
    ((SELECT id FROM species WHERE canonical_name = 'Araucaria angustifolia'), 'Araucaria', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Araucaria angustifolia'), 'Pinheiro-do-Parana', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Araucaria angustifolia'), 'Parana Pine', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Euterpe edulis'), 'Palmito-jussara', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Euterpe edulis'), 'Jussara Palm', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Cedrela fissilis'), 'Cedro-rosa', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Cedrela fissilis'), 'Argentine Cedar', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Passiflora edulis'), 'Maracuja', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Passiflora edulis'), 'Passion Fruit', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Ipomoea batatas'), 'Batata-doce', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Ipomoea batatas'), 'Sweet Potato', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Manihot esculenta'), 'Mandioca', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Manihot esculenta'), 'Cassava', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Musa paradisiaca'), 'Banana', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Musa paradisiaca'), 'Banana', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Ananas comosus'), 'Abacaxi', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Ananas comosus'), 'Pineapple', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Theobroma cacao'), 'Cacau', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Theobroma cacao'), 'Cocoa', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Coffea arabica'), 'Cafe', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Coffea arabica'), 'Coffee', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Inga edulis'), 'Inga', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Inga edulis'), 'Ice Cream Bean', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Bauhinia forficata'), 'Pata-de-vaca', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Bauhinia forficata'), 'Brazilian Orchid Tree', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Solanum lycopersicum'), 'Tomate', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Solanum lycopersicum'), 'Tomato', 'en', 'gbif', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Phaseolus vulgaris'), 'Feijao', 'pt', 'reflora', TRUE),
    ((SELECT id FROM species WHERE canonical_name = 'Phaseolus vulgaris'), 'Common Bean', 'en', 'gbif', TRUE)
ON CONFLICT (species_id, common_name, language) DO NOTHING;

-- =============================================
-- SAMPLE DISTRIBUTION (Southern Brazil)
-- =============================================

INSERT INTO species_distribution (species_id, tdwg_code, native, endemic, introduced, source) VALUES
    ((SELECT id FROM species WHERE canonical_name = 'Araucaria angustifolia'), 'BZS', TRUE, TRUE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Euterpe edulis'), 'BZS', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Euterpe edulis'), 'BZL', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Cedrela fissilis'), 'BZS', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Cedrela fissilis'), 'BZL', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Passiflora edulis'), 'BZS', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Passiflora edulis'), 'BZL', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Manihot esculenta'), 'BZS', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Theobroma cacao'), 'BZN', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Theobroma cacao'), 'BZE', FALSE, FALSE, TRUE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Inga edulis'), 'BZS', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Inga edulis'), 'BZL', TRUE, FALSE, FALSE, 'reflora'),
    ((SELECT id FROM species WHERE canonical_name = 'Bauhinia forficata'), 'BZS', TRUE, FALSE, FALSE, 'reflora')
ON CONFLICT (species_id, tdwg_code) DO NOTHING;

-- =============================================
-- VERIFY SEED DATA
-- =============================================

DO $$
DECLARE
    v_species_count INTEGER;
    v_traits_count INTEGER;
    v_names_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_species_count FROM species;
    SELECT COUNT(*) INTO v_traits_count FROM species_traits;
    SELECT COUNT(*) INTO v_names_count FROM common_names;

    RAISE NOTICE 'Seed data loaded:';
    RAISE NOTICE '  Species: %', v_species_count;
    RAISE NOTICE '  Traits: %', v_traits_count;
    RAISE NOTICE '  Common Names: %', v_names_count;
END $$;
