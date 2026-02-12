# DiversiPlant Docker Setup

## Architecture

```
Internet → go-server:443 (HTTPS/Let's Encrypt)
              ├─ /api/*           → Go handlers (→ db:5432)
              ├─ /diversiplant/*  → proxy → dashboard:8001
              └─ /                → static/ (admin UI)

dashboard:8001 (Python/Shiny, internal only)
              └─ POST go-server:8080/api/recommend

db:5432 (PostgreSQL 16 + PostGIS, internal only)
```

Only the Go server exposes ports 80/443 to the host. The `:8080` internal listener allows the dashboard to call the recommend API within the Docker network.

## Files

| File | Purpose |
|------|---------|
| `Dockerfile.dashboard` | Python 3.12 + GDAL + R + GIFT, copies app code + small data |
| `query-explorer/Dockerfile` | Multi-stage Go build → `debian:bookworm-slim` runtime |
| `docker-compose.prod.yml` | 3 services: `db`, `dashboard`, `go-server` |
| `.dockerignore` | Excludes large data, .git, Go project, dev files |
| `query-explorer/.dockerignore` | Excludes compiled binaries, logs |
| `.env.prod` | Template with all env vars (NOT committed) |
| `scripts/deploy-docker.sh` | rsync + docker compose build/up + healthcheck |

## Volumes

| Data | Strategy |
|------|----------|
| `data/ecoregions_raster/` (~296MB) | Bind mount from host |
| Let's Encrypt certs | Named volume `certs_data` |
| PostgreSQL data | Named volume `postgres_data` (reuses existing) |
| Small data (ui.css, csv, img) | Baked into dashboard image |

## Quick Start (Local Dev)

```bash
# 1. Copy and edit env file
cp .env.prod .env
# Edit .env — set DB_PASSWORD, DEV_MODE=true

# 2. Create postgres volume (if first time)
docker volume create diversiplant_postgres_data

# 3. Build and run
docker compose -f docker-compose.prod.yml --env-file .env up --build
```

With `DEV_MODE=true`, the Go server listens on `:8080` (HTTP only, no TLS).

## Deploy to Production

```bash
# 1. Edit .env.prod with real secrets
# 2. Run deploy script
bash scripts/deploy-docker.sh
```

The script will:
1. Create remote dirs + ensure postgres volume exists
2. Backup existing database
3. rsync project files to `/opt/diversiplant/src/`
4. Copy `.env.prod` as `.env` on server
5. Stop old native Go binary
6. `docker compose build && up -d`
7. Health check via `/api/health`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `diversiplant` | Database user |
| `DB_PASSWORD` | — | Database password (required) |
| `DB_NAME` | `diversiplant` | Database name |
| `DOMAIN` | `diversiplant.andreyandrade.com` | Domain for Let's Encrypt |
| `DEV_MODE` | `false` | `true` = HTTP only on :8080 |
| `GO_API_URL` | `http://127.0.0.1:8080/api/recommend` | Go API URL (set by compose) |
| `DASHBOARD_URL` | `http://127.0.0.1:8001` | Dashboard URL (set by compose) |
| `ECOREGIONS_PATH` | `./data/ecoregions_raster` | Host path to ecoregions data |
| `POSTGRES_VOLUME` | `diversiplant_postgres_data` | Named volume for DB |

## Verification

```bash
# API health
curl https://diversiplant.andreyandrade.com/api/health

# Dashboard
open https://diversiplant.andreyandrade.com/diversiplant/

# Logs
ssh root@138.197.46.69 'cd /opt/diversiplant/src && docker compose -f docker-compose.prod.yml logs -f'
```
