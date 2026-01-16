---
name: db-backup
description: Backup do banco PostgreSQL DiversiPlant
---

# Backup do Banco de Dados

Cria um backup completo do banco PostgreSQL DiversiPlant.

## Criar Backup

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/Users/andreyandrade/Code/DiversiPlantDashboard-sticky/backups"
mkdir -p $BACKUP_DIR

pg_dump -h localhost -U diversiplant -d diversiplant \
  --format=custom \
  --file="${BACKUP_DIR}/diversiplant_${TIMESTAMP}.dump"

echo "Backup criado: ${BACKUP_DIR}/diversiplant_${TIMESTAMP}.dump"
```

## Listar Backups Recentes

```bash
ls -lh /Users/andreyandrade/Code/DiversiPlantDashboard-sticky/backups/diversiplant_*.dump 2>/dev/null | tail -5
```

## Restaurar Backup (se necessário)

```bash
# pg_restore -h localhost -U diversiplant -d diversiplant --clean ARQUIVO.dump
```

## Backup Apenas dos Dados (SQL)

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/Users/andreyandrade/Code/DiversiPlantDashboard-sticky/backups"

pg_dump -h localhost -U diversiplant -d diversiplant \
  --data-only \
  --file="${BACKUP_DIR}/diversiplant_data_${TIMESTAMP}.sql"
```
