# Feedback do Cliente — Reorganizacao do Aditivo Marco 2026
*Recebido em 2026-03-01 | Base: variante C (docs 1.c e 2.c)*

---

## Resumo das Mudancas Solicitadas

O cliente reorganizou as prioridades da variante C:
- **Emergencial**: manter U1-U3, A3, A4 + subir 4 itens pagos (M3, A2, M2, A6)
- **Adiar A7, A8, B7**: os 3 itens "absorvidos sem custo" (60h) vao para novo contrato
- **M5 i18n**: cliente pediu esclarecimento — nao entendeu o item
- **Itens do contrato original**: cliente pede que #7 (scheduler), #9 (docs GitHub), #10 (TreeGOER) sejam incluidos no emergencial
- **Bug adicional**: nomes cientificos duplicados na busca (Panicum miliaceum, Cnidoscolus aconitifolius, Aspidosperma cuspa)

---

## BLOCO 1 — EMERGENCIAL (sem custo adicional)

### Mantidos da variante C

| Item | Descricao | Horas |
|------|-----------|-------|
| U1 | Fix INNER JOIN na busca — desbloqueia 89% das especies invisiveis | 8h |
| U2 | Corrigir `is_endemic = 0` para todos os registros no crawler WCVP | 6h |
| U3 | Limpeza de ~15 growth forms residuais | 2h |
| A3 | Fix Max Species cap: 999/1000 retorna 100 | 4h |
| A4 | Sort alfabetico como default | 8h |
| **Subtotal** | | **28h — R$ 0** |

### Pendentes do contrato original — cliente pede inclusao no emergencial

| Item | Descricao | Status na variante C | Obs |
|------|-----------|---------------------|-----|
| #9 | Documentacao do software para colaboradores GitHub | [~] PARCIAL — absorvido por M3 | M3 agora e emergencial (ver abaixo) |
| #7 | Scheduler automatizado com logging | [OK] ENTREGUE | Ja entregue — confirmar com cliente se ha pendencia residual |
| #10 | Validacao cruzada TreeGOER | [~] PARCIAL — TreeGOER OK, BIEN pendente | TreeGOER ja entregue; BIEN adiado para novo contrato |

> **Nota**: #7 (scheduler) ja consta como ENTREGUE na analise. Verificar com cliente se ha algo especifico faltando ou se e so confirmacao.
> **Nota**: #10 TreeGOER esta entregue (48.129 especies). BIEN (M1) foi adiado pelo cliente para novo contrato (baixa prioridade).

### Subidos de "pago" para EMERGENCIAL

| Item | Descricao | Horas | Valor (variante C) |
|------|-----------|-------|-------------------|
| A2 | Fix climate filter para nao-arvores: 42 herbs vs 42.572 no bioma | 16h | R$ 2.133 |
| A6 | Ranking planilhas Practitioners + correcao de conflitos | 16h | R$ 2.133 |
| M2 | WCUPS plant uses — Kew dataset publico, crawler limpo | 12h | R$ 1.600 |
| M3 | Documentacao de metodologia climatica com logging detalhado | 12h | R$ 1.600 |
| **Subtotal** | | **56h** | **R$ 7.466** |

> **DECISAO NECESSARIA**: estes 4 itens eram pagos na variante C. Cliente quer que sejam emergenciais.
> Opcoes: (a) absorver como sem custo, (b) manter pagos mas com prioridade emergencial, (c) negociar.

### Item com duvida do cliente

| Item | Descricao | Horas | Obs |
|------|-----------|-------|-----|
| M5 | i18n cobertura completa: admin panel, labels server-side, Results table | 20h | **Cliente nao entendeu o item** |

> **Esclarecimento necessario para M5**:
> - O sistema de traducao PT/EN (toggle) ja funciona para a maioria da interface
> - M5 completa as **strings faltantes**: colunas da tabela Results que ficam em PT quando muda para EN, labels do painel Admin que sao hardcoded em ingles, textos dinamicos do servidor
> - Nodes Figma com problema: 3538:14142 (tela inicial nao traduz), 3606:4187 (colunas Results)
> - Sem M5, partes da interface permanecem no idioma errado ao usar o toggle

---

## BLOCO 2 — ADIADOS PARA NOVO CONTRATO

### Itens que eram "sem custo absorvido" — adiados (60h)

| Item | Descricao | Horas | Prioridade no novo contrato |
|------|-----------|-------|-----------------------------|
| A7 | Crawler CNCFlora (~9.444 especies) + label "Threat Status (CNC Flora)" | 24h | A definir |
| A8 | Crawler IUCN *(condicional a liberacao pela IUCN)* | 16h | A definir |
| B7 | Web scraping nomes populares adicionais (Switchboard 4.0, etc.) | 20h | A definir |

### Alta prioridade no novo contrato (92h — R$ 12.267)

| Item | Descricao | Horas | Valor |
|------|-----------|-------|-------|
| A5 | Ranking de prioridade por fonte de dados por atributo e por lingua | 20h | R$ 2.667 |
| B1 | Koppen climate map (versao TDWG) com peso maior que ecoregion | 28h | R$ 3.733 |
| B3 | Aprimorar selecao de variaveis Worldclim por grupo funcional | 20h | R$ 2.667 |
| B5 | Versao responsiva mobile (breakpoints, layout condicional Plotly Dash) | 24h | R$ 3.200 |

### Media prioridade no novo contrato (68h — R$ 9.066)

| Item | Descricao | Horas | Valor |
|------|-----------|-------|-------|
| A10 | Ecoregions raster em vez de shape vetorial (precisao + linhas brancas) | 12h | R$ 1.600 |
| B2 | CitiesGOER (Zenodo) — dataset de clima urbano | 16h | R$ 2.133 |
| A9 | Correcoes sistematicas Figma (textboxes + restantes) + jitter sobrepostas | 28h | R$ 3.733 |
| M4 | Simbolos → Detalhes → Tabela-infografico | 12h | R$ 1.600 |

### Baixa prioridade no novo contrato (120h — R$ 16.000)

| Item | Descricao | Horas | Valor |
|------|-----------|-------|-------|
| M1 | Crawler BIEN (R package + API) | 16h | R$ 2.133 |
| M2b | PFAF + Tropical *(condicional a ToS)* | 24h | R$ 3.200 |
| M7 | Nomes populares: WFO API + REFLORA API | 16h | R$ 2.133 |
| M6 | Life cycle (anual/bienal/perene): extrair WCVP, campo + filtro UI | 12h | R$ 1.600 |
| A1 | Imputacao de max_height_m por growth form | 8h | R$ 1.067 |
| B6 | Climate Tab: diagrama icones vegetacao nativa madura por bioma | 20h | R$ 2.667 |
| B8 | Suporte para correcoes pontuais e emergencias ate 31/03/2027 | 24h | R$ 3.200 |

---

## BLOCO 3 — BUG ADICIONAL: Nomes Cientificos Duplicados

### Problema reportado

Especies aparecem em multiplas linhas, uma por cada nome comum diferente:

**Exemplo 1 — Panicum miliaceum (milho-alvo):**
- almindelig hirse · milho-alvo · Panicum miliaceum
- blackseeded proso millet · milho-alvo · Panicum miliaceum
- Black-seed Proso Millet · milho-alvo · Panicum miliaceum
- broomcorn · milho-alvo · Panicum miliaceum
- Broomcorn · milho-alvo · Panicum miliaceum

**Exemplo 2 — Cnidoscolus aconitifolius (chaya):**
- cabbage-star · chaya · Cnidoscolus aconitifolius (76%)
- chaya · Cnidoscolus aconitifolius (76%)
- treadsoftly · chaya · Cnidoscolus aconitifolius (76%)
- Treadsoftly · chaya · Cnidoscolus aconitifolius (76%)
- tree-spinach · chaya · Cnidoscolus aconitifolius (76%)

**Exemplo 3 — Aspidosperma cuspa (guatambuzinho):**
- Bois amer blanc · guatambuzinho · Aspidosperma cuspa (78%)
- Madame Jean · guatambuzinho · Aspidosperma cuspa (78%)

### Analise

Este e o bug **#3 da lista de pendencias** — "Evitar repeticao do nome cientifico por nome popular".

A query ja tem `DISTINCT ON (s.canonical_name)` nas linhas `server_app.py:1034` e `:1065`. Porem:
1. O fix **U1** (INNER → LEFT JOIN) pode alterar o comportamento do DISTINCT ON
2. Os resultados do cliente mostram que a deduplicacao **nao esta funcionando** — possivelmente porque:
   - A query retorna resultados do **discovery** (outra query sem DISTINCT ON)
   - Ou o DISTINCT ON esta sendo anulado por diferenca no nome EN que vem antes na ORDER BY
3. Nomes com casing diferente ("Broomcorn" vs "broomcorn", "Treadsoftly" vs "treadsoftly") sugerem ausencia de `LOWER()` na deduplicacao

### Tratamento proposto

- **Incluir no EMERGENCIAL** junto com U1 (fix INNER JOIN) — mesma area de codigo
- Investigar a query de discovery que retorna resultados com chip "x" (selecionados)
- Garantir que `DISTINCT ON (s.canonical_name)` funciona apos o fix U1
- Adicionar normalizacao de casing nos nomes comuns

---

## RESUMO COMPARATIVO — Variante C vs. Feedback Cliente

| Bloco | Variante C | Feedback cliente |
|-------|-----------|-----------------|
| **Emergencial sem custo** | 108h (U1-U3, A3, A4, A7, A8, M5, B7) | 28h (U1-U3, A3, A4) + bug dedup |
| **Emergencial pago (subidos)** | — | 56h (A2, A6, M2, M3) = R$ 7.466 |
| **M5 i18n** | Sem custo (20h) | Pendente esclarecimento |
| **Adiados (eram sem custo)** | — | 60h (A7, A8, B7) |
| **Novo contrato alta** | — | 92h = R$ 12.267 |
| **Novo contrato media** | — | 68h = R$ 9.066 |
| **Novo contrato baixa** | — | 120h = R$ 16.000 |

### Valor do aditivo atual (conforme feedback)

| Bloco | Horas | Valor |
|-------|-------|-------|
| Emergencial sem custo (U1-U3, A3, A4) | 28h | R$ 0 |
| Emergencial pago (A2, A6, M2, M3) | 56h | R$ 7.466 |
| M5 i18n (pendente decisao) | 20h | R$ 0 ou R$ 2.667 |
| **Total aditivo atual** | **84–104h** | **R$ 7.466 – R$ 10.133** |
| **Novo contrato (total adiado)** | **340h** | **R$ 37.333 + 60h absorvidas** |

---

## PONTOS DE DECISAO PENDENTES

1. **M5 i18n**: esclarecer ao cliente o que e (ver explicacao acima). Incluir no emergencial ou adiar?
2. **4 itens subidos (A2, A6, M2, M3)**: sao pagos (R$ 7.466) ou cliente espera sem custo?
3. **#7 Scheduler**: ja entregue — confirmar se ha pendencia residual
4. **#9 Docs GitHub**: M3 (documentacao) foi subido para emergencial — cobre este item?
5. **#10 TreeGOER**: ja entregue — BIEN (M1) adiado para novo contrato. OK?
6. **Bug dedup (#3)**: incluir formalmente no U1 ou criar item separado?
