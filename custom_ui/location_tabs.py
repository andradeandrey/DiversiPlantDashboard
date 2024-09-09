import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget


#Second tabs of the dashboard
#help_text are the texts in grey under titles (ui.h4)

FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_updated.csv")

location = ui.nav_panel("Location",
                        
    ui.page_fluid(ui.layout_sidebar(

            ui.sidebar(


                ui.h4("Floristic group"),
                ui.help_text("Choose floristic group you want to consider"),
                
                ui.div(ui.input_selectize(
                    "floristic_group", #changes would impact server_app
                    "",
                    choices=["All Species", "Endemic","Native", "Naturalized"],
                    multiple=False
                    ),class_="input-selectize"),


                ui.h4("Coordinates"),
                ui.help_text("Enter the coordinates of where you want to work."),
                ui.help_text("By default the coordinates for the main species tabs are the coordinates of UFSC Experimental Farm"),
                ui.div(ui.input_text(
                    "longitude",#changes would impact server_app
                    "Longitude :",#changes would only impact what we read
                    '-49'
                ),
                ui.input_text(
                    "latitude",#changes would impact server_app
                    "Latitude :",#changes would only impact what we read
                    '-27'
                )),
                ui.div(ui.input_action_button("update_map", #connection with the server_app file
                                              "Update map" #what appears on the button
                                              )),


                open="always",
                width="17%"
                ),


    ui.h3("Botanical Country Map"),
    ui.div(output_widget("world_map"),class_="map"),),
    height="4000px"))
    