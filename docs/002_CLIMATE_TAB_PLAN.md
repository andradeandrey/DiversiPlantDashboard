# Tarefa 002: Climate Tab - Seleção de Clima e Bioma

**Data**: 2026-01-08
**Status**: Concluída

## Objetivo
Implementar a funcionalidade da aba Climate conforme a imagem de referência, permitindo seleção de tipos de clima e bioma com diagrama Whittaker interativo.

---

## Componentes Implementados

### 1. Texto Explicativo
```
If you enable the use of your current location or select a botanical country
in the location tab, this step will be automatically completed. You may also
only select one or more climate type or biome types below for which you are
planning your mixed-species planting, without needing to specify an exact
location. The next steps will show only species adapted to this climate & biome.
```

### 2. Seleção de Climate Types (chips/badges clicáveis)
- Continental
- Polar
- Temperate
- Dry
- Highland
- Tropical Rainy

### 3. Seleção de Biome Types (chips/badges clicáveis)
- Boreal Forest (Taiga)
- Deserts & Xeric Shrublands
- Mangroves
- Mediterranean Forests, Woodlands & Scrub
- Montane Grasslands & Shrublands
- Rock and Ice
- Temperate Broadleaf & Mixed Forests
- Temperate Conifer Forests
- Tropical & Subtropical Moist Broadleaf Forests
- Tropical & Subtropical Dry Broadleaf Forests
- Tropical & Subtropical Grasslands, Savannas & Shrublands
- Temperate Grasslands, Savannas & Shrublands

### 4. Diagrama de Whittaker (Plotly Interativo)
- Gráfico Temperature (°C) vs Precipitation (cm)
- Áreas coloridas por bioma usando Plotly filled polygons
- Legenda lateral interativa
- Hover com informações do bioma

---

## Arquivos Modificados

### `custom_ui/tab_02_climate.py`
- Layout com flexbox (Climate | Biome lado a lado)
- Chips selecionáveis usando `ui.input_checkbox_group`
- Diagrama Whittaker via `output_widget` (Plotly)

### `custom_server/server_app.py`
- Função `whittaker_diagram()` com Plotly usando polígonos preenchidos
- 9 biomas representados com cores distintas

### `data/ui.css`
- Estilos para chips como badges arredondados
- Classes: `.climate-explanation`, `.climate-biome-container`, `.climate-column`, `.biome-column`
- Estilos para checkboxes como chips com `:has()` selector
- Cores específicas por tipo de clima quando selecionado

---

## Dados de Mapeamento

### Climate → Köppen Classification
| UI Label | Köppen Codes |
|----------|--------------|
| Continental | Dfa, Dfb, Dfc, Dfd, Dwa, Dwb, Dwc, Dwd |
| Polar | ET, EF |
| Temperate | Cfa, Cfb, Cfc, Csa, Csb, Cwa, Cwb |
| Dry | BWh, BWk, BSh, BSk |
| Highland | H (variável por altitude) |
| Tropical Rainy | Af, Am, Aw |

### Biome → WWF Biome Numbers
| UI Label | WWF Biome |
|----------|-----------|
| Boreal Forest (Taiga) | 6 |
| Deserts & Xeric Shrublands | 13 |
| Mangroves | 14 |
| Mediterranean Forests | 12 |
| Montane Grasslands | 10 |
| Rock and Ice | 15 |
| Temperate Broadleaf | 4 |
| Temperate Conifer | 5 |

---

## Whittaker Biomes - Coordenadas do Diagrama

| Biome | Temp Min (°C) | Temp Max (°C) | Precip Min (cm) | Precip Max (cm) | Cor |
|-------|---------------|---------------|-----------------|-----------------|-----|
| Tundra | -15 | 5 | 0 | 50 | #B8E0E0 |
| Boreal Forest | -10 | 5 | 30 | 150 | #A8D5A2 |
| Temperate Seasonal Forest | 0 | 20 | 75 | 200 | #6B8E5A |
| Temperate Rain Forest | 5 | 20 | 200 | 450 | #2E7D4A |
| Tropical Rain Forest | 20 | 30 | 200 | 450 | #1B5E3B |
| Tropical Seasonal Forest | 20 | 30 | 100 | 200 | #8BA870 |
| Subtropical Desert | 15 | 30 | 0 | 30 | #E8D4A0 |
| Temperate Grassland/Desert | 0 | 20 | 0 | 75 | #F5E6B8 |
| Woodland/Shrubland | 10 | 25 | 30 | 100 | #C17F59 |

---

## Implementação

### Código UI (`tab_02_climate.py`)
```python
climate = ui.nav_panel(
    ui.div(
        ui.span("2", class_="badge bg-secondary rounded-circle me-2"),
        ui.span("Climate"),
        class_="d-flex align-items-center"
    ),
    ui.page_fluid(
        # Texto explicativo
        ui.div(ui.p("If you enable..."), class_="climate-explanation"),

        # Container flex para Climate e Biome
        ui.div(
            ui.div(
                ui.h4("Climate Types"),
                ui.input_checkbox_group("climate_types", None, choices=CLIMATE_TYPES, inline=True),
                class_="climate-column"
            ),
            ui.div(
                ui.h4("Biome Types"),
                ui.input_checkbox_group("biome_types", None, choices=BIOME_TYPES, inline=True),
                class_="biome-column"
            ),
            class_="climate-biome-container"
        ),

        # Diagrama Whittaker
        ui.div(
            ui.h4("Whittaker Biomes Diagram", class_="text-center"),
            output_widget("whittaker_diagram"),
            class_="whittaker-container"
        )
    )
)
```

### Código Server (`server_app.py`)
```python
@render_widget
def whittaker_diagram():
    biomes = [
        {"name": "Tropical Rain Forest", "color": "#1B5E3B", ...},
        # ... mais biomas
    ]
    fig = go.Figure()
    for biome in biomes:
        fig.add_trace(go.Scatter(
            x=biome["temp"], y=biome["precip"],
            fill="toself", fillcolor=biome["color"],
            name=biome["name"], mode="lines"
        ))
    return fig
```

---

## Critérios de Sucesso

- [x] Texto explicativo visível no topo
- [x] Chips de Climate selecionáveis (multi-select)
- [x] Chips de Biome selecionáveis (multi-select)
- [x] Visual similar à imagem de referência
- [x] Diagrama Whittaker interativo com Plotly
- [x] Hover mostra nome do bioma
- [ ] Seleção persiste entre tabs (pendente integração com Location)
