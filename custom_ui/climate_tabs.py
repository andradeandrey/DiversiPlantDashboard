import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")

#Third tab, needs changes to make it work and impactful on the dashboard


climate = ui.nav_panel("Climate",
                       
    ui.page_fluid(ui.layout_sidebar(

            ui.sidebar(


                ui.h4("Climate"),
                ui.p(ui.help_text("Choose your climate type"),
                ui.tooltip(
                    ui.help_text(".  (Help)"),
                    """The location and climate you selected indicate the following growth forms predominant in 
                    the potential vegetation supported by the current local climate. However, if your location is in 
                    the mountains, valley or in (seasonally) waterlogged soils, your potential vegetation might 
                    differ strongly from the suggested composition of growth forms.",
                    placement="right""",
                )),
                ui.div(ui.input_selectize(
                    "climate_type",
                    "",
                    choices=[
                                "",
                                "Continental ",
                                "Dry ",
                                "Highland ",
                                "Polar ",
                                "Temperate ",
                                "Tropical Rainy "
                            ],
                    multiple=False
                    ),class_="input-selectize"),


                ui.h4("Biome"),
                ui.help_text("Choose your biome type."),
                ui.div(ui.input_selectize("biome_type",
                              "",
                              choices=[
                                        "",
                                        "Boreal Forest (Taiga)",
                                        "Desert",
                                        "Mountain (Alpine)"
                                        "Temperate Rainforest",
                                        "Temperate Deciduous Forest",
                                        "Temperate Grassland",
                                        "Tropical Rainforest",
                                        "Tropical Grassland (Savanna)",
                                        "Tundra",
                                    ],
                              multiple=False
                              ),class_="input-selectize"),

                              
                open="always",
                width="17%"
                ),

    ui.h3("Botanical Country Graph"),
    ui.div(output_widget("biome_graph"),class_="map"),),
    height="4000px"))
    