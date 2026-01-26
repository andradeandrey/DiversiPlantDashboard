#!/bin/bash
# Deploy Climate Envelope System to Production
#
# This script uploads and applies the multi-source climate envelope system
# including migration, crawler, and analysis scripts.
#
# Usage:
#   ./scripts/deploy-envelope-system.sh
#   ./scripts/deploy-envelope-system.sh --skip-crawler  # Skip GBIF crawler
#   ./scripts/deploy-envelope-system.sh --analysis-only  # Only run analysis

set -e

# Configuration
SERVER="${DIVERSIPLANT_SERVER:-diversiplant@diversiplant.andreyandrade.com}"
DB_NAME="${DIVERSIPLANT_DB:-diversiplant}"
REMOTE_DIR="/opt/diversiplant"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
SKIP_CRAWLER=false
ANALYSIS_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-crawler)
            SKIP_CRAWLER=true
            shift
            ;;
        --analysis-only)
            ANALYSIS_ONLY=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}=== Climate Envelope System Deploy ===${NC}"
echo "Server: $SERVER"
echo "Database: $DB_NAME"
echo "Skip Crawler: $SKIP_CRAWLER"
echo "Analysis Only: $ANALYSIS_ONLY"
echo ""

# Check if files exist
check_files() {
    local files=(
        "database/migrations/010_climate_envelope_system.sql"
        "crawlers/gbif_occurrences.py"
        "scripts/populate-wcvp-envelopes.sql"
        "scripts/populate-ecoregion-envelopes.sql"
        "scripts/analyze-envelope-discrepancies.sql"
    )

    for file in "${files[@]}"; do
        if [[ ! -f "$file" ]]; then
            echo -e "${RED}Missing file: $file${NC}"
            exit 1
        fi
    done
    echo -e "${GREEN}All files present${NC}"
}

if [[ "$ANALYSIS_ONLY" == "false" ]]; then

    echo -e "${YELLOW}[1/7] Checking local files...${NC}"
    check_files

    echo -e "${YELLOW}[2/7] Uploading migration...${NC}"
    scp database/migrations/010_climate_envelope_system.sql "$SERVER:$REMOTE_DIR/migrations/"

    echo -e "${YELLOW}[3/7] Uploading GBIF crawler...${NC}"
    scp crawlers/gbif_occurrences.py "$SERVER:$REMOTE_DIR/crawlers/"

    echo -e "${YELLOW}[4/7] Uploading SQL scripts...${NC}"
    scp scripts/populate-wcvp-envelopes.sql "$SERVER:$REMOTE_DIR/scripts/"
    scp scripts/populate-ecoregion-envelopes.sql "$SERVER:$REMOTE_DIR/scripts/"
    scp scripts/analyze-envelope-discrepancies.sql "$SERVER:$REMOTE_DIR/scripts/"

    echo -e "${YELLOW}[5/7] Applying migration...${NC}"
    ssh "$SERVER" "cd $REMOTE_DIR && psql -d $DB_NAME -f migrations/010_climate_envelope_system.sql"

    echo -e "${YELLOW}[6/7] Populating WCVP envelopes...${NC}"
    ssh "$SERVER" "cd $REMOTE_DIR && psql -d $DB_NAME -f scripts/populate-wcvp-envelopes.sql"

    echo -e "${YELLOW}[7/7] Populating Ecoregion envelopes...${NC}"
    ssh "$SERVER" "cd $REMOTE_DIR && psql -d $DB_NAME -f scripts/populate-ecoregion-envelopes.sql"

fi

echo -e "${YELLOW}Running discrepancy analysis...${NC}"
ssh "$SERVER" "cd $REMOTE_DIR && psql -d $DB_NAME -f scripts/analyze-envelope-discrepancies.sql"

echo ""
echo -e "${GREEN}=== Deploy Complete ===${NC}"
echo ""
echo "Next steps:"
echo ""

if [[ "$SKIP_CRAWLER" == "false" && "$ANALYSIS_ONLY" == "false" ]]; then
    echo "1. Run GBIF occurrence crawler (this takes time):"
    echo "   ssh $SERVER 'cd $REMOTE_DIR && python -m crawlers.run gbif_occurrences --limit 10000'"
    echo ""
    echo "2. After crawler finishes, re-run analysis:"
    echo "   ssh $SERVER 'cd $REMOTE_DIR && psql -d $DB_NAME -f scripts/analyze-envelope-discrepancies.sql'"
    echo ""
fi

echo "View coverage summary:"
echo "   ssh $SERVER \"psql -d $DB_NAME -c 'SELECT * FROM v_envelope_coverage_summary'\""
echo ""
echo "View species needing review:"
echo "   ssh $SERVER \"psql -d $DB_NAME -c 'SELECT * FROM climate_envelope_analysis WHERE needs_review LIMIT 20'\""
echo ""
