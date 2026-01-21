package main

import (
	"context"
	"crypto/tls"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
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

	// API routes
	mux.HandleFunc("/api/health", handleHealth)
	mux.HandleFunc("/api/stats", handleStats)
	mux.HandleFunc("/api/tdwg", handleTDWG)
	mux.HandleFunc("/api/species", handleSpecies)
	mux.HandleFunc("/api/query", handleQuery)
	mux.HandleFunc("/api/sources", handleSources)

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

		// HTTP redirect to HTTPS
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
	tables := []string{"species", "species_unified", "species_regions", "species_geometry", "tdwg_level3"}
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
		switch growthForm {
		case "tree":
			query += " AND su.is_tree = TRUE"
		case "shrub":
			query += " AND su.is_shrub = TRUE"
		case "herb":
			query += " AND su.is_herb = TRUE"
		case "climber":
			query += " AND su.is_climber = TRUE"
		case "palm":
			query += " AND su.is_palm = TRUE"
		default:
			query += fmt.Sprintf(" AND su.growth_form = $%d", argNum)
			args = append(args, growthForm)
			argNum++
		}
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
		switch growthForm {
		case "tree":
			countQuery += " AND su.is_tree = TRUE"
		case "shrub":
			countQuery += " AND su.is_shrub = TRUE"
		case "herb":
			countQuery += " AND su.is_herb = TRUE"
		case "climber":
			countQuery += " AND su.is_climber = TRUE"
		case "palm":
			countQuery += " AND su.is_palm = TRUE"
		default:
			countQuery += fmt.Sprintf(" AND su.growth_form = $%d", countArgNum)
			countArgs = append(countArgs, growthForm)
		}
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
	if err != nil {
		http.Error(w, fmt.Sprintf(`{"error": "%s"}`, err.Error()), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type SourceStats struct {
		Source   string `json:"source"`
		Total    int64  `json:"total"`
		Trees    int64  `json:"trees"`
		Shrubs   int64  `json:"shrubs"`
		Herbs    int64  `json:"herbs"`
		Climbers int64  `json:"climbers"`
		Palms    int64  `json:"palms"`
	}

	var sources []SourceStats
	for rows.Next() {
		var s SourceStats
		rows.Scan(&s.Source, &s.Total, &s.Trees, &s.Shrubs, &s.Herbs, &s.Climbers, &s.Palms)
		sources = append(sources, s)
	}

	json.NewEncoder(w).Encode(sources)
}
