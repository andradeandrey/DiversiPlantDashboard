#!/bin/bash

# Script to apply the recommendation system migration

set -e

# Database configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-diversiplant}"
DB_NAME="${DB_NAME:-diversiplant}"

MIGRATION_FILE="../database/migrations/009_recommendation_system.sql"

echo "================================================================"
echo "Applying Recommendation System Migration"
echo "================================================================"
echo ""
echo "Database: $DB_NAME on $DB_HOST:$DB_PORT"
echo "User: $DB_USER"
echo ""
echo "This will:"
echo "  1. Create species_climate_envelope table"
echo "  2. Create species_trait_vectors table"
echo "  3. Create recommendation_cache table"
echo "  4. Create calculate_climate_match() function"
echo "  5. Populate climate envelopes for all species"
echo "  6. Populate trait vectors for all species"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Applying migration..."
echo ""

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$MIGRATION_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================================"
    echo "Migration applied successfully!"
    echo "================================================================"
    echo ""
    echo "Verifying data..."
    echo ""

    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        SELECT
            'species_climate_envelope' as table_name,
            COUNT(*) as row_count
        FROM species_climate_envelope
        UNION ALL
        SELECT
            'species_trait_vectors',
            COUNT(*)
        FROM species_trait_vectors;
    "

    echo ""
    echo "Ready to test! Try running:"
    echo ""
    echo "  curl -X POST http://localhost:8080/api/recommend \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"tdwg_code\": \"BZS\", \"n_species\": 20, \"climate_threshold\": 0.6}'"
    echo ""
else
    echo ""
    echo "Migration failed. Please check the error messages above."
    exit 1
fi
