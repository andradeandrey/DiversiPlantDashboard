#!/bin/bash
set -e

# =============================================================================
# Deploy Script - DiversiPlant Query Explorer + Climate Envelopes
# =============================================================================
# This script deploys:
# - Query Explorer binary (Go server)
# - Climate envelope migrations (010 + 011)
# - Unified envelope system (GBIF + TreeGOER + WCVP)
# =============================================================================

SERVER="diversiplant"
REMOTE_DIR="/opt/diversiplant"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🚀 DiversiPlant Deployment Script"
echo "=================================="
echo ""
echo "Server: $SERVER"
echo "Timestamp: $TIMESTAMP"
echo ""

# =============================================================================
# STEP 1: Backup Remote Database
# =============================================================================
echo "📦 [1/7] Creating database backup..."
ssh $SERVER "docker exec diversiplant-db pg_dump -U diversiplant diversiplant | gzip > $REMOTE_DIR/backups/diversiplant_${TIMESTAMP}.sql.gz"
echo "✅ Backup created: diversiplant_${TIMESTAMP}.sql.gz"
echo ""

# =============================================================================
# STEP 2: Stop Query Explorer Service
# =============================================================================
echo "🛑 [2/7] Stopping query-explorer service..."
ssh $SERVER "pkill -9 query-explorer || true"
sleep 2
echo "✅ Service stopped"
echo ""

# =============================================================================
# STEP 3: Upload Binary
# =============================================================================
echo "📤 [3/7] Uploading query-explorer binary..."
scp query-explorer/query-explorer-linux $SERVER:$REMOTE_DIR/query-explorer/query-explorer
ssh $SERVER "chmod +x $REMOTE_DIR/query-explorer/query-explorer"
echo "✅ Binary uploaded (9.7MB)"
echo ""

# =============================================================================
# STEP 4: Upload Migrations
# =============================================================================
echo "📤 [4/7] Uploading migrations..."
scp database/migrations/010_climate_envelope_system.sql $SERVER:$REMOTE_DIR/database/migrations/
scp database/migrations/011_unified_climate_envelope_view.sql $SERVER:$REMOTE_DIR/database/migrations/
echo "✅ Migrations uploaded"
echo ""

# =============================================================================
# STEP 5: Apply Migrations
# =============================================================================
echo "🔧 [5/7] Applying migrations..."

# Migration 010 (if not already applied)
echo "  - Checking migration 010..."
ssh $SERVER "docker exec diversiplant-db psql -U diversiplant -d diversiplant -c \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='climate_envelope_gbif')\" -t | grep -q t && echo '    Already applied' || docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < $REMOTE_DIR/database/migrations/010_climate_envelope_system.sql"

# Migration 011 (unified view)
echo "  - Applying migration 011 (unified view)..."
ssh $SERVER "docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < $REMOTE_DIR/database/migrations/011_unified_climate_envelope_view.sql"

echo "✅ Migrations applied"
echo ""

# =============================================================================
# STEP 6: Populate Envelopes (if needed)
# =============================================================================
echo "🌱 [6/7] Checking envelope population..."

# Check if envelopes are already populated
GBIF_COUNT=$(ssh $SERVER "docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -c 'SELECT COUNT(*) FROM climate_envelope_gbif;'" | tr -d ' ')
ECO_COUNT=$(ssh $SERVER "docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -c 'SELECT COUNT(*) FROM climate_envelope_ecoregion;'" | tr -d ' ')
WCVP_COUNT=$(ssh $SERVER "docker exec diversiplant-db psql -U diversiplant -d diversiplant -t -c 'SELECT COUNT(*) FROM species_climate_envelope;'" | tr -d ' ')

echo "  Current envelope counts:"
echo "    - GBIF: $GBIF_COUNT"
echo "    - Ecoregion (TreeGOER): $ECO_COUNT"
echo "    - WCVP: $WCVP_COUNT"
echo ""

# Upload population scripts
echo "  Uploading population scripts..."
scp scripts/populate-wcvp-envelopes.sql $SERVER:$REMOTE_DIR/scripts/
scp scripts/populate-ecoregion-envelopes.sql $SERVER:$REMOTE_DIR/scripts/

# Populate WCVP if needed
if [ "$WCVP_COUNT" -lt "100000" ]; then
    echo "  - Populating WCVP envelopes..."
    ssh $SERVER "docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < $REMOTE_DIR/scripts/populate-wcvp-envelopes.sql"
else
    echo "  - WCVP envelopes already populated"
fi

# Populate Ecoregion if needed
if [ "$ECO_COUNT" -lt "40000" ]; then
    echo "  - Populating Ecoregion envelopes..."
    ssh $SERVER "docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < $REMOTE_DIR/scripts/populate-ecoregion-envelopes.sql"
else
    echo "  - Ecoregion envelopes already populated"
fi

echo "✅ Envelopes populated"
echo ""

# =============================================================================
# STEP 7: Start Query Explorer Service
# =============================================================================
echo "🚀 [7/7] Starting query-explorer service..."

ssh $SERVER << 'ENDSSH'
cd /opt/diversiplant/query-explorer

# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=diversiplant
export DB_PASSWORD=diversiplant_dev
export DB_NAME=diversiplant
export DEV_MODE=false

# Start in background with nohup
nohup ./query-explorer > ../logs/query-explorer.log 2>&1 &
echo $! > query-explorer.pid

# Wait for server to start
sleep 3

# Check if running
if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
    echo "✅ Query Explorer is running!"
    echo "   PID: $(cat query-explorer.pid)"
    echo "   Health: http://localhost:8080/api/health"
else
    echo "⚠️  Warning: Server may not be responding yet"
    echo "   Check logs: tail -f /opt/diversiplant/logs/query-explorer.log"
fi
ENDSSH

echo ""
echo "=================================="
echo "✅ Deployment Complete!"
echo "=================================="
echo ""
echo "📊 Verification commands:"
echo "   ssh $SERVER 'curl -s http://localhost:8080/api/health | jq .'"
echo "   ssh $SERVER 'tail -f $REMOTE_DIR/logs/query-explorer.log'"
echo ""
echo "🔍 Check envelope coverage:"
echo "   ssh $SERVER 'docker exec diversiplant-db psql -U diversiplant -d diversiplant -c \"SELECT envelope_source, COUNT(*) FROM species_climate_envelope_unified GROUP BY envelope_source;\"'"
echo ""
echo "🌳 Test recommendation API:"
echo "   curl -X POST http://diversiplant.andreyandrade.com/api/recommend -H 'Content-Type: application/json' -d '{\"tdwg_code\":\"BZS\",\"n_species\":10}'"
echo ""
