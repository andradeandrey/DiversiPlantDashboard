import os
from shiny import ui,App
from pathlib import Path
from shinywidgets import output_widget
import faicons as fa

#Second tabs of the dashboard
#help_text are the texts in grey under titles (ui.h4)

FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_updated.csv")
# Add main content
ICONS = {
    "hammer": fa.icon_svg("hammer"),
}

# location = ui.nav_panel(
#     "❶ Location (GIFT Database)",
#     ui.page_fluid(
#         # Container for flexbox layout
#         ui.div(
#             ui.div(
#                 ui.h4("Copy your Project Coordinates from ",
#                     ui.a(
#                         "Google Maps", 
#                         href="https://www.google.com/maps",  # Link to Google Maps
#                         target="_blank",  # Open in a new tab
#                         class_="link"  # Add a class for styling if needed
#                     ),
#                     " or ",
#                     ui.a(
#                         "OpenStreetMap", 
#                         href="https://www.openstreetmap.org",  # Link to OSM
#                         target="_blank",  # Open in a new tab
#                         class_="link"
#                     )),
#                 ui.div(
#                     ui.h5(
#                         "🔨 OR enable automatic 'Location' in your web browser OR device OR Zoom & click on your planting project location. 🔨"
#                     ),
#                     ui.p(
#                         "Your climate & biome will then be returned automatically to filter adapted species on following pages."
#                     ),
#                 ),
#                 class_="left-section",
#             ),
#             ui.div(
#                 # Coordinates Input and Update Map Button in a Flexbox
#                 ui.div(
#                     ui.input_text(
#                         "longitude_latitude",  # Changes would impact server_app
#                         "Paste your coordinates:",  # Label
#                     ),
#                     ui.input_action_button(
#                         "update_map",  # Connection with server_app
#                         "Send ➔",  # Button label
#                     ),
#                     class_="coordinates-container",  # Flexbox container class
#                 ),
#                 ui.div(
#                     ui.help_text("OR")),
#                 ui.input_action_button(
#                     "current_location",
#                     "🚧 Current Location 🚧",
#                     # class_="btn-warning",  # Adding a warning color class
#                     disabled=True  # Disable the button to indicate it's not functional
#                 ),
#                 ui.p("The feature above is currently unavailable."),
#                 ui.div(
#                     ui.p(""),
#                     ui.help_text("For this region display"),
#                     ui.input_selectize(
#                         "floristic_group",  # Changes would impact server_app
#                         "",
#                         choices=["All Species", "Endemic", "Native", "Naturalized"],
#                         multiple=False,
#                     ),
#                 ),
#                 class_="right-section",
#             ),
#             class_="flex-container",  # Flexbox container
#         ),
#         # Map Section Below
#         ui.div(
#             ui.output_ui("world_map"), class_="map"),
#         ),
#     ),

location = ui.nav_panel(
    # Replace the existing header with a div containing the badge and text
    ui.div(
        ui.span("1", class_="badge bg-secondary rounded-circle me-2"),
        ui.span("Location (GIFT Database)"),
        class_="d-flex align-items-center"
    ),
    
    ui.page_fluid(
        # Container for flexbox layout
        ui.div(
            ui.div(
                ui.h4("Copy your Project Coordinates from ",
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
                    "current_location",
                    "🚧 Current Location 🚧",
                    # class_="btn-warning",  # Adding a warning color class
                    disabled=True  # Disable the button to indicate it's not functional
                ),
                ui.p("The feature above is currently unavailable."),
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