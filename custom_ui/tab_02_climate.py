"""Climate / Clima tab — matches Figma design with ecoregion map."""
import os
from shiny import ui, App
from pathlib import Path
from shinywidgets import output_widget
from shiny import ui, render, reactive
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

# Climate types mapping to Koppen classification
CLIMATE_TYPES = {
    "Continental": "Continental",
    "Polar": "Polar",
    "Temperate": "Temperate",
    "Dry": "Dry",
    "Highland": "Highland",
    "Tropical Rainy": "Tropical Rainy"
}

# Biome types mapping to WWF biome numbers
BIOME_TYPES = {
    "Boreal Forest (Taiga)": "Boreal Forest (Taiga)",
    "Deserts & Xeric Shrublands": "Deserts & Xeric Shrublands",
    "Mangroves": "Mangroves",
    "Mediterranean Forests, Woodlands & Scrub": "Mediterranean Forests, Woodlands & Scrub",
    "Montane Grasslands & Shrublands": "Montane Grasslands & Shrublands",
    "Rock and Ice": "Rock and Ice",
    "Temperate Broadleaf & Mixed Forests": "Temperate Broadleaf & Mixed Forests",
    "Temperate Conifer Forests": "Temperate Conifer Forests",
    "Tropical & Subtropical Moist Broadleaf Forests": "Tropical & Subtropical Moist Broadleaf Forests",
    "Tropical & Subtropical Dry Broadleaf Forests": "Tropical & Subtropical Dry Broadleaf Forests",
    "Tropical & Subtropical Grasslands, Savannas & Shrublands": "Tropical & Subtropical Grasslands, Savannas & Shrublands",
    "Temperate Grasslands, Savannas & Shrublands": "Temperate Grasslands, Savannas & Shrublands",
}

climate = ui.nav_panel(
    tab_title(2, "Clima", "Climate"),
    ui.page_fluid(
        # Title matching Figma
        ui.div(
            ui.h4(
                t(
                    "Clima e bioma sincronizados com a localização",
                    "Climate and biome synced with location",
                ),
            ),
            ui.p(
                t(
                    "Espécies adequadas ao seu clima local. Se você ativar a localização ou selecionar "
                    "um país botânico na aba de localização, esta etapa será preenchida automaticamente. "
                    "Você também pode selecionar tipos de clima ou bioma abaixo.",
                    "Species suited to your local climate. If you enable the use of your current location "
                    "or select a botanical country in the location tab, this step will be automatically "
                    "completed. You may also select climate or biome types below.",
                ),
                class_="text-muted",
            ),
            class_="climate-explanation",
        ),

        # Ecoregion map + climate/biome pills (Figma layout: map left, pills right)
        ui.div(
            # Left: ecoregion map
            ui.div(
                ui.output_ui("ecoregion_map"),
                class_="ecoregion-map-col",
                style="flex: 2; min-width: 300px;",
            ),
            # Right: detected info + manual selection
            ui.div(
                ui.p(
                    t(
                        "Você pode explorar! Navegue manualmente neste mapa para conferir "
                        "os diferentes biomas e ecoregiões.",
                        "You can explore! Navigate manually on this map to check "
                        "the different biomes and ecoregions.",
                    ),
                    class_="text-muted",
                    style="font-size: 0.9em;",
                ),
                # Detected ecoregion info (auto-filled from coordinates)
                ui.output_ui("ecoregion_info"),

                # Climate Types
                ui.h5(
                    t("Clima para a região selecionada", "Climate for selected region"),
                    class_="mt-3",
                ),
                ui.input_checkbox_group(
                    "climate_types",
                    None,
                    choices=CLIMATE_TYPES,
                    inline=True,
                ),
                # Biome Types
                ui.h5(t("Bioma para a região selecionada", "Biome for selected region")),
                ui.input_checkbox_group(
                    "biome_types",
                    None,
                    choices=BIOME_TYPES,
                    inline=True,
                ),
                class_="ecoregion-info-col",
                style="flex: 1; min-width: 280px; padding-left: 20px;",
            ),
            style="display: flex; gap: 16px; flex-wrap: wrap;",
        ),

        # Whittaker Diagram Section
        ui.div(
            ui.h4(
                t("Diagrama de Biomas de Whittaker", "Whittaker Biomes Diagram"),
                class_="text-center",
            ),
            ui.p(
                t(
                    "Clique em uma região de bioma no diagrama para selecioná-la. "
                    "O diagrama mostra a relação entre temperatura média anual e precipitação.",
                    "Click on a biome region in the diagram to select it. "
                    "The diagram shows the relationship between mean annual temperature and precipitation.",
                ),
                class_="text-center text-muted",
            ),
            output_widget("whittaker_diagram"),
            class_="whittaker-container",
        ),

        nav_buttons(back_value="tab_location", next_value="tab_species"),
    ),
    value="tab_climate",
)
