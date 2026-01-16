---
name: commit
description: Cria commit com autor Stickybit
arguments:
  - name: message
    description: Mensagem do commit (conventional commits)
    required: true
---

# Commit Stickybit

Cria um commit seguindo o padrão de conventional commits com autor Stickybit.

## Formatos de Mensagem Sugeridos
- `feat: descrição` - Nova funcionalidade
- `fix: descrição` - Correção de bug
- `docs: descrição` - Documentação
- `refactor: descrição` - Refatoração
- `test: descrição` - Testes
- `chore: descrição` - Manutenção

## Comandos

```bash
cd /Users/andreyandrade/Code/DiversiPlantDashboard-sticky
git add -u
git commit --author="Stickybit <dev@stickybit.com.br>" -m "$ARGUMENTS.message"
```

## Verificar Commit

```bash
git log -1 --format="Commit: %H%nAuthor: %an <%ae>%nDate: %ad%nMessage: %s"
```
