# ~~Ajustes Pendentes~~ Ajustes Aplicados — Tela Inicial

## Feedback do Cliente (Figma nó 3584:35)

> "A tela tem de estar em um zoom de 80% para aparecer os logos, não aparece barra de rolagem."

### Problema

Em zoom 100% (especialmente laptops 1366×768), o conteúdo da tela inicial transborda e os logos dos patrocinadores ficam cortados. O `overflow: hidden` no CSS esconde o scroll mas também corta o conteúdo. Só funciona corretamente a 80% de zoom.

Causa raiz: `padding-top: 150px` fixo na coluna esquerda consome muito do viewport vertical.

### Análise de Espaço (viewport 768px → ~650px útil)

| Item | Valor atual | Pixels |
|------|------------|--------|
| padding-top | 150px | 150 |
| h2 título | 24px × ~2 linhas | ~65 |
| p subtítulo | 15px × ~2 linhas + margin 24px | ~50 |
| 4 bullets (gap 14px) | 14px font × 2 linhas cada | ~240 |
| botão | margin-top 32px + padding | ~68 |
| logos patrocinadores | padding-bottom 30px + imagem | ~110 |
| **Total** | | **~683px** |

683px > 650px disponível = **estoura!**

A 80% zoom: 768/0.8 = 960px → cabe.

### Correção Planejada

**`custom_ui/tab_00_start.py`:**
- Linha 219: `padding: 150px 50px 0` → `padding: max(60px, 8vh) 50px 0`
- Linha 53: `margin-bottom: 24px` → `margin-bottom: 16px`
- Linha 117: `margin-top: 32px` → `margin-top: 20px`

**`data/ui.css`:**
- `.welcome-bullets-container` gap: `14px` → `10px`
- `.welcome-bullet` font-size: `14px` → `13px`
- `.btn-comecar` padding: `12px 32px` → `10px 28px`
- `.sponsor-logos` padding-bottom: `30px` → `20px`

### Economia estimada: ~156px

Novo total: ~527px → cabe em 650px com folga.

### Status: APLICADO (2026-02-20)

---

## Rótulos no Mapa da Aba Localização

### Problema

O mapa na aba de localização usava Google Satellite (`lyrs=s`) sem rótulos de países, estados ou cidades, dificultando a navegação do usuário até o local do seu projeto. Também não havia controle de camadas para alternar entre estilos de mapa.

### Correção Aplicada

**`custom_server/server_app.py`:**
- Adicionado layer **Google Maps** (`lyrs=m`) como padrão — mostra nomes de países, estados e cidades
- Satellite mudou de `lyrs=s` para `lyrs=y` (hybrid com rótulos)
- Adicionado **LayerControl** para alternar entre Google Maps / OpenStreetMap / Satellite
- OpenStreetMap mantido como opção alternativa

### Status: APLICADO (2026-02-20)

---

## Reestruturação da Aba Clima

### Problema

A aba Clima exibia informações genéricas no título, incluía uma seção desnecessária de "Climate Types" (Continental, Polar, Temperate, Dry, Highland, Tropical Rainy) e o diagrama de Whittaker aparecia no topo, tirando foco da seleção de bioma.

### Correções Aplicadas

**`custom_ui/tab_02_climate.py`:**
- Título estático substituído por `output_ui("climate_context_info")` — mensagem dinâmica com nome da ecorregião e bioma detectados na localização do usuário
- Removida seção inteira de **Climate Types** (dict `CLIMATE_TYPES` + checkbox group `climate_types`)
- Adicionado texto orientativo (PT/EN) antes dos checkboxes de bioma, explicando como corrigir bioma incorreto ou selecionar biomas adicionais em zonas de transição
- **Whittaker diagram + legenda movidos para o fundo** da tela, abaixo dos biomas, com título "OPCIONAL" e separador visual

**`custom_server/server_app.py`:**
- Adicionado render `climate_context_info()` — exibe dinamicamente: "Seu projeto está localizado na ecorregião {eco_name}. Esta ecorregião faz parte do bioma global {biome_name}..." com fallbacks para coordenadas ausentes/inválidas
- Removida dependência de `input.climate_types()` do diagrama de Whittaker (checkboxes de clima não existem mais)

### Status: APLICADO (2026-02-20)

---

## Ajustes na Aba Espécies

### Alterações

**`custom_ui/tab_03_species.py`:**
- Label de busca alterado de "Search:" para **"Type plant names you want to include:"** (PT: "Digite nomes de plantas que deseja incluir:")
- Adicionado título **"Apply filters to limit search results:"** (PT: "Aplique filtros para limitar os resultados:") acima dos filtros
- Adicionado dropdown **"Origin"** (Origem) entre "Plant use" e "Conservation threat" com opções: All, Native, Endemic — filtra por país botânico WCVP (TDWG) da localização do usuário, sem botão "Todos"

**`custom_server/server_app.py`:**
- Lê `input.filter_origin()` e resolve código TDWG via `get_tdwg_by_coords`
- JOIN em `species_regions` com condições `is_native = TRUE` ou `is_endemic = TRUE` conforme seleção
- Ambas variantes da query (com e sem climate scoring) incluem o origin join
- Removidos todos os botões "Todos" dos filtros selectize
- Espaçamento entre label "Aplique filtros..." e input de busca reduzido
- Dropdown "Origem" estilizado com label no padrão `species-filter-label` e altura 38px
- Classe `species-filter-multi` restaurada nos selectize para manter estilo correto

### Status: APLICADO (2026-02-20)

---

## Ajustes no EChart (Gráfico de Nichos Ecológicos)

### Alterações

**`custom_server/server_app.py`:**
- Título dinâmico "Mostrando...sem ambos" substituído por subtítulo estático: **"Choose compatible species to fill vacant ecological niches along succession"**
- Ícone de brush (retângulo azul) movido para abaixo do subtítulo com rótulo permanente: **"Select+drag white (vacant) area"**
- Hover do brush alterado de "Selecionar setor" para: "Selected rectangle will return suitable species to fill each vacant stratum and period."
- **Removida legenda de growth forms** (duplicava a legenda "Símbolos" já existente)
- **Removidos todos os avisos ⚠️** (anotações com ponto de exclamação)
- Eixo Y rotulado: **"Light demand (Stratum)"**
- Valores negativos de Y exibem **"Unknown"** em vez de vazio
- Valores negativos de X exibem **"Unknown"** em vez de vazio
- Texto overlay "Clique para conhecer espécies novas!" substituído por: **"Click to list below species with selected strata & harvest periods"**
- `grid.top` reduzido de 110 para 60 (espaço liberado pela remoção da legenda)

### Status: APLICADO (2026-02-20)

---

## Simplificação do Modal "Simplify"

### Alteração

**`custom_ui/tab_03_species.py`:**
- Removido slider **"Nº de períodos de colheita feito"** (`harvest_bins`) — funcionalidade substituída pelo retângulo de seleção Select+Drag do brush
- Mantido apenas **"Nº de categorias de Estrato"** (radio buttons 2–9)

**`custom_server/server_app.py`:**
- Adicionado fallback `try/except` para `input.harvest_bins()` com valor padrão 4, evitando erro quando o input não existe mais

### Status: APLICADO (2026-02-20)
