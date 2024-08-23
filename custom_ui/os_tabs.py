import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants,get_Function


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")

other_species = ui.nav_panel("Other Species",
                          
    ui.page_fluid(ui.page_fluid(

        
            # ui.sidebar(
            #     ui.h3("Filter"),
            #     ui.help_text("Choose specific criteria for the species you want to be suggested"),
            #     ui.h5("Country"),
            #     ui.div(ui.input_selectize(
            #         "filter_country_sgg",
            #         "",
            #         choices=["France","Brasil","Canada"],
            #         multiple=True
            #         ),class_="input-selectize"),
            #     ui.h5("Function"),
            #     ui.div(ui.input_selectize(
            #                         "filter_function_sgg",
            #                         "",
            #                         choices=get_Function(FILE_NAME),
            #                         multiple=True
            #                         ),class_="input-selectize"),


            #     ui.div(ui.output_ui("text"))),
            #     # ui.h3("Growth Form"),
            #     # ui.help_text("After seeing the suggestions, choose the species to add"),
                
                ui.div(ui.output_ui(
                    "suggestion_plants",
                    ),class_="input-selectize"),

                open="always",
                width="17%"
                ),
        
        
        ui.div(ui.output_ui("suggestion"))))