import os
from shiny import ui, App
from pathlib import Path
from shinywidgets import output_widget
from shiny import ui, render, reactive

# Climate types mapping to Köppen classification
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
    ui.div(
        ui.span("2", class_="badge bg-secondary rounded-circle me-2"),
        ui.span("Climate"),
        class_="d-flex align-items-center"
    ),
    ui.page_fluid(
        # Explanatory text at top
        ui.div(
            ui.p(
                "If you enable the use of your current location or select a botanical country "
                "in the location tab, this step will be automatically completed. You may also "
                "only select one or more climate type or biome types below for which you are "
                "planning your mixed-species planting, without needing to specify an exact "
                "location. The next steps will show only species adapted to this climate & biome."
            ),
            class_="climate-explanation"
        ),

        # Container for Climate and Biome selection side by side
        ui.div(
            # Climate Types Column
            ui.div(
                ui.h4("Climate Types"),
                ui.input_checkbox_group(
                    "climate_types",
                    None,
                    choices=CLIMATE_TYPES,
                    inline=True
                ),
                class_="climate-column"
            ),
            # Biome Types Column
            ui.div(
                ui.h4("Biome Types"),
                ui.input_checkbox_group(
                    "biome_types",
                    None,
                    choices=BIOME_TYPES,
                    inline=True
                ),
                class_="biome-column"
            ),
            class_="climate-biome-container"
        ),

        # Whittaker Diagram Section
        ui.div(
            ui.h4("Whittaker Biomes Diagram", class_="text-center"),
            ui.p(
                "Click on a biome region in the diagram to select it. "
                "The diagram shows the relationship between mean annual temperature and precipitation.",
                class_="text-center text-muted"
            ),
            output_widget("whittaker_diagram"),
            class_="whittaker-container"
        )
    )
)
