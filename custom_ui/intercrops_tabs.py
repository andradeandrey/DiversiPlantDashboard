import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants, get_Function, get_Country


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")

intercrops = ui.nav_panel(
    "Intercrops",
    ui.page_fluid(ui.layout_sidebar(
            ui.sidebar(
                ui.h3("Filter"),
                ui.help_text("Reduce the number of species before selecting them"),
                ui.h5("Country"),
                ui.div(ui.input_selectize(
                    "overview_country",
                    "",
                    choices=["France","Brasil","Canada"],
                    multiple=True
                    ),class_="input-selectize"),
                ui.h5("Function"),
                ui.div(ui.input_selectize(
                                    "overview_function",
                                    "",
                                    choices=get_Function(FILE_NAME),
                                    multiple=True
                                    ),class_="input-selectize"),
                ui.h3("Growth Form"),
                ui.help_text("Select the plant you want to analyze"),
                
                ui.div(ui.input_selectize(
                    "overview_plants",
                    "",
                    choices=get_Plants(FILE_NAME),
                    multiple=True
                    ),class_="input-selectize"),
                ui.h3("Parameters"),
                ui.help_text("Modify some parameters of the graph"),
                ui.h5("Stratum"),
                ui.help_text("Select the number of stratum division you want"),
                ui.div(ui.input_slider("number_of_division","",min=2,max=8,value=8)),
                open="always",
                width="17%"
                ),

    ui.div(output_widget("intercrops")),
    ui.div(ui.output_ui("card_wrong_plant"))),
    height="2000px"),
    )