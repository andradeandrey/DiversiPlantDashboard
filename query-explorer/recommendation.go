package main

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"time"

	"github.com/lib/pq"
)

// ============================================================================
// REQUEST/RESPONSE STRUCTURES
// ============================================================================

type RecommendRequest struct {
	// Location (one required)
	TDWGCode  string   `json:"tdwg_code,omitempty"`
	StateCode string   `json:"state_code,omitempty"` // BR-SP, BR-MG, etc.
	Latitude  *float64 `json:"latitude,omitempty"`
	Longitude *float64 `json:"longitude,omitempty"`

	// Parameters
	NSpecies         int     `json:"n_species"`         // Default: 20
	ClimateThreshold float64 `json:"climate_threshold"` // Default: 0.6

	// Filters
	Preferences Preferences `json:"preferences,omitempty"`
}

type Preferences struct {
	GrowthForms        []string `json:"growth_forms,omitempty"`    // graminoid, forb, subshrub, shrub, tree, scrambler, vine, liana, palm, bamboo, other
	IncludeIntroduced  bool     `json:"include_introduced,omitempty"` // Include introduced species (default: false)
	IncludeThreatened  *bool    `json:"include_threatened,omitempty"`
	MinHeightM         *float64 `json:"min_height_m,omitempty"`
	MaxHeightM         *float64 `json:"max_height_m,omitempty"`
	NitrogenFixersOnly bool     `json:"nitrogen_fixers_only,omitempty"`
	EndemicsOnly       bool     `json:"endemics_only,omitempty"`
}

type RecommendResponse struct {
	Species          []SpeciesRecommendation `json:"species"`
	DiversityMetrics DiversityMetrics        `json:"diversity_metrics"`
	LocationInfo     LocationInfo            `json:"location_info"`
	QueryTime        string                  `json:"query_time"`
}

type SpeciesRecommendation struct {
	SpeciesID             int64    `json:"species_id"`
	CanonicalName         string   `json:"canonical_name"`
	CommonNamePT          *string  `json:"common_name_pt,omitempty"`
	CommonNameEN          *string  `json:"common_name_en,omitempty"`
	Family                string   `json:"family"`
	GrowthForm            string   `json:"growth_form"`
	MaxHeightM            *float64 `json:"max_height_m,omitempty"`
	LifespanYears         *float64 `json:"lifespan_years,omitempty"`
	IsNitrogenFixer       bool     `json:"is_nitrogen_fixer"`
	ThreatStatus          *string  `json:"threat_status,omitempty"`
	IsNative              bool     `json:"is_native"`
	IsEndemic             bool     `json:"is_endemic"`
	ClimateMatchScore     float64  `json:"climate_match_score"`
	SelectionRank         int      `json:"selection_rank"`
	DiversityContribution float64  `json:"diversity_contribution"`
}

type DiversityMetrics struct {
	FunctionalDiversity   float64 `json:"functional_diversity"`
	PhylogeneticDiversity float64 `json:"phylogenetic_diversity"`
	GrowthFormRichness    float64 `json:"growth_form_richness"`
	TotalDiversityScore   float64 `json:"total_diversity_score"`
	NSpecies              int     `json:"n_species"`
	NFamilies             int     `json:"n_families"`
	NGrowthForms          int     `json:"n_growth_forms"`
}

type LocationInfo struct {
	TDWGCode  string   `json:"tdwg_code"`
	TDWGName  string   `json:"tdwg_name"`
	Latitude  *float64 `json:"latitude,omitempty"`
	Longitude *float64 `json:"longitude,omitempty"`
	Bio1      float64  `json:"bio1"`  // Annual mean temp
	Bio5      float64  `json:"bio5"`  // Max temp warmest month
	Bio6      float64  `json:"bio6"`  // Min temp coldest month
	Bio12     float64  `json:"bio12"` // Annual precipitation
	Bio15     float64  `json:"bio15"` // Precipitation seasonality
}

type TraitVector struct {
	IsTree          bool
	IsShrub         bool
	IsHerb          bool
	IsClimber       bool
	IsPalm          bool
	HeightNorm      float64
	LifespanNorm    float64
	IsNitrogenFixer bool
	DispersalAnimal bool
	DispersalWind   bool
	FamilyCode      int
}

// ============================================================================
// CACHE KEY GENERATION
// ============================================================================

func (r *RecommendRequest) CacheKey() string {
	latVal := 0.0
	lonVal := 0.0
	if r.Latitude != nil {
		latVal = *r.Latitude
	}
	if r.Longitude != nil {
		lonVal = *r.Longitude
	}

	prefsJSON, _ := json.Marshal(r.Preferences)
	data := fmt.Sprintf("%s_%s_%.6f_%.6f_%d_%.2f_%s",
		r.TDWGCode, r.StateCode,
		latVal, lonVal,
		r.NSpecies, r.ClimateThreshold,
		string(prefsJSON),
	)

	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

// ============================================================================
// CACHE OPERATIONS
// ============================================================================

func getCachedRecommendation(db *sql.DB, cacheKey string) (*RecommendResponse, bool) {
	var speciesIDs []int64
	var metricsJSON string

	err := db.QueryRow(`
		SELECT recommended_species, diversity_metrics
		FROM recommendation_cache
		WHERE cache_key = $1 AND expires_at > NOW()
	`, cacheKey).Scan(&speciesIDs, &metricsJSON)

	if err != nil {
		return nil, false
	}

	// Update hit count
	db.Exec("UPDATE recommendation_cache SET hit_count = hit_count + 1 WHERE cache_key = $1", cacheKey)

	// Return cached response (would need to reconstruct full response)
	// For simplicity, returning false to always compute fresh for now
	return nil, false
}

func cacheRecommendation(db *sql.DB, cacheKey string, req RecommendRequest, speciesIDs []int64, metrics DiversityMetrics, ttl time.Duration) error {
	metricsJSON, err := json.Marshal(metrics)
	if err != nil {
		return err
	}

	latVal := sql.NullFloat64{}
	lonVal := sql.NullFloat64{}
	if req.Latitude != nil {
		latVal = sql.NullFloat64{Float64: *req.Latitude, Valid: true}
	}
	if req.Longitude != nil {
		lonVal = sql.NullFloat64{Float64: *req.Longitude, Valid: true}
	}

	prefsJSON, _ := json.Marshal(req.Preferences)

	_, err = db.Exec(`
		INSERT INTO recommendation_cache
		(cache_key, location_tdwg, location_lat, location_lon, preferences, climate_threshold, n_species, recommended_species, diversity_metrics, expires_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW() + $10::interval)
		ON CONFLICT (cache_key) DO UPDATE
		SET hit_count = recommendation_cache.hit_count + 1,
		    expires_at = NOW() + $10::interval
	`, cacheKey, req.TDWGCode, latVal, lonVal, prefsJSON, req.ClimateThreshold, req.NSpecies, speciesIDs, metricsJSON, fmt.Sprintf("%d seconds", int(ttl.Seconds())))

	return err
}

// ============================================================================
// MAIN RECOMMENDATION LOGIC
// ============================================================================

func executeRecommendation(db *sql.DB, req RecommendRequest) (*RecommendResponse, error) {
	// 1. Resolve location to TDWG + climate
	location, err := resolveLocation(db, req)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve location: %w", err)
	}

	// 2. Get climatically adapted candidates
	candidates, err := getClimateAdaptedSpecies(db, location, req)
	if err != nil {
		return nil, fmt.Errorf("failed to get candidates: %w", err)
	}

	if len(candidates) == 0 {
		return nil, fmt.Errorf("no species found matching criteria (try lowering climate_threshold)")
	}

	// 3. Load trait vectors
	traitVectors, err := loadTraitVectors(db, candidates)
	if err != nil {
		return nil, fmt.Errorf("failed to load traits: %w", err)
	}

	// 4. Greedy diversity maximization
	selected := greedyDiversitySelection(candidates, traitVectors, req.NSpecies)

	// 5. Calculate final metrics
	metrics := calculateDiversityMetrics(selected, traitVectors)

	// 6. Cache result
	speciesIDs := make([]int64, len(selected))
	for i, sp := range selected {
		speciesIDs[i] = sp.SpeciesID
	}
	cacheRecommendation(db, req.CacheKey(), req, speciesIDs, metrics, 24*time.Hour)

	return &RecommendResponse{
		Species:          selected,
		DiversityMetrics: metrics,
		LocationInfo:     location,
	}, nil
}

// ============================================================================
// LOCATION RESOLUTION
// ============================================================================

func resolveLocation(db *sql.DB, req RecommendRequest) (LocationInfo, error) {
	var location LocationInfo

	// Case 1: TDWG code provided
	if req.TDWGCode != "" {
		err := db.QueryRow(`
			SELECT c.tdwg_code, COALESCE(t.level3_name, c.tdwg_code),
			       c.bio1_mean, c.bio5_mean, c.bio6_mean, c.bio12_mean, c.bio15_mean
			FROM tdwg_climate c
			LEFT JOIN tdwg_level3 t ON c.tdwg_code = t.level3_code
			WHERE c.tdwg_code = $1
		`, req.TDWGCode).Scan(
			&location.TDWGCode, &location.TDWGName,
			&location.Bio1,
			&location.Bio5,
			&location.Bio6,
			&location.Bio12,
			&location.Bio15,
		)
		if err != nil {
			return location, fmt.Errorf("invalid TDWG code: %s", req.TDWGCode)
		}
		return location, nil
	}

	// Case 2: Brazilian state code provided
	if req.StateCode != "" {
		// Map state to TDWG (simplified - would need proper mapping table)
		stateToTDWG := map[string]string{
			"BR-SC": "BZS", "BR-PR": "BZS", "BR-RS": "BZS", // South
			"BR-SP": "BZL", "BR-RJ": "BZL", "BR-ES": "BZL", // Southeast
			"BR-MG": "BZL",
			"BR-BA": "BZE", "BR-SE": "BZE", "BR-AL": "BZE", // East
			"BR-PE": "BZE", "BR-PB": "BZE", "BR-RN": "BZE",
			"BR-CE": "BZN", "BR-PI": "BZN", "BR-MA": "BZN", // North
			"BR-PA": "BZN", "BR-AM": "BZN", "BR-RR": "BZN",
			"BR-GO": "BZC", "BR-MT": "BZC", "BR-MS": "BZC", "BR-DF": "BZC", // Central
		}

		tdwgCode, ok := stateToTDWG[req.StateCode]
		if !ok {
			return location, fmt.Errorf("invalid state code: %s", req.StateCode)
		}

		req.TDWGCode = tdwgCode
		return resolveLocation(db, req)
	}

	// Case 3: Coordinates provided
	if req.Latitude != nil && req.Longitude != nil {
		lat := *req.Latitude
		lon := *req.Longitude

		// Get TDWG code and name from coordinates
		err := db.QueryRow(`
			SELECT level3_code, level3_name FROM get_tdwg_by_coords($1, $2)
		`, lat, lon).Scan(&location.TDWGCode, &location.TDWGName)

		if err != nil {
			return location, fmt.Errorf("failed to resolve coordinates to TDWG: %w", err)
		}

		// Get climate at point using pivot query
		err = db.QueryRow(`
			SELECT
				MAX(CASE WHEN bio_var = 'bio1' THEN value END) as bio1,
				MAX(CASE WHEN bio_var = 'bio5' THEN value END) as bio5,
				MAX(CASE WHEN bio_var = 'bio6' THEN value END) as bio6,
				MAX(CASE WHEN bio_var = 'bio12' THEN value END) as bio12,
				MAX(CASE WHEN bio_var = 'bio15' THEN value END) as bio15
			FROM get_climate_at_point($1, $2)
		`, lat, lon).Scan(
			&location.Bio1,
			&location.Bio5,
			&location.Bio6,
			&location.Bio12,
			&location.Bio15,
		)

		if err != nil || location.Bio1 == 0 {
			// Fallback to TDWG climate if raster fails
			err = db.QueryRow(`
				SELECT c.bio1_mean, c.bio5_mean, c.bio6_mean, c.bio12_mean, c.bio15_mean
				FROM tdwg_climate c
				WHERE c.tdwg_code = $1
			`, location.TDWGCode).Scan(
				&location.Bio1,
				&location.Bio5,
				&location.Bio6,
				&location.Bio12,
				&location.Bio15,
			)
			if err != nil {
				return location, fmt.Errorf("failed to get climate data: %w", err)
			}
		}

		location.Latitude = req.Latitude
		location.Longitude = req.Longitude

		return location, nil
	}

	return location, fmt.Errorf("must provide either tdwg_code, state_code, or coordinates")
}

// ============================================================================
// CLIMATE-ADAPTED SPECIES QUERY
// ============================================================================

func getClimateAdaptedSpecies(db *sql.DB, loc LocationInfo, req RecommendRequest) ([]SpeciesRecommendation, error) {
	// Build WHERE clause from preferences
	whereClause := buildWhereClause(req.Preferences)

	// Build native/introduced filter
	nativeClause := "AND sr.is_native = TRUE"
	if req.Preferences.IncludeIntroduced {
		// Accept both native AND introduced species
		nativeClause = "AND (sr.is_native = TRUE OR sr.is_introduced = TRUE)"
	}

	query := fmt.Sprintf(`
		SELECT
			s.id,
			s.canonical_name,
			COALESCE(s.family, 'Unknown') as family,
			COALESCE(su.growth_form, 'unknown') as growth_form,
			su.max_height_m,
			su.lifespan_years,
			COALESCE(tv.is_nitrogen_fixer, false) as is_nitrogen_fixer,
			su.threat_status,
			COALESCE(sr.is_native, false) as is_native,
			COALESCE(sr.is_endemic, false) as is_endemic,
			calculate_climate_match(s.id, $1, $2, $3, $4, $5) as climate_match_score,
			cn_pt.common_name as common_name_pt,
			cn_en.common_name as common_name_en
		FROM species s
		JOIN species_unified su ON s.id = su.species_id
		JOIN species_regions sr ON s.id = sr.species_id
		JOIN species_climate_envelope_unified sce ON s.id = sce.species_id
		LEFT JOIN species_trait_vectors tv ON s.id = tv.species_id
		LEFT JOIN common_names cn_pt ON s.id = cn_pt.species_id AND cn_pt.language = 'pt'
		LEFT JOIN common_names cn_en ON s.id = cn_en.species_id AND cn_en.language = 'en'
		WHERE sr.tdwg_code = $6
		  %s
		  AND su.growth_form IS NOT NULL
		  AND calculate_climate_match(s.id, $1, $2, $3, $4, $5) >= $7
		  %s
		ORDER BY climate_match_score DESC
		LIMIT $8
	`, nativeClause, whereClause)

	// Calculate candidate pool size: at least 2x requested species, min 500, max 2000
	candidateLimit := req.NSpecies * 2
	if candidateLimit < 500 {
		candidateLimit = 500
	}
	if candidateLimit > 2000 {
		candidateLimit = 2000
	}

	rows, err := db.Query(query,
		loc.Bio1,
		loc.Bio5,
		loc.Bio6,
		loc.Bio12,
		loc.Bio15,
		loc.TDWGCode,
		req.ClimateThreshold,
		candidateLimit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var candidates []SpeciesRecommendation
	for rows.Next() {
		var sp SpeciesRecommendation
		err := rows.Scan(
			&sp.SpeciesID, &sp.CanonicalName, &sp.Family, &sp.GrowthForm,
			&sp.MaxHeightM, &sp.LifespanYears, &sp.IsNitrogenFixer,
			&sp.ThreatStatus, &sp.IsNative, &sp.IsEndemic,
			&sp.ClimateMatchScore, &sp.CommonNamePT, &sp.CommonNameEN,
		)
		if err != nil {
			return nil, err
		}
		candidates = append(candidates, sp)
	}

	return candidates, nil
}

// validGrowthForms defines the 11 accepted growth form values
var validGrowthForms = map[string]bool{
	"graminoid": true, "forb": true, "subshrub": true, "shrub": true,
	"tree": true, "scrambler": true, "vine": true, "liana": true,
	"palm": true, "bamboo": true, "other": true,
}

// joinWithOr joins SQL clauses with OR operator
func joinWithOr(clauses []string) string {
	result := ""
	for i, clause := range clauses {
		if i > 0 {
			result += " OR "
		}
		result += clause
	}
	return result
}

func buildWhereClause(prefs Preferences) string {
	var clauses []string

	if len(prefs.GrowthForms) > 0 {
		var formClauses []string
		for _, form := range prefs.GrowthForms {
			if validGrowthForms[form] {
				formClauses = append(formClauses, fmt.Sprintf("su.growth_form = '%s'", form))
			}
		}

		// Combine with OR (any of the growth forms)
		if len(formClauses) > 0 {
			clauses = append(clauses, "("+joinWithOr(formClauses)+")")
		}
	}

	if prefs.IncludeThreatened != nil && !*prefs.IncludeThreatened {
		clauses = append(clauses, "(su.threat_status IS NULL OR su.threat_status NOT IN ('CR', 'EN', 'VU'))")
	}

	if prefs.MinHeightM != nil {
		clauses = append(clauses, fmt.Sprintf("su.max_height_m >= %.2f", *prefs.MinHeightM))
	}

	if prefs.MaxHeightM != nil {
		clauses = append(clauses, fmt.Sprintf("su.max_height_m <= %.2f", *prefs.MaxHeightM))
	}

	if prefs.NitrogenFixersOnly {
		clauses = append(clauses, "tv.is_nitrogen_fixer = TRUE")
	}

	if prefs.EndemicsOnly {
		clauses = append(clauses, "sr.is_endemic = TRUE")
	}

	if len(clauses) == 0 {
		return ""
	}

	return " AND " + joinWithAnd(clauses)
}

// joinWithAnd joins SQL clauses with AND operator
func joinWithAnd(clauses []string) string {
	result := ""
	for i, clause := range clauses {
		if i > 0 {
			result += " AND "
		}
		result += clause
	}
	return result
}

// ============================================================================
// TRAIT VECTOR LOADING
// ============================================================================

func loadTraitVectors(db *sql.DB, candidates []SpeciesRecommendation) (map[int64]TraitVector, error) {
	if len(candidates) == 0 {
		return make(map[int64]TraitVector), nil
	}

	// Build list of species IDs
	ids := make([]int64, len(candidates))
	for i, c := range candidates {
		ids[i] = c.SpeciesID
	}

	// Query trait vectors
	query := `
		SELECT species_id,
		       COALESCE(is_tree, false), COALESCE(is_shrub, false),
		       COALESCE(is_herb, false), COALESCE(is_climber, false),
		       COALESCE(is_palm, false), COALESCE(is_nitrogen_fixer, false),
		       COALESCE(height_normalized, 0.25), COALESCE(lifespan_normalized, 0.3),
		       COALESCE(dispersal_animal, false), COALESCE(dispersal_wind, false),
		       COALESCE(family_code, 0)
		FROM species_trait_vectors
		WHERE species_id = ANY($1)
	`

	rows, err := db.Query(query, pq.Array(ids))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	vectors := make(map[int64]TraitVector)
	for rows.Next() {
		var id int64
		var tv TraitVector
		err := rows.Scan(
			&id, &tv.IsTree, &tv.IsShrub, &tv.IsHerb, &tv.IsClimber, &tv.IsPalm,
			&tv.IsNitrogenFixer, &tv.HeightNorm, &tv.LifespanNorm,
			&tv.DispersalAnimal, &tv.DispersalWind, &tv.FamilyCode,
		)
		if err != nil {
			return nil, err
		}
		vectors[id] = tv
	}

	return vectors, nil
}

// ============================================================================
// GREEDY DIVERSITY SELECTION ALGORITHM
// ============================================================================

func greedyDiversitySelection(
	candidates []SpeciesRecommendation,
	traits map[int64]TraitVector,
	nSpecies int,
) []SpeciesRecommendation {
	if len(candidates) == 0 || nSpecies == 0 {
		return []SpeciesRecommendation{}
	}

	selected := []SpeciesRecommendation{}
	remaining := make([]SpeciesRecommendation, len(candidates))
	copy(remaining, candidates)

	// Start with best climate match
	selected = append(selected, remaining[0])
	remaining = remaining[1:]

	// Iteratively add species maximizing marginal diversity
	for len(selected) < nSpecies && len(remaining) > 0 {
		bestIdx := -1
		bestScore := -1.0

		for i, candidate := range remaining {
			// Marginal diversity gain
			diversityGain := calculateMarginalDiversity(selected, candidate, traits)

			// Combined score: diversity (70%) + climate match (30%)
			combinedScore := diversityGain*0.7 + candidate.ClimateMatchScore*0.3

			if combinedScore > bestScore {
				bestScore = combinedScore
				bestIdx = i
			}
		}

		if bestIdx >= 0 {
			selected = append(selected, remaining[bestIdx])
			remaining = append(remaining[:bestIdx], remaining[bestIdx+1:]...)
		} else {
			break
		}
	}

	// Assign ranks and diversity contributions
	for i := range selected {
		selected[i].SelectionRank = i + 1
		if i == 0 {
			selected[i].DiversityContribution = 1.0
		} else {
			selected[i].DiversityContribution = calculateMarginalDiversity(
				selected[:i], selected[i], traits,
			)
		}
	}

	return selected
}

func calculateMarginalDiversity(
	existing []SpeciesRecommendation,
	candidate SpeciesRecommendation,
	traits map[int64]TraitVector,
) float64 {
	if len(existing) == 0 {
		return 1.0
	}

	candidateTrait := traits[candidate.SpeciesID]

	// Find minimum Gower distance to existing species
	minDistance := 1.0
	for _, ex := range existing {
		existingTrait := traits[ex.SpeciesID]
		distance := gowerDistance(candidateTrait, existingTrait)
		if distance < minDistance {
			minDistance = distance
		}
	}

	return minDistance
}

// ============================================================================
// GOWER DISTANCE CALCULATION
// ============================================================================

func gowerDistance(a, b TraitVector) float64 {
	// Count differences in categorical traits
	categoricalDiffs := 0.0
	if a.IsTree != b.IsTree {
		categoricalDiffs += 1.0
	}
	if a.IsShrub != b.IsShrub {
		categoricalDiffs += 1.0
	}
	if a.IsHerb != b.IsHerb {
		categoricalDiffs += 1.0
	}
	if a.IsClimber != b.IsClimber {
		categoricalDiffs += 1.0
	}
	if a.IsPalm != b.IsPalm {
		categoricalDiffs += 1.0
	}
	if a.IsNitrogenFixer != b.IsNitrogenFixer {
		categoricalDiffs += 1.0
	}
	if a.DispersalAnimal != b.DispersalAnimal {
		categoricalDiffs += 1.0
	}
	if a.DispersalWind != b.DispersalWind {
		categoricalDiffs += 1.0
	}

	// Continuous trait differences (already normalized 0-1)
	continuousDiffs := math.Abs(a.HeightNorm-b.HeightNorm) +
		math.Abs(a.LifespanNorm-b.LifespanNorm)

	// Family difference (phylogenetic proxy)
	familyDiff := 0.0
	if a.FamilyCode != b.FamilyCode {
		familyDiff = 1.0
	}

	// Gower distance: average of normalized distances
	totalFeatures := 11.0 // 8 categorical + 2 continuous + 1 family
	distance := (categoricalDiffs + continuousDiffs + familyDiff) / totalFeatures

	return distance
}

// ============================================================================
// DIVERSITY METRICS CALCULATION
// ============================================================================

func calculateDiversityMetrics(
	species []SpeciesRecommendation,
	traits map[int64]TraitVector,
) DiversityMetrics {
	if len(species) == 0 {
		return DiversityMetrics{}
	}

	// Count unique families and growth forms
	families := make(map[string]bool)
	growthForms := make(map[string]bool)

	for _, sp := range species {
		families[sp.Family] = true
		growthForms[sp.GrowthForm] = true
	}

	// Functional diversity: mean pairwise distance
	totalDistance := 0.0
	pairs := 0
	for i := 0; i < len(species); i++ {
		for j := i + 1; j < len(species); j++ {
			totalDistance += gowerDistance(
				traits[species[i].SpeciesID],
				traits[species[j].SpeciesID],
			)
			pairs++
		}
	}
	functionalDiv := 0.0
	if pairs > 0 {
		functionalDiv = totalDistance / float64(pairs)
	}

	// Phylogenetic diversity (family-level proxy)
	phyloDiv := float64(len(families)) / float64(len(species))

	// Growth form richness (max 5 forms: tree, shrub, herb, climber, palm)
	gfRichness := float64(len(growthForms)) / 5.0

	// Total diversity score (weighted)
	totalScore := functionalDiv*0.5 + phyloDiv*0.25 + gfRichness*0.25

	return DiversityMetrics{
		FunctionalDiversity:   math.Round(functionalDiv*1000) / 1000,
		PhylogeneticDiversity: math.Round(phyloDiv*1000) / 1000,
		GrowthFormRichness:    math.Round(gfRichness*1000) / 1000,
		TotalDiversityScore:   math.Round(totalScore*1000) / 1000,
		NSpecies:              len(species),
		NFamilies:             len(families),
		NGrowthForms:          len(growthForms),
	}
}

// ============================================================================
// HTTP HANDLER
// ============================================================================

func handleRecommend(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if r.Method != http.MethodPost {
		http.Error(w, `{"error": "POST required"}`, http.StatusMethodNotAllowed)
		return
	}

	var req RecommendRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error": "Invalid JSON"}`, http.StatusBadRequest)
		return
	}

	// Set defaults
	if req.NSpecies <= 0 || req.NSpecies > 1000 {
		req.NSpecies = 20
	}
	if req.ClimateThreshold < 0.3 || req.ClimateThreshold > 1.0 {
		req.ClimateThreshold = 0.6
	}

	// Check cache
	cacheKey := req.CacheKey()
	if cached, ok := getCachedRecommendation(db, cacheKey); ok {
		json.NewEncoder(w).Encode(cached)
		return
	}

	// Execute recommendation
	start := time.Now()
	recommendations, err := executeRecommendation(db, req)
	if err != nil {
		http.Error(w, fmt.Sprintf(`{"error": "%s"}`, err.Error()), http.StatusInternalServerError)
		return
	}

	recommendations.QueryTime = time.Since(start).String()

	json.NewEncoder(w).Encode(recommendations)
}
