package main

import (
	"context"
	"crypto/tls"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	_ "github.com/lib/pq"
	"golang.org/x/crypto/acme/autocert"
)

var db *sql.DB

type Config struct {
	DBHost     string
	DBPort     string
	DBUser     string
	DBPassword string
	DBName     string
	Domain     string
	CertDir    string
	DevMode    bool
}

func getConfig() Config {
	return Config{
		DBHost:     getEnv("DB_HOST", "localhost"),
		DBPort:     getEnv("DB_PORT", "5432"),
		DBUser:     getEnv("DB_USER", "diversiplant"),
		DBPassword: getEnv("DB_PASSWORD", "diversiplant"),
		DBName:     getEnv("DB_NAME", "diversiplant"),
		Domain:     getEnv("DOMAIN", "diversiplant.andreyandrade.com"),
		CertDir:    getEnv("CERT_DIR", "/opt/diversiplant-admin/certs"),
		DevMode:    getEnv("DEV_MODE", "false") == "true",
	}
}

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func initDB(cfg Config) error {
	connStr := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		cfg.DBHost, cfg.DBPort, cfg.DBUser, cfg.DBPassword, cfg.DBName)

	var err error
	db, err = sql.Open("postgres", connStr)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}

	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return fmt.Errorf("failed to ping database: %w", err)
	}

	log.Println("Database connected successfully")
	return nil
}

func main() {
	cfg := getConfig()

	if err := initDB(cfg); err != nil {
		log.Fatalf("Database initialization failed: %v", err)
	}
	defer db.Close()

	mux := http.NewServeMux()

	// Dashboard proxy (must be registered before catch-all)
	dashboardProxy := newDashboardProxy()
	mux.Handle("/diversiplant/", dashboardProxy)

	// API routes
	mux.HandleFunc("/api/health", handleHealth)
	mux.HandleFunc("/api/stats", handleStats)
	mux.HandleFunc("/api/tdwg", handleTDWG)
	mux.HandleFunc("/api/species", handleSpecies)
	mux.HandleFunc("/api/query", handleQuery)
	mux.HandleFunc("/api/sources", handleSources)
	mux.HandleFunc("/api/climate", handleClimate)
	mux.HandleFunc("/api/climate/stats", handleClimateStats)
	mux.HandleFunc("/api/climate/species", handleClimateSpecies)
	mux.HandleFunc("/api/climate/point", handleClimatePoint)
	mux.HandleFunc("/api/recommend", handleRecommend)
	mux.HandleFunc("/api/ecoregion/species", handleEcoregionSpecies)

	// Static files
	mux.Handle("/", http.FileServer(http.Dir("static")))

	// CORS middleware
	handler := corsMiddleware(mux)

	if cfg.DevMode {
		// Development mode - HTTP only
		log.Printf("Starting development server on :8080")
		log.Fatal(http.ListenAndServe(":8080", handler))
	} else {
		// Production mode - HTTPS with ACME
		certManager := autocert.Manager{
			Prompt:     autocert.AcceptTOS,
			HostPolicy: autocert.HostWhitelist(cfg.Domain),
			Cache:      autocert.DirCache(cfg.CertDir),
		}

		server := &http.Server{
			Addr:    ":443",
			Handler: handler,
			TLSConfig: &tls.Config{
				GetCertificate: certManager.GetCertificate,
				MinVersion:     tls.VersionTLS12,
			},
		}

		// Internal HTTP on :8080 for inter-container communication
		go func() {
			log.Println("Starting internal API server on :8080")
			if err := http.ListenAndServe(":8080", handler); err != nil {
				log.Printf("Internal API server error: %v", err)
			}
		}()

		// HTTP redirect to HTTPS (+ ACME challenge)
		go func() {
			redirectServer := &http.Server{
				Addr:    ":80",
				Handler: certManager.HTTPHandler(http.HandlerFunc(redirectHTTPS)),
			}
			log.Println("Starting HTTP redirect server on :80")
			if err := redirectServer.ListenAndServe(); err != nil {
				log.Printf("HTTP redirect server error: %v", err)
			}
		}()

		log.Printf("Starting HTTPS server for %s on :443", cfg.Domain)
		log.Fatal(server.ListenAndServeTLS("", ""))
	}
}

func newDashboardProxy() http.Handler {
	dashboardURL := getEnv("DASHBOARD_URL", "http://127.0.0.1:8001")
	target, _ := url.Parse(dashboardURL)
	proxy := httputil.NewSingleHostReverseProxy(target)

	// Custom error handler for when the Python server is offline
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Printf("Dashboard proxy error: %v", err)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusBadGateway)
		fmt.Fprintf(w, `<html><body style="font-family:sans-serif;text-align:center;padding:60px">
			<h1>Dashboard Offline</h1>
			<p>The DiversiPlant Shiny dashboard is not running.</p>
			<p>Start it with: <code>uvicorn app:app --host 127.0.0.1 --port 8001</code></p>
			<p><a href="/">Go to Admin UI</a></p>
		</body></html>`)
	}

	return proxy
}

func redirectHTTPS(w http.ResponseWriter, r *http.Request) {
	target := "https://" + r.Host + r.URL.Path
	if r.URL.RawQuery != "" {
		target += "?" + r.URL.RawQuery
	}
	http.Redirect(w, r, target, http.StatusMovedPermanently)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// API Handlers

type HealthResponse struct {
	Status    string           `json:"status"`
	Database  string           `json:"database"`
	PostGIS   string           `json:"postgis"`
	Timestamp string           `json:"timestamp"`
	Tables    map[string]int64 `json:"tables"`
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	resp := HealthResponse{
		Status:    "ok",
		Timestamp: time.Now().Format(time.RFC3339),
		Tables:    make(map[string]int64),
	}

	// Check database
	if err := db.Ping(); err != nil {
		resp.Status = "error"
		resp.Database = err.Error()
	} else {
		resp.Database = "connected"
	}

	// Check PostGIS
	var postgisVersion string
	err := db.QueryRow("SELECT PostGIS_version()").Scan(&postgisVersion)
	if err != nil {
		resp.PostGIS = "not available"
	} else {
		resp.PostGIS = postgisVersion
	}

	// Check tables
	tables := []string{"species", "species_unified", "species_regions", "species_geometry", "tdwg_level3", "tdwg_climate"}
	for _, table := range tables {
		var count int64
		err := db.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM %s", table)).Scan(&count)
		if err != nil {
			resp.Tables[table] = -1
		} else {
			resp.Tables[table] = count
		}
	}

	json.NewEncoder(w).Encode(resp)
}

type StatsResponse struct {
	TotalSpecies     int64             `json:"total_species"`
	SpeciesUnified   int64             `json:"species_unified"`
	SpeciesRegions   int64             `json:"species_regions"`
	SpeciesGeometry  int64             `json:"species_geometry"`
	TDWGRegions      int64             `json:"tdwg_regions"`
	SourceBreakdown  []SourceCount     `json:"source_breakdown"`
	GrowthFormCounts []GrowthFormCount `json:"growth_form_counts"`
}

type SourceCount struct {
	Source string `json:"source"`
	Count  int64  `json:"count"`
}

type GrowthFormCount struct {
	GrowthForm string `json:"growth_form"`
	Count      int64  `json:"count"`
}

func handleStats(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	resp := StatsResponse{}

	// Get counts
	db.QueryRow("SELECT COUNT(*) FROM species").Scan(&resp.TotalSpecies)
	db.QueryRow("SELECT COUNT(*) FROM species_unified").Scan(&resp.SpeciesUnified)
	db.QueryRow("SELECT COUNT(*) FROM species_regions").Scan(&resp.SpeciesRegions)
	db.QueryRow("SELECT COUNT(*) FROM species_geometry").Scan(&resp.SpeciesGeometry)
	db.QueryRow("SELECT COUNT(*) FROM tdwg_level3").Scan(&resp.TDWGRegions)

	// Source breakdown
	rows, err := db.Query(`
		SELECT growth_form_source, COUNT(*)
		FROM species_unified
		WHERE growth_form_source IS NOT NULL
		GROUP BY growth_form_source
		ORDER BY COUNT(*) DESC
	`)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var sc SourceCount
			rows.Scan(&sc.Source, &sc.Count)
			resp.SourceBreakdown = append(resp.SourceBreakdown, sc)
		}
	}

	// Growth form counts
	rows, err = db.Query(`
		SELECT growth_form, COUNT(*)
		FROM species_unified
		WHERE growth_form IS NOT NULL
		GROUP BY growth_form
		ORDER BY COUNT(*) DESC
		LIMIT 10
	`)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var gf GrowthFormCount
			rows.Scan(&gf.GrowthForm, &gf.Count)
			resp.GrowthFormCounts = append(resp.GrowthFormCounts, gf)
		}
	}

	json.NewEncoder(w).Encode(resp)
}

type TDWGResponse struct {
	Code      string  `json:"code"`
	Name      string  `json:"name"`
	Continent string  `json:"continent"`
	Distance  float64 `json:"distance_km,omitempty"`
}

func handleTDWG(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	lat, _ := strconv.ParseFloat(r.URL.Query().Get("lat"), 64)
	lon, _ := strconv.ParseFloat(r.URL.Query().Get("lon"), 64)

	if lat == 0 || lon == 0 {
		http.Error(w, `{"error": "lat and lon required"}`, http.StatusBadRequest)
		return
	}

	var resp TDWGResponse

	// Try exact match first
	err := db.QueryRow(`
		SELECT level3_code, level3_name, COALESCE(continent, '')
		FROM tdwg_level3
		WHERE ST_Contains(geom, ST_SetSRID(ST_Point($1, $2), 4326))
		LIMIT 1
	`, lon, lat).Scan(&resp.Code, &resp.Name, &resp.Continent)

	if err == sql.ErrNoRows {
		// Try nearby
		err = db.QueryRow(`
			SELECT level3_code, level3_name, COALESCE(continent, ''),
				   ROUND((ST_Distance(geom, ST_SetSRID(ST_Point($1, $2), 4326)) * 111)::numeric, 2)
			FROM tdwg_level3
			WHERE ST_DWithin(geom, ST_SetSRID(ST_Point($1, $2), 4326), 0.5)
			ORDER BY geom <-> ST_SetSRID(ST_Point($1, $2), 4326)
			LIMIT 1
		`, lon, lat).Scan(&resp.Code, &resp.Name, &resp.Continent, &resp.Distance)
	}

	if err != nil {
		http.Error(w, `{"error": "Region not found"}`, http.StatusNotFound)
		return
	}

	json.NewEncoder(w).Encode(resp)
}

type SpeciesRequest struct {
	TDWGCode   string `json:"tdwg_code"`
	GrowthForm string `json:"growth_form"`
	Limit      int    `json:"limit"`
	Offset     int    `json:"offset"`
	NativeOnly bool   `json:"native_only"`
}

type SpeciesResponse struct {
	Species   []SpeciesItem `json:"species"`
	Total     int64         `json:"total"`
	Limit     int           `json:"limit"`
	Offset    int           `json:"offset"`
	QueryTime string        `json:"query_time"`
}

type SpeciesItem struct {
	ID            int64   `json:"id"`
	CanonicalName string  `json:"canonical_name"`
	Family        string  `json:"family"`
	GrowthForm    string  `json:"growth_form"`
	Source        string  `json:"source"`
	CommonName    *string `json:"common_name,omitempty"`
	IsNative      bool    `json:"is_native"`
}

func handleSpecies(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	tdwgCode := r.URL.Query().Get("tdwg_code")
	growthForm := r.URL.Query().Get("growth_form")
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
	nativeOnly := r.URL.Query().Get("native_only") == "true"

	if limit <= 0 || limit > 500 {
		limit = 50
	}
	if offset < 0 {
		offset = 0
	}

	start := time.Now()

	// Build query
	query := `
		SELECT s.id, s.canonical_name, COALESCE(s.family, ''),
			   COALESCE(su.growth_form, ''), COALESCE(su.growth_form_source, ''),
			   cn.common_name, sr.is_native
		FROM species s
		JOIN species_unified su ON s.id = su.species_id
		JOIN species_regions sr ON s.id = sr.species_id
		LEFT JOIN common_names cn ON s.id = cn.species_id AND cn.language = 'pt'
		WHERE sr.tdwg_code = $1
	`
	args := []interface{}{tdwgCode}
	argNum := 2

	if growthForm != "" {
		query += fmt.Sprintf(" AND su.growth_form = $%d", argNum)
		args = append(args, growthForm)
		argNum++
	}

	if nativeOnly {
		query += " AND sr.is_native = TRUE"
	}

	// Count query - build separately for reliability
	countQuery := `
		SELECT COUNT(DISTINCT s.id)
		FROM species s
		JOIN species_unified su ON s.id = su.species_id
		JOIN species_regions sr ON s.id = sr.species_id
		WHERE sr.tdwg_code = $1
	`
	countArgs := []interface{}{tdwgCode}
	countArgNum := 2

	if growthForm != "" {
		countQuery += fmt.Sprintf(" AND su.growth_form = $%d", countArgNum)
		countArgs = append(countArgs, growthForm)
	}

	if nativeOnly {
		countQuery += " AND sr.is_native = TRUE"
	}

	var total int64
	if err := db.QueryRow(countQuery, countArgs...).Scan(&total); err != nil {
		log.Printf("Count query error: %v", err)
	}

	// Add pagination
	query += fmt.Sprintf(" ORDER BY s.canonical_name LIMIT $%d OFFSET $%d", argNum, argNum+1)
	args = append(args, limit, offset)

	rows, err := db.Query(query, args...)
	if err != nil {
		http.Error(w, fmt.Sprintf(`{"error": "%s"}`, err.Error()), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	var species []SpeciesItem
	seen := make(map[int64]bool)

	for rows.Next() {
		var sp SpeciesItem
		rows.Scan(&sp.ID, &sp.CanonicalName, &sp.Family, &sp.GrowthForm, &sp.Source, &sp.CommonName, &sp.IsNative)
		if !seen[sp.ID] {
			species = append(species, sp)
			seen[sp.ID] = true
		}
	}

	resp := SpeciesResponse{
		Species:   species,
		Total:     total,
		Limit:     limit,
		Offset:    offset,
		QueryTime: time.Since(start).String(),
	}

	json.NewEncoder(w).Encode(resp)
}

type QueryRequest struct {
	SQL   string `json:"sql"`
	Limit int    `json:"limit"`
}

type QueryResponse struct {
	Columns   []string        `json:"columns"`
	Rows      [][]interface{} `json:"rows"`
	RowCount  int             `json:"row_count"`
	QueryTime string          `json:"query_time"`
	Error     string          `json:"error,omitempty"`
}

func handleQuery(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if r.Method != http.MethodPost {
		http.Error(w, `{"error": "POST required"}`, http.StatusMethodNotAllowed)
		return
	}

	var req QueryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error": "Invalid JSON"}`, http.StatusBadRequest)
		return
	}

	// Security: Only allow SELECT
	sql := strings.TrimSpace(strings.ToUpper(req.SQL))
	if !strings.HasPrefix(sql, "SELECT") && !strings.HasPrefix(sql, "EXPLAIN") {
		http.Error(w, `{"error": "Only SELECT queries allowed"}`, http.StatusForbidden)
		return
	}

	// Disallow dangerous keywords
	forbidden := []string{"DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"}
	for _, kw := range forbidden {
		if strings.Contains(sql, kw) {
			http.Error(w, fmt.Sprintf(`{"error": "%s not allowed"}`, kw), http.StatusForbidden)
			return
		}
	}

	limit := req.Limit
	if limit <= 0 || limit > 1000 {
		limit = 100
	}

	// Remove trailing semicolon and whitespace
	req.SQL = strings.TrimSpace(req.SQL)
	req.SQL = strings.TrimSuffix(req.SQL, ";")

	// Add LIMIT if not present
	if !strings.Contains(sql, "LIMIT") {
		req.SQL = fmt.Sprintf("%s LIMIT %d", req.SQL, limit)
	}

	start := time.Now()

	rows, err := db.Query(req.SQL)
	if err != nil {
		json.NewEncoder(w).Encode(QueryResponse{Error: err.Error()})
		return
	}
	defer rows.Close()

	columns, _ := rows.Columns()
	resp := QueryResponse{
		Columns: columns,
		Rows:    [][]interface{}{},
	}

	for rows.Next() {
		values := make([]interface{}, len(columns))
		valuePtrs := make([]interface{}, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}

		rows.Scan(valuePtrs...)

		row := make([]interface{}, len(columns))
		for i, v := range values {
			switch val := v.(type) {
			case []byte:
				row[i] = string(val)
			case nil:
				row[i] = nil
			default:
				row[i] = val
			}
		}
		resp.Rows = append(resp.Rows, row)
	}

	resp.RowCount = len(resp.Rows)
	resp.QueryTime = time.Since(start).String()

	json.NewEncoder(w).Encode(resp)
}

func handleSources(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	type GrowthFormStats struct {
		Source   string `json:"source"`
		Total    int64  `json:"total"`
		Trees    int64  `json:"trees"`
		Shrubs   int64  `json:"shrubs"`
		Herbs    int64  `json:"herbs"`
		Climbers int64  `json:"climbers"`
		Palms    int64  `json:"palms"`
	}

	type ThreatStats struct {
		Source string `json:"source"`
		Total  int64  `json:"total"`
		CR     int64  `json:"cr"`
		EN     int64  `json:"en"`
		VU     int64  `json:"vu"`
		NT     int64  `json:"nt"`
		LC     int64  `json:"lc"`
	}

	type LifespanStats struct {
		Source      string   `json:"source"`
		Total       int64    `json:"total"`
		AvgLifespan *float64 `json:"avg_lifespan"`
		MinLifespan *float64 `json:"min_lifespan"`
		MaxLifespan *float64 `json:"max_lifespan"`
	}

	type AllSourcesResponse struct {
		GrowthForm []GrowthFormStats `json:"growth_form"`
		Threat     []ThreatStats     `json:"threat_status"`
		Lifespan   []LifespanStats   `json:"lifespan"`
	}

	resp := AllSourcesResponse{}

	// Growth form sources
	rows, err := db.Query(`
		SELECT
			growth_form_source as source,
			COUNT(*) as total,
			COUNT(*) FILTER (WHERE is_tree) as trees,
			COUNT(*) FILTER (WHERE is_shrub) as shrubs,
			COUNT(*) FILTER (WHERE is_herb) as herbs,
			COUNT(*) FILTER (WHERE is_climber) as climbers,
			COUNT(*) FILTER (WHERE is_palm) as palms
		FROM species_unified
		WHERE growth_form_source IS NOT NULL
		GROUP BY growth_form_source
		ORDER BY COUNT(*) DESC
	`)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var s GrowthFormStats
			rows.Scan(&s.Source, &s.Total, &s.Trees, &s.Shrubs, &s.Herbs, &s.Climbers, &s.Palms)
			resp.GrowthForm = append(resp.GrowthForm, s)
		}
	}

	// Threat status sources
	rows2, err := db.Query(`
		SELECT
			threat_status_source as source,
			COUNT(*) as total,
			COUNT(*) FILTER (WHERE threat_status = 'CR') as cr,
			COUNT(*) FILTER (WHERE threat_status = 'EN') as en,
			COUNT(*) FILTER (WHERE threat_status = 'VU') as vu,
			COUNT(*) FILTER (WHERE threat_status = 'NT') as nt,
			COUNT(*) FILTER (WHERE threat_status = 'LC') as lc
		FROM species_unified
		WHERE threat_status_source IS NOT NULL
		GROUP BY threat_status_source
		ORDER BY COUNT(*) DESC
	`)
	if err == nil {
		defer rows2.Close()
		for rows2.Next() {
			var s ThreatStats
			rows2.Scan(&s.Source, &s.Total, &s.CR, &s.EN, &s.VU, &s.NT, &s.LC)
			resp.Threat = append(resp.Threat, s)
		}
	}

	// Lifespan sources
	rows3, err := db.Query(`
		SELECT
			lifespan_source as source,
			COUNT(*) as total,
			ROUND(AVG(lifespan_years)::numeric, 1) as avg_lifespan,
			ROUND(MIN(lifespan_years)::numeric, 1) as min_lifespan,
			ROUND(MAX(lifespan_years)::numeric, 1) as max_lifespan
		FROM species_unified
		WHERE lifespan_source IS NOT NULL
		GROUP BY lifespan_source
		ORDER BY COUNT(*) DESC
	`)
	if err == nil {
		defer rows3.Close()
		for rows3.Next() {
			var s LifespanStats
			rows3.Scan(&s.Source, &s.Total, &s.AvgLifespan, &s.MinLifespan, &s.MaxLifespan)
			resp.Lifespan = append(resp.Lifespan, s)
		}
	}

	json.NewEncoder(w).Encode(resp)
}

// Climate API Handlers

type ClimateData struct {
	TDWGCode       string   `json:"tdwg_code"`
	TDWGName       string   `json:"tdwg_name,omitempty"`
	Bio1Mean       *float64 `json:"bio1_mean"`
	Bio1Min        *float64 `json:"bio1_min"`
	Bio1Max        *float64 `json:"bio1_max"`
	Bio2Mean       *float64 `json:"bio2_mean"`
	Bio3Mean       *float64 `json:"bio3_mean"`
	Bio4Mean       *float64 `json:"bio4_mean"`
	Bio5Mean       *float64 `json:"bio5_mean"`
	Bio6Mean       *float64 `json:"bio6_mean"`
	Bio7Mean       *float64 `json:"bio7_mean"`
	Bio8Mean       *float64 `json:"bio8_mean"`
	Bio9Mean       *float64 `json:"bio9_mean"`
	Bio10Mean      *float64 `json:"bio10_mean"`
	Bio11Mean      *float64 `json:"bio11_mean"`
	Bio12Mean      *float64 `json:"bio12_mean"`
	Bio12Min       *float64 `json:"bio12_min"`
	Bio12Max       *float64 `json:"bio12_max"`
	Bio13Mean      *float64 `json:"bio13_mean"`
	Bio14Mean      *float64 `json:"bio14_mean"`
	Bio15Mean      *float64 `json:"bio15_mean"`
	Bio16Mean      *float64 `json:"bio16_mean"`
	Bio17Mean      *float64 `json:"bio17_mean"`
	Bio18Mean      *float64 `json:"bio18_mean"`
	Bio19Mean      *float64 `json:"bio19_mean"`
	KoppenZone     *string  `json:"koppen_zone"`
	WhittakerBiome *string  `json:"whittaker_biome"`
	AridityIndex   *float64 `json:"aridity_index"`
}

func handleClimate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	tdwgCode := r.URL.Query().Get("tdwg_code")
	lat, _ := strconv.ParseFloat(r.URL.Query().Get("lat"), 64)
	lon, _ := strconv.ParseFloat(r.URL.Query().Get("lon"), 64)

	var data ClimateData

	if tdwgCode != "" {
		err := db.QueryRow(`
			SELECT c.tdwg_code, t.level3_name,
				   c.bio1_mean, c.bio1_min, c.bio1_max,
				   c.bio2_mean, c.bio3_mean, c.bio4_mean,
				   c.bio5_mean, c.bio6_mean, c.bio7_mean,
				   c.bio8_mean, c.bio9_mean, c.bio10_mean, c.bio11_mean,
				   c.bio12_mean, c.bio12_min, c.bio12_max,
				   c.bio13_mean, c.bio14_mean, c.bio15_mean,
				   c.bio16_mean, c.bio17_mean, c.bio18_mean, c.bio19_mean,
				   c.koppen_zone, c.whittaker_biome, c.aridity_index
			FROM tdwg_climate c
			JOIN tdwg_level3 t ON c.tdwg_code = t.level3_code
			WHERE c.tdwg_code = $1
		`, tdwgCode).Scan(
			&data.TDWGCode, &data.TDWGName,
			&data.Bio1Mean, &data.Bio1Min, &data.Bio1Max,
			&data.Bio2Mean, &data.Bio3Mean, &data.Bio4Mean,
			&data.Bio5Mean, &data.Bio6Mean, &data.Bio7Mean,
			&data.Bio8Mean, &data.Bio9Mean, &data.Bio10Mean, &data.Bio11Mean,
			&data.Bio12Mean, &data.Bio12Min, &data.Bio12Max,
			&data.Bio13Mean, &data.Bio14Mean, &data.Bio15Mean,
			&data.Bio16Mean, &data.Bio17Mean, &data.Bio18Mean, &data.Bio19Mean,
			&data.KoppenZone, &data.WhittakerBiome, &data.AridityIndex,
		)
		if err != nil {
			http.Error(w, `{"error": "Climate data not found"}`, http.StatusNotFound)
			return
		}
	} else if lat != 0 || lon != 0 {
		err := db.QueryRow(`
			SELECT c.tdwg_code, t.level3_name,
				   c.bio1_mean, c.bio1_min, c.bio1_max,
				   c.bio2_mean, c.bio3_mean, c.bio4_mean,
				   c.bio5_mean, c.bio6_mean, c.bio7_mean,
				   c.bio8_mean, c.bio9_mean, c.bio10_mean, c.bio11_mean,
				   c.bio12_mean, c.bio12_min, c.bio12_max,
				   c.bio13_mean, c.bio14_mean, c.bio15_mean,
				   c.bio16_mean, c.bio17_mean, c.bio18_mean, c.bio19_mean,
				   c.koppen_zone, c.whittaker_biome, c.aridity_index
			FROM tdwg_level3 t
			JOIN tdwg_climate c ON t.level3_code = c.tdwg_code
			WHERE ST_Contains(t.geom, ST_SetSRID(ST_Point($1, $2), 4326))
			LIMIT 1
		`, lon, lat).Scan(
			&data.TDWGCode, &data.TDWGName,
			&data.Bio1Mean, &data.Bio1Min, &data.Bio1Max,
			&data.Bio2Mean, &data.Bio3Mean, &data.Bio4Mean,
			&data.Bio5Mean, &data.Bio6Mean, &data.Bio7Mean,
			&data.Bio8Mean, &data.Bio9Mean, &data.Bio10Mean, &data.Bio11Mean,
			&data.Bio12Mean, &data.Bio12Min, &data.Bio12Max,
			&data.Bio13Mean, &data.Bio14Mean, &data.Bio15Mean,
			&data.Bio16Mean, &data.Bio17Mean, &data.Bio18Mean, &data.Bio19Mean,
			&data.KoppenZone, &data.WhittakerBiome, &data.AridityIndex,
		)
		if err != nil {
			http.Error(w, `{"error": "No climate data for this location"}`, http.StatusNotFound)
			return
		}
	} else {
		http.Error(w, `{"error": "Provide tdwg_code or lat/lon"}`, http.StatusBadRequest)
		return
	}

	json.NewEncoder(w).Encode(data)
}

type ClimateStatsResponse struct {
	TotalRegions      int64        `json:"total_regions"`
	WithTemperature   int64        `json:"with_temperature"`
	WithPrecipitation int64        `json:"with_precipitation"`
	AvgTemperature    *float64     `json:"avg_temperature"`
	MinTemperature    *float64     `json:"min_temperature"`
	MaxTemperature    *float64     `json:"max_temperature"`
	AvgPrecipitation  *float64     `json:"avg_precipitation"`
	BiomeBreakdown    []BiomeCount `json:"biome_breakdown"`
	KoppenBreakdown   []KoppenCount `json:"koppen_breakdown"`
}

type BiomeCount struct {
	Biome     string   `json:"biome"`
	Count     int64    `json:"count"`
	AvgTemp   *float64 `json:"avg_temp"`
	AvgPrecip *float64 `json:"avg_precip"`
}

type KoppenCount struct {
	Zone  string `json:"zone"`
	Count int64  `json:"count"`
}

func handleClimateStats(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	resp := ClimateStatsResponse{}

	db.QueryRow(`
		SELECT COUNT(*), COUNT(bio1_mean), COUNT(bio12_mean),
			   ROUND(AVG(bio1_mean)::numeric, 1),
			   ROUND(MIN(bio1_mean)::numeric, 1),
			   ROUND(MAX(bio1_mean)::numeric, 1),
			   ROUND(AVG(bio12_mean)::numeric, 0)
		FROM tdwg_climate
	`).Scan(
		&resp.TotalRegions, &resp.WithTemperature, &resp.WithPrecipitation,
		&resp.AvgTemperature, &resp.MinTemperature, &resp.MaxTemperature,
		&resp.AvgPrecipitation,
	)

	rows, err := db.Query(`
		SELECT whittaker_biome, COUNT(*),
			   ROUND(AVG(bio1_mean)::numeric, 1),
			   ROUND(AVG(bio12_mean)::numeric, 0)
		FROM tdwg_climate
		WHERE whittaker_biome IS NOT NULL
		GROUP BY whittaker_biome
		ORDER BY COUNT(*) DESC
	`)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var bc BiomeCount
			rows.Scan(&bc.Biome, &bc.Count, &bc.AvgTemp, &bc.AvgPrecip)
			resp.BiomeBreakdown = append(resp.BiomeBreakdown, bc)
		}
	}

	rows2, err := db.Query(`
		SELECT koppen_zone, COUNT(*)
		FROM tdwg_climate
		WHERE koppen_zone IS NOT NULL
		GROUP BY koppen_zone
		ORDER BY COUNT(*) DESC
	`)
	if err == nil {
		defer rows2.Close()
		for rows2.Next() {
			var kc KoppenCount
			rows2.Scan(&kc.Zone, &kc.Count)
			resp.KoppenBreakdown = append(resp.KoppenBreakdown, kc)
		}
	}

	json.NewEncoder(w).Encode(resp)
}

type SpeciesClimateResponse struct {
	SpeciesID         int64    `json:"species_id"`
	CanonicalName     string   `json:"canonical_name"`
	Family            string   `json:"family"`
	NRegions          int64    `json:"n_regions"`
	TempMeanAvg       *float64 `json:"temp_mean_avg"`
	TempAbsoluteMin   *float64 `json:"temp_absolute_min"`
	TempAbsoluteMax   *float64 `json:"temp_absolute_max"`
	PrecipMeanAvg     *float64 `json:"precip_mean_avg"`
	PrecipAbsoluteMin *float64 `json:"precip_absolute_min"`
	PrecipAbsoluteMax *float64 `json:"precip_absolute_max"`
	AridityAvg        *float64 `json:"aridity_avg"`
	DominantBiome     *string  `json:"dominant_biome"`
	DominantKoppen    *string  `json:"dominant_koppen"`
	Biomes            []string `json:"biomes,omitempty"`
}

func handleClimateSpecies(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	speciesName := r.URL.Query().Get("name")
	speciesID := r.URL.Query().Get("id")

	if speciesName == "" && speciesID == "" {
		http.Error(w, `{"error": "Provide species name or id"}`, http.StatusBadRequest)
		return
	}

	var resp SpeciesClimateResponse
	var query string
	var args []interface{}

	if speciesID != "" {
		query = `
			SELECT s.id, s.canonical_name, COALESCE(s.family, ''),
				   COUNT(DISTINCT sd.tdwg_code),
				   ROUND(AVG(c.bio1_mean)::numeric, 1),
				   ROUND(MIN(c.bio1_min)::numeric, 1),
				   ROUND(MAX(c.bio1_max)::numeric, 1),
				   ROUND(AVG(c.bio12_mean)::numeric, 0),
				   ROUND(MIN(c.bio12_min)::numeric, 0),
				   ROUND(MAX(c.bio12_max)::numeric, 0),
				   ROUND(AVG(c.aridity_index)::numeric, 1),
				   MODE() WITHIN GROUP (ORDER BY c.whittaker_biome),
				   MODE() WITHIN GROUP (ORDER BY c.koppen_zone)
			FROM species s
			JOIN species_distribution sd ON s.id = sd.species_id AND sd.native = TRUE
			LEFT JOIN tdwg_climate c ON sd.tdwg_code = c.tdwg_code
			WHERE s.id = $1 AND c.bio1_mean IS NOT NULL
			GROUP BY s.id, s.canonical_name, s.family
		`
		args = []interface{}{speciesID}
	} else {
		query = `
			SELECT s.id, s.canonical_name, COALESCE(s.family, ''),
				   COUNT(DISTINCT sd.tdwg_code),
				   ROUND(AVG(c.bio1_mean)::numeric, 1),
				   ROUND(MIN(c.bio1_min)::numeric, 1),
				   ROUND(MAX(c.bio1_max)::numeric, 1),
				   ROUND(AVG(c.bio12_mean)::numeric, 0),
				   ROUND(MIN(c.bio12_min)::numeric, 0),
				   ROUND(MAX(c.bio12_max)::numeric, 0),
				   ROUND(AVG(c.aridity_index)::numeric, 1),
				   MODE() WITHIN GROUP (ORDER BY c.whittaker_biome),
				   MODE() WITHIN GROUP (ORDER BY c.koppen_zone)
			FROM species s
			JOIN species_distribution sd ON s.id = sd.species_id AND sd.native = TRUE
			LEFT JOIN tdwg_climate c ON sd.tdwg_code = c.tdwg_code
			WHERE s.canonical_name ILIKE $1 AND c.bio1_mean IS NOT NULL
			GROUP BY s.id, s.canonical_name, s.family
		`
		args = []interface{}{speciesName}
	}

	err := db.QueryRow(query, args...).Scan(
		&resp.SpeciesID, &resp.CanonicalName, &resp.Family, &resp.NRegions,
		&resp.TempMeanAvg, &resp.TempAbsoluteMin, &resp.TempAbsoluteMax,
		&resp.PrecipMeanAvg, &resp.PrecipAbsoluteMin, &resp.PrecipAbsoluteMax,
		&resp.AridityAvg, &resp.DominantBiome, &resp.DominantKoppen,
	)

	if err != nil {
		http.Error(w, `{"error": "Species not found or no climate data"}`, http.StatusNotFound)
		return
	}

	rows, _ := db.Query(`
		SELECT DISTINCT c.whittaker_biome
		FROM species s
		JOIN species_distribution sd ON s.id = sd.species_id AND sd.native = TRUE
		JOIN tdwg_climate c ON sd.tdwg_code = c.tdwg_code
		WHERE s.id = $1 AND c.whittaker_biome IS NOT NULL
		ORDER BY c.whittaker_biome
	`, resp.SpeciesID)
	if rows != nil {
		defer rows.Close()
		for rows.Next() {
			var biome string
			rows.Scan(&biome)
			resp.Biomes = append(resp.Biomes, biome)
		}
	}

	json.NewEncoder(w).Encode(resp)
}

// handleClimatePoint returns precise climate data from WorldClim rasters at exact coordinates
func handleClimatePoint(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	latStr := r.URL.Query().Get("lat")
	lonStr := r.URL.Query().Get("lon")

	if latStr == "" || lonStr == "" {
		http.Error(w, `{"error": "Provide lat and lon parameters"}`, http.StatusBadRequest)
		return
	}

	lat, err := strconv.ParseFloat(latStr, 64)
	if err != nil {
		http.Error(w, `{"error": "Invalid lat value"}`, http.StatusBadRequest)
		return
	}

	lon, err := strconv.ParseFloat(lonStr, 64)
	if err != nil {
		http.Error(w, `{"error": "Invalid lon value"}`, http.StatusBadRequest)
		return
	}

	// Check if raster data exists
	var rasterCount int
	err = db.QueryRow("SELECT COUNT(*) FROM worldclim_raster").Scan(&rasterCount)
	if err != nil || rasterCount == 0 {
		// Fall back to TDWG-based climate data
		http.Error(w, `{"error": "Raster data not loaded. Use /api/climate with lat/lon for TDWG-based data."}`, http.StatusNotFound)
		return
	}

	// Query climate data from raster using the SQL function
	var climateJSON []byte
	err = db.QueryRow("SELECT get_climate_json_at_point($1, $2)", lat, lon).Scan(&climateJSON)
	if err != nil {
		http.Error(w, `{"error": "No climate data at this location"}`, http.StatusNotFound)
		return
	}

	// Parse the JSON and add metadata
	var climateData map[string]any
	json.Unmarshal(climateJSON, &climateData)

	if len(climateData) == 0 {
		http.Error(w, `{"error": "No climate data at this location (possibly ocean or missing coverage)"}`, http.StatusNotFound)
		return
	}

	// Add request coordinates
	climateData["lat"] = lat
	climateData["lon"] = lon
	climateData["source"] = "worldclim_raster"

	json.NewEncoder(w).Encode(climateData)
}
