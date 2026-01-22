-- Migration 007: WorldClim Raster Storage
-- Stores WorldClim bioclimatic rasters in PostGIS for precise point queries

-- Enable PostGIS Raster extension
CREATE EXTENSION IF NOT EXISTS postgis_raster;

-- Table to store WorldClim raster tiles
-- Each bio variable is stored as separate raster tiles for efficient querying
CREATE TABLE IF NOT EXISTS worldclim_raster (
    rid SERIAL PRIMARY KEY,
    bio_var VARCHAR(10) NOT NULL,  -- 'bio1', 'bio2', ..., 'bio19'
    rast RASTER NOT NULL,
    resolution VARCHAR(10) NOT NULL DEFAULT '10m',  -- '10m', '5m', '2.5m', '30s'
    filename VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spatial index on raster
CREATE INDEX IF NOT EXISTS idx_worldclim_raster_gist
    ON worldclim_raster USING GIST (ST_ConvexHull(rast));

-- Index for bio variable lookup
CREATE INDEX IF NOT EXISTS idx_worldclim_raster_bio
    ON worldclim_raster(bio_var);

-- Add raster constraints after data is loaded (will be done by crawler)
-- SELECT AddRasterConstraints('worldclim_raster', 'rast');

-- Function to get all bio variables at a point
CREATE OR REPLACE FUNCTION get_climate_at_point(
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION
) RETURNS TABLE (
    bio_var VARCHAR(10),
    value DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        wr.bio_var,
        ST_Value(wr.rast, ST_SetSRID(ST_MakePoint(lon, lat), 4326)) as value
    FROM worldclim_raster wr
    WHERE ST_Intersects(wr.rast, ST_SetSRID(ST_MakePoint(lon, lat), 4326));
END;
$$ LANGUAGE plpgsql;

-- Function to get climate data as JSON at a point
CREATE OR REPLACE FUNCTION get_climate_json_at_point(
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION
) RETURNS JSONB AS $$
DECLARE
    result JSONB := '{}';
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT bio_var, value FROM get_climate_at_point(lat, lon)
    LOOP
        result := result || jsonb_build_object(rec.bio_var, rec.value);
    END LOOP;

    -- Add derived classifications
    IF result ? 'bio1' AND result ? 'bio12' THEN
        -- Calculate aridity index
        result := result || jsonb_build_object(
            'aridity_index',
            (result->>'bio12')::numeric / NULLIF((result->>'bio1')::numeric + 10, 0) * 10
        );

        -- Determine Whittaker biome
        result := result || jsonb_build_object(
            'whittaker_biome',
            CASE
                WHEN (result->>'bio1')::numeric >= 20 AND (result->>'bio12')::numeric >= 2000 THEN 'Tropical Rainforest'
                WHEN (result->>'bio1')::numeric >= 20 AND (result->>'bio12')::numeric >= 1000 THEN 'Tropical Seasonal Forest'
                WHEN (result->>'bio1')::numeric >= 20 AND (result->>'bio12')::numeric >= 500 THEN 'Tropical Savanna'
                WHEN (result->>'bio1')::numeric >= 20 AND (result->>'bio12')::numeric < 500 THEN 'Hot Desert'
                WHEN (result->>'bio1')::numeric >= 10 AND (result->>'bio12')::numeric >= 1500 THEN 'Temperate Rainforest'
                WHEN (result->>'bio1')::numeric >= 10 AND (result->>'bio12')::numeric >= 750 THEN 'Temperate Forest'
                WHEN (result->>'bio1')::numeric >= 10 AND (result->>'bio12')::numeric >= 300 THEN 'Temperate Grassland'
                WHEN (result->>'bio1')::numeric >= 10 AND (result->>'bio12')::numeric < 300 THEN 'Cold Desert'
                WHEN (result->>'bio1')::numeric >= 0 AND (result->>'bio12')::numeric >= 500 THEN 'Boreal Forest'
                WHEN (result->>'bio1')::numeric < 0 THEN 'Tundra'
                ELSE 'Unknown'
            END
        );

        -- Determine Köppen zone (simplified)
        result := result || jsonb_build_object(
            'koppen_zone',
            CASE
                -- Tropical (A)
                WHEN (result->>'bio6')::numeric >= 18 AND (result->>'bio14')::numeric >= 60 THEN 'Af'
                WHEN (result->>'bio6')::numeric >= 18 AND (result->>'bio12')::numeric >= 25 * (100 - (result->>'bio14')::numeric) THEN 'Am'
                WHEN (result->>'bio6')::numeric >= 18 THEN 'Aw'
                -- Arid (B)
                WHEN (result->>'bio12')::numeric < 10 * (result->>'bio1')::numeric THEN
                    CASE
                        WHEN (result->>'bio12')::numeric < 5 * (result->>'bio1')::numeric THEN
                            CASE WHEN (result->>'bio1')::numeric >= 18 THEN 'BWh' ELSE 'BWk' END
                        ELSE
                            CASE WHEN (result->>'bio1')::numeric >= 18 THEN 'BSh' ELSE 'BSk' END
                    END
                -- Temperate (C)
                WHEN (result->>'bio6')::numeric >= -3 AND (result->>'bio6')::numeric < 18 THEN
                    CASE
                        WHEN (result->>'bio10')::numeric >= 22 THEN 'Cfa'
                        ELSE 'Cfb'
                    END
                -- Continental (D)
                WHEN (result->>'bio6')::numeric < -3 AND (result->>'bio10')::numeric >= 10 THEN
                    CASE
                        WHEN (result->>'bio6')::numeric < -38 THEN 'Dfd'
                        ELSE 'Dfb'
                    END
                -- Polar (E)
                WHEN (result->>'bio10')::numeric < 10 THEN
                    CASE WHEN (result->>'bio10')::numeric < 0 THEN 'EF' ELSE 'ET' END
                ELSE 'Unknown'
            END
        );
    END IF;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- View for checking raster coverage
CREATE OR REPLACE VIEW v_worldclim_raster_info AS
SELECT
    bio_var,
    resolution,
    COUNT(*) as tile_count,
    SUM(ST_Width(rast) * ST_Height(rast)) as total_pixels,
    MIN(ST_XMin(ST_Envelope(rast))) as min_lon,
    MAX(ST_XMax(ST_Envelope(rast))) as max_lon,
    MIN(ST_YMin(ST_Envelope(rast))) as min_lat,
    MAX(ST_YMax(ST_Envelope(rast))) as max_lat
FROM worldclim_raster
GROUP BY bio_var, resolution;

COMMENT ON TABLE worldclim_raster IS 'WorldClim 2.1 bioclimatic rasters stored as PostGIS tiles';
COMMENT ON FUNCTION get_climate_at_point IS 'Get all bioclimatic values at a specific lat/lon point';
COMMENT ON FUNCTION get_climate_json_at_point IS 'Get climate data as JSON with derived classifications at a point';
