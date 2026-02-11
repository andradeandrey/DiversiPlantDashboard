# Deploy do Sistema de Ecoregion Raster - Servidor Produção

**Data**: 2026-02-04
**Servidor**: diversiplant.andreyandrade.com (138.197.46.69)
**Status**: 🔄 Em andamento

---

## Resumo do Deploy

Sistema de identificação precisa de ecoregions usando método raster está sendo implementado no servidor de produção.

### Arquivos Transferidos

| Arquivo | Tamanho | Localização | Status |
|---------|---------|-------------|--------|
| `ecoregions_south_america.tif` | 64 MB | `/opt/diversiplant/data/ecoregions_raster/` | ✅ |
| `create_ecoregion_lookup.py` | ~17 KB | `/opt/diversiplant/scripts/` | ✅ |

### Dependências Instaladas

```bash
pip install tqdm rasterio psycopg2-binary
```

✅ Todas as dependências instaladas no venv do servidor

---

## Processo em Execução

### Comando Executado

```bash
cd /opt/diversiplant
source venv/bin/activate
nohup python scripts/create_ecoregion_lookup.py > logs/ecoregion_raster_deploy.log 2>&1 &
```

### Progresso Esperado

| Fase | Ação | Tempo Estimado |
|------|------|----------------|
| 1. Conexão DB | Conectar e criar tabela | ~1 segundo |
| 2. Sampling raster | Processar 6.900 linhas × 4.800 cols | ~60-70 minutos |
| 3. Inserção batch | Inserir em lotes de 10.000 | (incluído na fase 2) |
| 4. Função SQL | Criar função e VIEW | ~10 segundos |
| 5. Testes | Validar resultados | ~5 segundos |

**Total estimado**: ~60-70 minutos

### Velocidade de Processamento

- **Servidor produção**: ~1.5-2.0 linhas/segundo
- **Máquina local**: ~7-8 linhas/segundo

**Razão**: Hardware menos potente, maior latência de I/O.

---

## Monitoramento

### Verificar Progresso

```bash
# Usar script de monitoramento
./scripts/check_ecoregion_deploy.sh

# Ou manualmente
ssh diversiplant "tail -50 /opt/diversiplant/logs/ecoregion_raster_deploy.log"

# Ver em tempo real
ssh diversiplant "tail -f /opt/diversiplant/logs/ecoregion_raster_deploy.log"
```

### Verificar Processo

```bash
# Ver se está rodando
ssh diversiplant "ps aux | grep create_ecoregion_lookup.py | grep -v grep"

# Ver uso de recursos
ssh diversiplant "top -b -n 1 | grep python"
```

---

## Resultado Esperado

### Banco de Dados

**Tabela criada**:
```sql
CREATE TABLE ecoregion_lookup (
    id SERIAL PRIMARY KEY,
    location geography(POINT, 4326),
    eco_id INTEGER NOT NULL
);
```

**Estatísticas esperadas**:
- **~15.4 milhões** de pontos
- **124 ecoregiões** únicas (América do Sul)
- **~3.6 GB** total (tabela + índice)

**Função criada**:
```sql
CREATE FUNCTION get_ecoregion_from_raster(lon, lat) RETURNS integer;
```

**VIEW criada**:
```sql
CREATE VIEW ecoregion_comparison AS ...
```

### Validação

Após completar, executar testes:

```bash
ssh diversiplant "docker exec diversiplant-db psql -U diversiplant -d diversiplant" <<'EOF'
-- Teste 1: Verificar contagem
SELECT COUNT(*) as total_points,
       COUNT(DISTINCT eco_id) as unique_ecos,
       pg_size_pretty(pg_total_relation_size('ecoregion_lookup')) as size
FROM ecoregion_lookup;

-- Teste 2: Santo Amaro da Imperatriz
SELECT get_ecoregion_from_raster(-48.8, -27.7) as eco_id,
       e.eco_name
FROM ecoregions e
WHERE e.eco_id = get_ecoregion_from_raster(-48.8, -27.7);

-- Teste 3: Comparação de métodos
SELECT * FROM ecoregion_comparison;
EOF
```

**Resultado esperado Teste 2**:
```
eco_id |           eco_name
-------+------------------------------
   500 | Serra do Mar coastal forests
```

---

## Troubleshooting

### Se o processo travou

```bash
# Verificar se está realmente rodando
ssh diversiplant "ps aux | grep create_ecoregion_lookup"

# Ver últimas linhas do log
ssh diversiplant "tail -100 /opt/diversiplant/logs/ecoregion_raster_deploy.log"

# Verificar uso de memória
ssh diversiplant "free -h"

# Verificar espaço em disco
ssh diversiplant "df -h"
```

### Se precisar reiniciar

```bash
# Matar processo
ssh diversiplant "pkill -f create_ecoregion_lookup.py"

# Limpar tabela
ssh diversiplant "docker exec diversiplant-db psql -U diversiplant -d diversiplant -c 'DROP TABLE IF EXISTS ecoregion_lookup CASCADE;'"

# Reiniciar
ssh diversiplant "cd /opt/diversiplant && source venv/bin/activate && nohup python scripts/create_ecoregion_lookup.py > logs/ecoregion_raster_deploy.log 2>&1 &"
```

### Logs Importantes

| Log | Localização |
|-----|-------------|
| Script Python | `/opt/diversiplant/logs/ecoregion_raster_deploy.log` |
| PostgreSQL | `docker logs diversiplant-db` |
| Sistema | `/var/log/syslog` |

---

## Próximos Passos (Após Completar)

### 1. Verificação Final

```bash
# Executar script de verificação
./scripts/check_ecoregion_deploy.sh

# Verificar estatísticas
ssh diversiplant "docker exec diversiplant-db psql -U diversiplant -d diversiplant -c 'SELECT COUNT(*) FROM ecoregion_lookup;'"
```

### 2. Integração com Query-Explorer

Não é necessário reiniciar o query-explorer - a função SQL já está disponível.

Testar via API:
```bash
# Se houver endpoint que use ecoregion
curl -X GET 'https://diversiplant.andreyandrade.com/api/species?lat=-27.7&lon=-48.8'
```

### 3. Documentação

Atualizar documentação de produção com:
- Nova tabela `ecoregion_lookup`
- Nova função `get_ecoregion_from_raster()`
- Nova VIEW `ecoregion_comparison`

---

## Rollback (Se Necessário)

```bash
# Remover completamente
ssh diversiplant "docker exec diversiplant-db psql -U diversiplant -d diversiplant" <<'EOF'
DROP VIEW IF EXISTS ecoregion_comparison CASCADE;
DROP FUNCTION IF EXISTS get_ecoregion_from_raster CASCADE;
DROP TABLE IF EXISTS ecoregion_lookup CASCADE;
EOF

# Remover arquivos
ssh diversiplant "rm -rf /opt/diversiplant/data/ecoregions_raster"
```

**Espaço liberado**: ~3.6 GB

---

## Timeline

| Horário (UTC-3) | Evento | Status |
|-----------------|--------|--------|
| 19:20 | Transferência do raster (64MB) | ✅ Completo |
| 19:21 | Transferência do script Python | ✅ Completo |
| 19:22 | Instalação de dependências | ✅ Completo |
| 19:23 | Início do processamento | ✅ Iniciado |
| ~20:30 | Conclusão esperada (estimativa) | 🔄 Aguardando |

---

## Contato

Em caso de problemas, verificar:
1. Log do script: `/opt/diversiplant/logs/ecoregion_raster_deploy.log`
2. Documentação técnica: `docs/ECOREGION_RASTER_METHOD.md`
3. Implementação local: `docs/ECOREGION_RASTER_IMPLEMENTATION.md`

---

**Status atual**: 🔄 Processamento em andamento (~3% completo)
**ETA**: ~60-70 minutos a partir do início (19:23)
**Conclusão estimada**: ~20:30 UTC-3
