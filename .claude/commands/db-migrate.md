---
name: db-migrate
description: Aplica migrações do banco de dados
---

# Migrações do Banco de Dados

Aplica o schema e migrações pendentes ao banco PostgreSQL.

## Verificar Conexão

```bash
psql -h localhost -U diversiplant -d diversiplant -c "SELECT version();"
```

## Verificar PostGIS

```bash
psql -h localhost -U diversiplant -d diversiplant -c "SELECT PostGIS_version();"
```

## Aplicar Schema Inicial

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
psql -h localhost -U diversiplant -d diversiplant -f database/schema.sql
```

## Verificar Tabelas Criadas

```bash
psql -h localhost -U diversiplant -d diversiplant -c "\dt"
```

## Verificar Status dos Crawlers

```bash
psql -h localhost -U diversiplant -d diversiplant -c "SELECT * FROM crawler_status;"
```

## Listar Migrações Disponíveis

```bash
ls -la /Users/andreyandrade/Code/DiversiPlantDashboard-sticky/database/migrations/
```

## Criar Nova Migração

Para criar uma nova migração, crie um arquivo em `database/migrations/` com o formato:
`YYYYMMDD_HHMMSS_description.sql`

Exemplo:
```bash
touch /Users/andreyandrade/Code/DiversiPlantDashboard-sticky/database/migrations/$(date +%Y%m%d_%H%M%S)_add_new_column.sql
```
