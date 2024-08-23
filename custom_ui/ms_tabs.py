import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants, get_Function, get_Country


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")

main_species = ui.nav_panel("Main Species",
    ui.page_fluid(ui.layout_sidebar(

            ui.sidebar(

                ui.h3("Datasource"),
                ui.div(ui.input_selectize(
                    "database_choice",
                    "",
                    choices=["Normal Database", "GIFT Database"],
                    multiple=False
                    ),class_="input-selectize"),
                ui.div(ui.input_action_button("update_database", "Update choices")),


                ui.h3("Growth Form"),
                ui.p(ui.help_text("Add plants that are important for your planting project. "),
                ui.tooltip(
                    ui.help_text("(Help)"),
                    """Type main species you want to use. \n
                    If 2 species you selected are not compatible, they will be flagged. You might still combine them, but would probably need to reduce the density of each. 
                    Next tabs will suggest companion plants likely to be compatible.""",
                    placement="right",
                )),
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
                ui.div(ui.input_slider("number_of_division","",min=2,max=9,value=9)),


                ui.div(ui.download_button("export_df","Export chosen data")),

                open="always",
                width="17%"

                ),


    ui.div(output_widget("intercrops")),
    ui.div(ui.output_ui("compatibility")),
    #ui.div(ui.output_ui("card_wrong_plant"))),
    height="2000px"),
    ))