import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget


#Second tabs of the dashboard
#help_text are the texts in grey under titles (ui.h4)

FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_updated.csv")

# location = ui.nav_panel("1 Location",
                        
#     ui.page_fluid(ui.layout_sidebar(

#             ui.sidebar(


#                 ui.h4("Floristic group"),
#                 ui.help_text("Choose floristic group you want to consider"),
                
#                 ui.div(ui.input_selectize(
#                     "floristic_group", #changes would impact server_app
#                     "",
#                     choices=["All Species", "Endemic","Native", "Naturalized"],
#                     multiple=False
#                     ),class_="input-selectize"),


#                 ui.h4("Coordinates"),
#                 ui.help_text("Enter the coordinates of where you want to work."),
#                 ui.help_text("By default the coordinates for the main species tabs are the coordinates of UFSC Experimental Farm"),
#                 ui.div(ui.input_text(
#                     "longitude",#changes would impact server_app
#                     "Longitude :",#changes would only impact what we read
#                     '-49'
#                 ),
#                 ui.input_text(
#                     "latitude",#changes would impact server_app
#                     "Latitude :",#changes would only impact what we read
#                     '-27'
#                 )),
#                 ui.div(ui.input_action_button("update_map", #connection with the server_app file
#                                             "Update map" #what appears on the button
#                                             )),


#                 open="always",
#                 width="17%"
#                 ),


#     ui.h3("Botanical Country Map"),
#     ui.div(output_widget("world_map"),class_="map"),),
#     height="4000px"
#     )),
import faicons as fa

# Add main content
ICONS = {
    "hammer": fa.icon_svg("hammer"),
}

location = ui.nav_panel(
    "❶ Location",
    ui.page_fluid(
        # Container for flexbox layout
        ui.div(
            ui.div(
                ui.h4("Copy your Project Coordinates From ",
                    ui.a(
                        "Google Maps", 
                        href="https://www.google.com/maps",  # Link to Google Maps
                        target="_blank",  # Open in a new tab
                        class_="link"  # Add a class for styling if needed
                    ),
                    " or ",
                    ui.a(
                        "OpenStreetMap", 
                        href="https://www.openstreetmap.org",  # Link to OSM
                        target="_blank",  # Open in a new tab
                        class_="link"
                    )),
                ui.div(
                    ui.h5(
                        "🔨 OR enable automatic 'Location' in your web browser OR device OR Zoom & click on your planting project location. 🔨"
                    ),
                    ui.p(
                        "Your climate & biome will then be returned automatically to filter adapted species on following pages."
                    ),
                ),
                class_="left-section",
            ),
            ui.div(
                # Coordinates Input and Update Map Button in a Flexbox
                ui.div(
                    ui.input_text(
                        "longitude_latitude",  # Changes would impact server_app
                        "Paste your coordinates:",  # Label
                    ),
                    ui.input_action_button(
                        "update_map",  # Connection with server_app
                        "Send ➔",  # Button label
                    ),
                    class_="coordinates-container",  # Flexbox container class
                ),
                ui.div(
                    ui.help_text("OR")),
                ui.input_action_button(
                    "current_location",  # Connection with server_app
                    "🔨 Enable Current Location 🔨",  # Button label
                    class_="red-button",
                ),
                ui.div(
                    ui.p(""),
                    ui.help_text("For this region display"),
                    ui.input_selectize(
                        "floristic_group",  # Changes would impact server_app
                        "",
                        choices=["All Species", "Endemic", "Native", "Naturalized"],
                        multiple=False,
                    ),
                ),
                class_="right-section",
            ),
            class_="flex-container",  # Flexbox container
        ),
        # Map Section Below
        ui.div(
            ui.output_ui("world_map"), class_="map"),
        ),
    ),
