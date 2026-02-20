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
