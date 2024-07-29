import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants, get_Function, get_Country
import geopandas as gpd

world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
countries=world['name'].tolist()
countries.sort()
FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")

location = ui.nav_panel(
    "Location",
    ui.page_fluid(ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Floristic group"),
                ui.help_text("Choose floristic group you want to consider"),
                
                ui.div(ui.input_selectize(
                    "floristic_group",
                    "",
                    choices=["","Native", "Endemic", "Naturalized",  "All Species"],
                    multiple=False
                    ),class_="input-selectize"),
                ui.h4("Botanical region"),
                ui.help_text("After checking the map, choose your botanical region"),
                ui.div(ui.input_selectize("choose_location",
                              "",
                              choices=[""]+countries,
                              multiple=False
                              ),class_="input-selectize"),
                open="always",
                width="17%"
                ),
    ui.h3("Botanical Country Map"),
    ui.div(output_widget("world_map"),class_="map"),),
    height="4000px"))
    