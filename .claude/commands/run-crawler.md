---
name: run-crawler
description: Executa crawlers de dados do DiversiPlant
arguments:
  - name: source
    description: "Fonte: reflora, gbif, gift, wcvp, worldclim, treegoer, iucn, ou 'all'"
    required: true
  - name: mode
    description: "Modo: full ou incremental"
    default: incremental
---

# Executar Crawler DiversiPlant

Execute o crawler especificado para atualizar os dados de espécies.

## Crawlers Disponíveis
- **reflora**: Flora do Brasil 2020 (~50k espécies brasileiras)
- **gbif**: Global Biodiversity Information Facility (~2M espécies)
- **gift**: Global Inventory of Floras and Traits (traits funcionais)
- **wcvp**: World Checklist of Vascular Plants (backbone taxonômico)
- **worldclim**: Dados climáticos bioclimáticos
- **treegoer**: Árvores por ecorregião
- **iucn**: Status de conservação IUCN

## Comandos

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
source venv/bin/activate
python -m crawlers.run --source $ARGUMENTS.source --mode $ARGUMENTS.mode --verbose
```

## Verificar Resultado

```bash
psql -d diversiplant -c "SELECT * FROM crawler_status WHERE crawler_name='$ARGUMENTS.source'"
```

## Verificar Logs

```bash
psql -d diversiplant -c "SELECT * FROM crawler_logs WHERE crawler_name='$ARGUMENTS.source' ORDER BY timestamp DESC LIMIT 10"
```
