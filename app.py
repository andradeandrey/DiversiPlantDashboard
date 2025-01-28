from pathlib import Path
from shiny import ui, App
import os

from custom_ui.details_tabs import details
from custom_ui.homepage_tabs import homepage
from custom_ui.os_tabs import other_species
from custom_ui.location_tabs import location
from custom_ui.climate_tabs import climate
from custom_ui.ms_tabs import main_species

from custom_server.server_app import server_app

css_file = os.path.join(Path(__file__).parent,"data","ui.css")

app_ui=ui.page_fluid(
    ui.include_css(css_file),
    ui.page_navbar(
    homepage,
    location,
    climate,
    main_species,
    details,
    other_species,
    title=ui.div("Agroforestry Dashboard", class_="title"),
    )
)


static_dir = Path(__file__).parent / "data"
app = App(app_ui, server_app, static_assets=static_dir)
