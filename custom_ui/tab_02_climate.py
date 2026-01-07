import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget
from shiny import ui, render, reactive

climate = ui.nav_panel(
    ui.div(
        ui.span("2", class_="badge bg-secondary rounded-circle me-2"),
        ui.span("Climate"),
        class_="d-flex align-items-center"
    ),
    ui.page_fluid(
        ui.h1("Climate", class_="text-center mb-4"),
        ui.div(
            ui.output_image("climate_image", height="600px",width="100%"),
            class_="climate-image-container"
        )
    )
)