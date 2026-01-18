#!/bin/bash
# Run all crawlers with progress monitoring

export DATABASE_URL="postgresql://diversiplant:diversiplant_dev@localhost:5432/diversiplant"

cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
source venv/bin/activate

echo "================================================"
echo "DiversiPlant - Iniciando todos os crawlers"
echo "================================================"
echo ""

# Function to run crawler and show status
run_crawler() {
    local name=$1
    local max_records=${2:-1000}

    echo "----------------------------------------"
    echo "[$(date '+%H:%M:%S')] Iniciando: $name"
    echo "----------------------------------------"

    python -m crawlers.run --source $name --mode incremental --max-records $max_records --verbose 2>&1

    if [ $? -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] $name: CONCLUIDO"
    else
        echo "[$(date '+%H:%M:%S')] $name: ERRO"
    fi
    echo ""
}

# Run each crawler
run_crawler "gbif" 500
run_crawler "gift" 500
run_crawler "reflora" 500
run_crawler "wcvp" 500
run_crawler "treegoer" 500
run_crawler "iucn" 500
run_crawler "worldclim" 100

echo "================================================"
echo "Todos os crawlers finalizados!"
echo "================================================"

# Show final status
psql $DATABASE_URL -c "SELECT crawler_name, status, records_processed, last_success FROM crawler_status ORDER BY crawler_name;"
