#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------------
# DiversiPlant Docker Deploy
# Syncs project to server and runs docker compose
# --------------------------------------------------

SERVER="root@138.197.46.69"
REMOTE_DIR="/opt/diversiplant/src"
ENV_FILE=".env.prod"
COMPOSE_FILE="docker-compose.prod.yml"

echo "=== DiversiPlant Docker Deploy ==="

# 0. Pre-flight checks
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.prod and fill in secrets."
  exit 1
fi

# 1. Prepare remote dirs + ensure postgres volume exists + backup
echo "[1/5] Preparing remote and backing up database..."
ssh "$SERVER" "mkdir -p /opt/diversiplant/backups $REMOTE_DIR && \
  docker volume create diversiplant_postgres_data 2>/dev/null || true"

ssh "$SERVER" 'docker exec $(docker ps -qf "ancestor=postgis/postgis:16-3.4" | head -1) \
  pg_dump -U diversiplant diversiplant 2>/dev/null | gzip > /opt/diversiplant/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz' \
  2>/dev/null || echo "  (skip: no running postgres container yet)"

# 2. Sync project files
echo "[2/5] Syncing project to $REMOTE_DIR..."
rsync -az --delete \
  --exclude='.git' \
  --exclude='data/ecoregions_raster' \
  --exclude='data/gbif_s3' \
  --exclude='data/wc2' \
  --exclude='data/traitbank_raw' \
  --exclude='data/Ecoregions2017.zip' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='query-explorer/diversiplant-server' \
  --exclude='query-explorer/query-explorer' \
  --exclude='query-explorer/query-explorer-linux' \
  --exclude='query-explorer/query-explorer-test' \
  --exclude='query-explorer/server.log' \
  --exclude='.env*' \
  --exclude='figma' \
  ./ "$SERVER:$REMOTE_DIR/"

# 3. Copy env file
echo "[3/5] Deploying $ENV_FILE..."
scp "$ENV_FILE" "$SERVER:$REMOTE_DIR/.env"

# 4. Stop old native binary (if running) + build and start containers
echo "[4/5] Building and starting containers..."
ssh "$SERVER" "pkill -f diversiplant-server 2>/dev/null || true; pkill -f query-explorer 2>/dev/null || true"
ssh "$SERVER" "cd $REMOTE_DIR && \
  docker compose -f $COMPOSE_FILE --env-file .env build && \
  docker compose -f $COMPOSE_FILE --env-file .env up -d"

# 5. Health check
echo "[5/5] Waiting for health check..."
sleep 8

STATUS=$(ssh "$SERVER" "curl -sf http://localhost:8080/api/health 2>/dev/null || echo 'FAIL'")
if echo "$STATUS" | grep -q '"status":"ok"'; then
  echo "=== Deploy successful! ==="
  echo "  API:       https://diversiplant.andreyandrade.com/api/health"
  echo "  Dashboard: https://diversiplant.andreyandrade.com/diversiplant/"
else
  echo "=== Health check returned: $STATUS ==="
  echo "Check logs with: ssh $SERVER 'cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE logs'"
  exit 1
fi
