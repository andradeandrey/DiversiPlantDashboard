# 🚀 Deploy para Servidor DiversiPlant

## 📋 Checklist Pré-Deploy

### Arquivos Preparados
- ✅ `query-explorer/query-explorer-linux` (9.7MB) - Binário compilado para Linux
- ✅ `database/migrations/010_climate_envelope_system.sql` (14KB) - Tabelas de climate envelopes
- ✅ `database/migrations/011_unified_climate_envelope_view.sql` (5.5KB) - VIEW unificada
- ✅ `scripts/populate-ecoregion-envelopes.sql` (4.6KB) - População TreeGOER
- ✅ `scripts/populate-wcvp-envelopes.sql` (3.2KB) - População WCVP
- ✅ `scripts/deploy-to-diversiplant.sh` (6.8KB) - Script automatizado

### O Que Será Atualizado

#### 1. **Banco de Dados PostgreSQL**
- Novas tabelas:
  - `climate_envelope_gbif` (GBIF occurrences-based envelopes)
  - `climate_envelope_ecoregion` (TreeGOER-based envelopes)
  - `species_climate_envelope` (WCVP-based envelopes - já existente, será populada)
- Nova VIEW:
  - `species_climate_envelope_unified` (combina as 3 fontes com priorização)

#### 2. **Query Explorer Server**
- Binário Go atualizado com:
  - Suporte ao endpoint `/api/recommend` (recomendação de diversidade)
  - Suporte ao endpoint `/api/ecoregion/species`
  - Uso da VIEW unificada para climate matching

#### 3. **Dados Populados**
- **WCVP Envelopes**: ~362,000 espécies (agregado de regiões TDWG)
- **Ecoregion Envelopes**: ~46,767 árvores (TreeGOER + centroides de ecoregiões)
- **GBIF Envelopes**: ~15,878 espécies (occurrences individuais - se já processado)

---

## 🎯 Resultados Esperados

### Cobertura de Climate Envelopes

| Fonte | Espécies | Descrição |
|-------|----------|-----------|
| GBIF | ~15,878 | Baseado em occurrences individuais (alta qualidade) |
| Ecoregion (TreeGOER) | ~46,767 | Árvores com dados de ecoregiões |
| WCVP | ~362,000 | Todas as espécies com distribuição TDWG |
| **UNIFIED** | **~181,932** | VIEW que prioriza GBIF > Ecoregion > WCVP |

### Cobertura de Árvores
- **Antes**: 23,694 árvores (41.4%)
- **Depois**: 42,295 árvores (73.9%)
- **Ganho**: +78.5% de cobertura 🎉

---

## 🚀 Como Executar o Deploy

### Opção 1: Deploy Automatizado (Recomendado)

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
./scripts/deploy-to-diversiplant.sh
```

### Opção 2: Deploy Manual

Se preferir executar passo a passo:

#### 1. Backup do Banco
```bash
ssh diversiplant@diversiplant.andreyandrade.com
docker exec diversiplant-db pg_dump -U diversiplant diversiplant | gzip > /opt/diversiplant/backups/backup_$(date +%Y%m%d).sql.gz
```

#### 2. Parar Servidor
```bash
pkill -9 query-explorer
```

#### 3. Enviar Binário
```bash
scp query-explorer/query-explorer-linux diversiplant@diversiplant.andreyandrade.com:/opt/diversiplant/query-explorer/query-explorer
```

#### 4. Enviar Migrations
```bash
scp database/migrations/010_climate_envelope_system.sql diversiplant@diversiplant.andreyandrade.com:/opt/diversiplant/database/migrations/
scp database/migrations/011_unified_climate_envelope_view.sql diversiplant@diversiplant.andreyandrade.com:/opt/diversiplant/database/migrations/
```

#### 5. Aplicar Migrations
```bash
ssh diversiplant@diversiplant.andreyandrade.com
cd /opt/diversiplant

# Migration 010
docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < database/migrations/010_climate_envelope_system.sql

# Migration 011
docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < database/migrations/011_unified_climate_envelope_view.sql
```

#### 6. Popular Envelopes
```bash
# WCVP
docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < scripts/populate-wcvp-envelopes.sql

# Ecoregion (TreeGOER)
docker exec -i diversiplant-db psql -U diversiplant -d diversiplant < scripts/populate-ecoregion-envelopes.sql
```

#### 7. Iniciar Servidor
```bash
cd /opt/diversiplant/query-explorer
export DB_HOST=localhost DB_PORT=5432 DB_USER=diversiplant DB_PASSWORD=diversiplant_dev DB_NAME=diversiplant
nohup ./query-explorer > ../logs/query-explorer.log 2>&1 &
```

---

## 🔍 Verificação Pós-Deploy

### 1. Verificar Servidor
```bash
curl http://localhost:8080/api/health
```

Resposta esperada:
```json
{
  "status": "ok",
  "database": "connected",
  "postgis": "3.4",
  "tables": {
    "species": 448926,
    "species_climate_envelope_unified": 181932
  }
}
```

### 2. Verificar Envelopes
```bash
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT
    envelope_source,
    COUNT(*) as species_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM species_climate_envelope_unified
GROUP BY envelope_source
ORDER BY species_count DESC;
"
```

Resultado esperado:
```
 envelope_source | species_count | percentage
-----------------+---------------+------------
 wcvp            |       119187  |      65.5
 ecoregion       |        46867  |      25.8
 gbif            |        15878  |       8.7
```

### 3. Testar Recomendação
```bash
curl -X POST http://localhost:8080/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "tdwg_code": "BZS",
    "n_species": 10,
    "climate_threshold": 0.6,
    "preferences": {"growth_forms": ["tree"]}
  }'
```

Deve retornar 10 árvores com:
- `climate_match_score` > 0.6
- `diversity_contribution` calculado
- `envelope_source` indicando qual fonte foi usada

---

## 📊 Monitoramento

### Logs do Servidor
```bash
ssh diversiplant@diversiplant.andreyandrade.com
tail -f /opt/diversiplant/logs/query-explorer.log
```

### Performance do Banco
```bash
docker exec diversiplant-db psql -U diversiplant -d diversiplant -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'climate_envelope%' OR tablename = 'species_climate_envelope'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

---

## 🆘 Rollback (Se Necessário)

### 1. Parar Servidor
```bash
pkill -9 query-explorer
```

### 2. Restaurar Backup
```bash
# Encontrar último backup
ls -lht /opt/diversiplant/backups/ | head -5

# Restaurar (substitua TIMESTAMP)
docker exec diversiplant-db dropdb -U diversiplant --if-exists diversiplant_temp
docker exec diversiplant-db createdb -U diversiplant diversiplant_temp
zcat /opt/diversiplant/backups/diversiplant_TIMESTAMP.sql.gz | \
  docker exec -i diversiplant-db psql -U diversiplant diversiplant_temp

# Renomear bancos (swap)
docker exec diversiplant-db psql -U postgres -c "
  ALTER DATABASE diversiplant RENAME TO diversiplant_broken;
  ALTER DATABASE diversiplant_temp RENAME TO diversiplant;
"
```

### 3. Restaurar Binário Anterior
```bash
cp /opt/diversiplant/query-explorer/query-explorer.backup \
   /opt/diversiplant/query-explorer/query-explorer
```

### 4. Reiniciar Servidor
```bash
cd /opt/diversiplant/query-explorer
./query-explorer &
```

---

## 📞 Suporte

Em caso de problemas:
1. Verificar logs: `tail -f /opt/diversiplant/logs/query-explorer.log`
2. Verificar conexão do banco: `docker ps | grep diversiplant-db`
3. Testar health endpoint: `curl localhost:8080/api/health`
4. Verificar migrations aplicadas:
   ```sql
   SELECT tablename FROM pg_tables
   WHERE tablename LIKE 'climate_envelope%';
   ```

---

## ✅ Checklist Final

Após deploy, verificar:
- [ ] Servidor responde em `http://localhost:8080/api/health`
- [ ] VIEW `species_climate_envelope_unified` existe
- [ ] Contagem de envelopes: GBIF + Ecoregion + WCVP ≈ 181,932
- [ ] Endpoint `/api/recommend` funciona
- [ ] Logs sem erros críticos
- [ ] Performance aceitável (<500ms para recomendações)

---

**Data do Deploy**: 2026-02-04
**Versão**: Query Explorer v2.0 + Unified Climate Envelopes
**Responsável**: Andrey Andrade
