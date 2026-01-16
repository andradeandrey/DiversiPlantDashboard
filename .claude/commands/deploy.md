---
name: deploy
description: Deploy da aplicação DiversiPlant
arguments:
  - name: environment
    description: "Ambiente: staging ou production"
    default: staging
---

# Deploy DiversiPlant

Faz o deploy da aplicação para o ambiente especificado.

## Pré-Deploy

### Verificar Testes

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
source venv/bin/activate
python -m pytest tests/ -v
```

### Verificar Sintaxe Python

```bash
python -m py_compile app.py
python -m py_compile crawlers/*.py
python -m py_compile database/*.py
python -m py_compile i18n/*.py
```

### Verificar Dependências

```bash
pip check
```

## Deploy para $ARGUMENTS.environment

### Build

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky

# Atualizar requirements
pip freeze > requirements.txt

# Coletar assets estáticos (se aplicável)
# python manage.py collectstatic --noinput
```

### Git Tag (Production apenas)

```bash
# Para production, criar tag de versão
# git tag -a v$(date +%Y%m%d) -m "Release $(date +%Y-%m-%d)"
# git push origin v$(date +%Y%m%d)
```

### Deploy

```bash
# Deploy via rsync/SSH (exemplo)
# rsync -avz --exclude 'venv' --exclude '__pycache__' ./ user@server:/app/diversiplant/

# OU via Docker (se configurado)
# docker build -t diversiplant:latest .
# docker push registry/diversiplant:latest
```

## Pós-Deploy

### Verificar Saúde

```bash
# curl -s https://$ARGUMENTS.environment.diversiplant.org/health | jq
```

### Verificar Logs

```bash
# ssh user@server "tail -f /var/log/diversiplant/app.log"
```
