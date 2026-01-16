---
name: dev-server
description: Inicia servidor de desenvolvimento
arguments:
  - name: port
    description: Porta do servidor
    default: "8001"
---

# Servidor de Desenvolvimento

Inicia o servidor Shiny/Starlette em modo de desenvolvimento com hot-reload.

## Comandos

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
source venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port $ARGUMENTS.port --reload
```

## Acessar

Abra no navegador: http://127.0.0.1:$ARGUMENTS.port/diversiplant

## Parar Servidor

Pressione `Ctrl+C` no terminal.
