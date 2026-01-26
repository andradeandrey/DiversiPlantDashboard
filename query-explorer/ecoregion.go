package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"
)

// EcoregionRequest represents the request for ecoregion species lookup
type EcoregionRequest struct {
	Latitude         float64  `json:"latitude"`
	Longitude        float64  `json:"longitude"`
	Limit            int      `json:"limit"`
	ClimateThreshold float64  `json:"climate_threshold"`
	GrowthForms      []string `json:"growth_forms"`
}

// EcoregionInfo contains information about the ecoregion at a location
type EcoregionInfo struct {
	EcoID     int     `json:"eco_id"`
	EcoName   string  `json:"eco_name"`
	BiomeName string  `json:"biome_name"`
	BiomeNum  int     `json:"biome_num"`
	Realm     string  `json:"realm"`
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
}

// BiomeClimate contains climate data for the location
type BiomeClimate struct {
	Bio1  *float64 `json:"bio1"`
	Bio5  *float64 `json:"bio5"`
	Bio6  *float64 `json:"bio6"`
	Bio12 *float64 `json:"bio12"`
	Bio15 *float64 `json:"bio15"`
}

// EcoregionSpecies represents a species found in the biome
type EcoregionSpecies struct {
	SpeciesID         int64    `json:"species_id"`
	CanonicalName     string   `json:"canonical_name"`
	Family            string   `json:"family"`
	GrowthForm        *string  `json:"growth_form"`
	MaxHeightM        *float64 `json:"max_height_m"`
	LifespanYears     *float64 `json:"lifespan_years"`
	ThreatStatus      *string  `json:"threat_status"`
	ClimateMatchScore float64  `json:"climate_match_score"`
	NEcoregions       int      `json:"n_ecoregions"`
	NObservations     int      `json:"n_observations"`
}

// EcoregionResponse contains the full response
type EcoregionResponse struct {
	Ecoregion   EcoregionInfo      `json:"ecoregion"`
	Climate     BiomeClimate       `json:"climate"`
	Species     []EcoregionSpecies `json:"species"`
	TotalInBiome int               `json:"total_in_biome"`
	QueryTime   string             `json:"query_time"`
}

// handleEcoregionSpecies handles GET/POST /api/ecoregion/species
func handleEcoregionSpecies(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	var req EcoregionRequest

	if r.Method == http.MethodPost {
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, `{"error": "Invalid JSON"}`, http.StatusBadRequest)
			return
		}
	} else if r.Method == http.MethodGet {
		// Parse query parameters
		lat, _ := strconv.ParseFloat(r.URL.Query().Get("lat"), 64)
		lon, _ := strconv.ParseFloat(r.URL.Query().Get("lon"), 64)
		limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
		threshold, _ := strconv.ParseFloat(r.URL.Query().Get("threshold"), 64)

		req = EcoregionRequest{
			Latitude:         lat,
			Longitude:        lon,
			Limit:            limit,
			ClimateThreshold: threshold,
		}
	} else {
		http.Error(w, `{"error": "Method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	// Validate coordinates
	if req.Latitude < -90 || req.Latitude > 90 || req.Longitude < -180 || req.Longitude > 180 {
		http.Error(w, `{"error": "Invalid coordinates"}`, http.StatusBadRequest)
		return
	}

	// Set defaults
	if req.Limit <= 0 || req.Limit > 500 {
		req.Limit = 100
	}
	if req.ClimateThreshold < 0.1 || req.ClimateThreshold > 1.0 {
		req.ClimateThreshold = 0.5
	}

	start := time.Now()

	// Get ecoregion at coordinates
	ecoregion, err := getEcoregionAtPoint(req.Latitude, req.Longitude)
	if err != nil {
		log.Printf("Error getting ecoregion: %v", err)
		http.Error(w, fmt.Sprintf(`{"error": "Failed to get ecoregion: %s"}`, err.Error()), http.StatusInternalServerError)
		return
	}

	// Get climate at coordinates
	climate, err := getClimateAtCoords(req.Latitude, req.Longitude)
	if err != nil {
		log.Printf("Error getting climate: %v", err)
		// Continue without climate data
		climate = BiomeClimate{}
	}

	// Get species for the biome with climate adaptation
	species, totalInBiome, err := getSpeciesForBiome(ecoregion.BiomeNum, climate, req.ClimateThreshold, req.Limit, req.GrowthForms)
	if err != nil {
		log.Printf("Error getting species: %v", err)
		http.Error(w, fmt.Sprintf(`{"error": "Failed to get species: %s"}`, err.Error()), http.StatusInternalServerError)
		return
	}

	response := EcoregionResponse{
		Ecoregion:    ecoregion,
		Climate:      climate,
		Species:      species,
		TotalInBiome: totalInBiome,
		QueryTime:    time.Since(start).String(),
	}

	json.NewEncoder(w).Encode(response)
}

// getEcoregionAtPoint finds the ecoregion containing the given coordinates
func getEcoregionAtPoint(lat, lon float64) (EcoregionInfo, error) {
	var eco EcoregionInfo
	eco.Latitude = lat
	eco.Longitude = lon

	err := db.QueryRow(`
		SELECT eco_id, eco_name, biome_name, biome_num, realm
		FROM ecoregions
		WHERE ST_Contains(geom, ST_SetSRID(ST_Point($1, $2), 4326))
		LIMIT 1
	`, lon, lat).Scan(&eco.EcoID, &eco.EcoName, &eco.BiomeName, &eco.BiomeNum, &eco.Realm)

	if err == sql.ErrNoRows {
		return eco, fmt.Errorf("no ecoregion found at coordinates (%.4f, %.4f)", lat, lon)
	}
	if err != nil {
		return eco, err
	}

	return eco, nil
}

// getClimateAtCoords gets climate data for coordinates
func getClimateAtCoords(lat, lon float64) (BiomeClimate, error) {
	var climate BiomeClimate

	err := db.QueryRow(`
		SELECT
			MAX(CASE WHEN bio_var = 'bio1' THEN value END) as bio1,
			MAX(CASE WHEN bio_var = 'bio5' THEN value END) as bio5,
			MAX(CASE WHEN bio_var = 'bio6' THEN value END) as bio6,
			MAX(CASE WHEN bio_var = 'bio12' THEN value END) as bio12,
			MAX(CASE WHEN bio_var = 'bio15' THEN value END) as bio15
		FROM get_climate_at_point($1, $2)
	`, lat, lon).Scan(&climate.Bio1, &climate.Bio5, &climate.Bio6, &climate.Bio12, &climate.Bio15)

	if err != nil {
		return climate, err
	}

	return climate, nil
}

// getSpeciesForBiome returns species from ecoregions in the given biome, ordered by climate match
func getSpeciesForBiome(biomeNum int, climate BiomeClimate, threshold float64, limit int, growthForms []string) ([]EcoregionSpecies, int, error) {
	// First, get total count of species in this biome
	var totalInBiome int
	err := db.QueryRow(`
		SELECT COUNT(DISTINCT se.species_id)
		FROM species_ecoregions se
		JOIN ecoregions e ON se.eco_id = e.eco_id
		WHERE e.biome_num = $1
	`, biomeNum).Scan(&totalInBiome)
	if err != nil {
		return nil, 0, err
	}

	// Build growth form filter
	growthFormFilter := ""
	if len(growthForms) > 0 {
		growthFormFilter = " AND ("
		for i, gf := range growthForms {
			if i > 0 {
				growthFormFilter += " OR "
			}
			growthFormFilter += fmt.Sprintf("LOWER(su.growth_form) LIKE '%%%s%%'", gf)
		}
		growthFormFilter += ")"
	}

	// Build query based on whether we have climate data
	var query string
	var rows *sql.Rows

	if climate.Bio1 != nil && climate.Bio5 != nil && climate.Bio6 != nil {
		// We have climate data - use climate matching
		query = fmt.Sprintf(`
			WITH biome_species AS (
				SELECT DISTINCT se.species_id, SUM(se.n_observations) as total_obs, COUNT(DISTINCT se.eco_id) as n_ecoregions
				FROM species_ecoregions se
				JOIN ecoregions e ON se.eco_id = e.eco_id
				WHERE e.biome_num = $1
				GROUP BY se.species_id
			)
			SELECT
				s.id,
				s.canonical_name,
				COALESCE(s.family, 'Unknown'),
				su.growth_form,
				su.max_height_m,
				su.lifespan_years,
				su.threat_status,
				COALESCE(calculate_climate_match(s.id, $2, $3, $4, $5, $6), 0.5) as climate_score,
				bs.n_ecoregions,
				bs.total_obs
			FROM biome_species bs
			JOIN species s ON bs.species_id = s.id
			LEFT JOIN species_unified su ON s.id = su.species_id
			WHERE COALESCE(calculate_climate_match(s.id, $2, $3, $4, $5, $6), 0.5) >= $7
			%s
			ORDER BY climate_score DESC, bs.total_obs DESC
			LIMIT $8
		`, growthFormFilter)
		rows, err = db.Query(query, biomeNum, *climate.Bio1, *climate.Bio5, *climate.Bio6,
			coalesceFloat(climate.Bio12, 1000), coalesceFloat(climate.Bio15, 50),
			threshold, limit)
	} else {
		// No climate data - just return by observation count
		query = fmt.Sprintf(`
			WITH biome_species AS (
				SELECT DISTINCT se.species_id, SUM(se.n_observations) as total_obs, COUNT(DISTINCT se.eco_id) as n_ecoregions
				FROM species_ecoregions se
				JOIN ecoregions e ON se.eco_id = e.eco_id
				WHERE e.biome_num = $1
				GROUP BY se.species_id
			)
			SELECT
				s.id,
				s.canonical_name,
				COALESCE(s.family, 'Unknown'),
				su.growth_form,
				su.max_height_m,
				su.lifespan_years,
				su.threat_status,
				0.5 as climate_score,
				bs.n_ecoregions,
				bs.total_obs
			FROM biome_species bs
			JOIN species s ON bs.species_id = s.id
			LEFT JOIN species_unified su ON s.id = su.species_id
			WHERE 1=1 %s
			ORDER BY bs.total_obs DESC
			LIMIT $2
		`, growthFormFilter)
		rows, err = db.Query(query, biomeNum, limit)
	}

	if err != nil {
		return nil, totalInBiome, err
	}
	defer rows.Close()

	var species []EcoregionSpecies
	for rows.Next() {
		var sp EcoregionSpecies
		err := rows.Scan(
			&sp.SpeciesID,
			&sp.CanonicalName,
			&sp.Family,
			&sp.GrowthForm,
			&sp.MaxHeightM,
			&sp.LifespanYears,
			&sp.ThreatStatus,
			&sp.ClimateMatchScore,
			&sp.NEcoregions,
			&sp.NObservations,
		)
		if err != nil {
			log.Printf("Error scanning species row: %v", err)
			continue
		}
		species = append(species, sp)
	}

	return species, totalInBiome, nil
}

func coalesceFloat(f *float64, defaultVal float64) float64 {
	if f == nil {
		return defaultVal
	}
	return *f
}
