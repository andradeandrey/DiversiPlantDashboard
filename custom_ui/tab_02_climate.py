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
        # Title bar — centered, bold title + muted subtitle inline
        ui.div(
            ui.span(
                t(
                    "Clima e bioma sincronizados com a localização",
                    "Climate and biome synced with location",
                ),
                class_="climate-title",
            ),
            ui.span(
                t(
                    "Espécies adequadas ao seu clima local",
                    "Species suited to your local climate",
                ),
                class_="climate-subtitle",
            ),
            class_="climate-header",
        ),

        # Main content: map (left) + diagram & form (right)
        ui.div(
            # Left: ecoregion map only
            ui.div(
                ui.output_ui("ecoregion_map"),
                ui.output_ui("ecoregion_info"),
                class_="climate-map-col",
            ),
            # Right: Whittaker diagram + climate/biome controls
            ui.div(
                ui.h6(
                    t("Diagrama de Biomas de Whittaker", "Whittaker Biomes Diagram"),
                    style="font-weight: 600; margin-bottom: 4px;",
                ),
                ui.p(
                    t(
                        "Clique em uma região de bioma no diagrama para selecioná-la.",
                        "Click on a biome region in the diagram to select it.",
                    ),
                    class_="text-muted",
                    style="font-size: 13px; margin-bottom: 8px;",
                ),
                output_widget("whittaker_diagram"),
                # Climate Types
                ui.h6(
                    t("Clima", "Climate"),
                    class_="mt-3",
                    style="font-weight: 600;",
                ),
                ui.input_checkbox_group(
                    "climate_types",
                    None,
                    choices=CLIMATE_TYPES,
                    inline=True,
                ),
                # Biome Types
                ui.h6(
                    t("Bioma", "Biome"),
                    style="font-weight: 600; margin-top: 12px;",
                ),
                ui.input_checkbox_group(
                    "biome_types",
                    None,
                    choices=BIOME_TYPES,
                    inline=True,
                ),
                class_="climate-right-col",
            ),
            class_="climate-main-row",
        ),

        # Floating nav buttons footer
        nav_buttons(back_value="tab_location", next_value="tab_species"),
        style="position: relative; padding-bottom: 70px;",
    ),
    value="tab_climate",
)
