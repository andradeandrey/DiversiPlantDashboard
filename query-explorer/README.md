# Query Explorer

Admin dashboard e explorador de queries SQL para o DiversiPlant.

## Requisitos

- Go 1.21+
- PostgreSQL 16 com PostGIS 3.4
- Banco DiversiPlant configurado

## Executar Localmente

```bash
cd query-explorer
DEV_MODE=true DB_PASSWORD=diversiplant_dev go run main.go
```

Acesse: http://localhost:8080

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DEV_MODE` | `false` | Modo desenvolvimento (HTTP na porta 8080) |
| `DB_HOST` | `localhost` | Host do PostgreSQL |
| `DB_PORT` | `5432` | Porta do PostgreSQL |
| `DB_USER` | `diversiplant` | Usuário do banco |
| `DB_PASSWORD` | `diversiplant` | Senha do banco |
| `DB_NAME` | `diversiplant` | Nome do banco |
| `DOMAIN` | `diversiplant.andreyandrade.com` | Domínio para HTTPS (produção) |
| `CERT_DIR` | `/opt/diversiplant-admin/certs` | Diretório para certificados Let's Encrypt |

## API Endpoints

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/health` | GET | Status do banco e PostGIS |
| `/api/stats` | GET | Estatísticas gerais |
| `/api/sources` | GET | Distribuição por fonte de dados |
| `/api/tdwg?lat=&lon=` | GET | Região TDWG por coordenadas |
| `/api/species?tdwg_code=&growth_form=` | GET | Espécies por região |
| `/api/query` | POST | Query SQL customizada (SELECT apenas) |

## Funcionalidades

- Dashboard com estatísticas do banco
- Distribuição de espécies por fonte (GIFT, WCVP, REFLORA, TreeGOER)
- Consulta por localização (TDWG ou PostGIS direto)
- Query SQL customizada com queries de exemplo
- Verificação de qualidade de dados
- Visualização do schema das tabelas
