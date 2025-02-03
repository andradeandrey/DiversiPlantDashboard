import os
from shiny import ui, App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants


FILE_NAME = os.path.join(
    Path(__file__).parent.parent, "data", "MgmtTraitData_updated.csv"
)

# main_species = ui.nav_panel(
#     "❸ Main Species",
#     ui.page_fluid(
#         ui.layout_sidebar(
#             ui.sidebar(
#                 # ui.h3("Datasource"),
#                 # ui.div(
#                 #     ui.input_selectize(
#                 #         "database_choice",
#                 #         "",
#                 #         choices=["Normal Database", "GIFT Database"],
#                 #         multiple=False,
#                 #     ),
#                 #     class_="input-selectize",
#                 # ),
#                 # ui.div(ui.input_action_button("update_database", "Update choices")),
#                 ui.h3("Main Species"),
#                 ui.p(
#                     ui.help_text(
#                         "Add plants that are important for your planting project. "
#                     ),
#                     ui.tooltip(
#                         ui.help_text("(Help)"),
#                         """Type main species you want to use. \n
#                     If 2 species you selected are not compatible, they will be flagged. You might still combine them, but would probably need to reduce the density of each. 
#                     Next tabs will suggest companion plants likely to be compatible.""",
#                         placement="right",
#                     ),
#                 ),
#                 ui.div(
#                     ui.input_selectize(
#                         "overview_plants",
#                         "",
#                         choices=get_Plants(FILE_NAME),
#                         multiple=True,
#                     ),
#                     class_="input-selectize",
#                 ),
#                 ui.h3("Parameters"),
#                 ui.help_text("Modify some parameters of the graph"),
#                 ui.h5("Stratum"),
#                 ui.help_text("Select the number of stratum division you want"),
#                 ui.div(
#                     ui.input_slider("number_of_division", "", min=2, max=9, value=9)
#                 ),
#                 ui.div(ui.download_button("export_df", "Export chosen data")),
#                 open="always",
#                 width="17%",
#             ),
#             ui.div(
#                 output_widget("intercrops"),
#                 ui.output_image("main_species_image", height="auto", width="100%"),
#                 class_="main-content",
#             ),
#             ui.div(ui.output_ui("compatibility")),
#             # ui.div(ui.output_ui("card_wrong_plant"))),
#             height="2000px",
#         ),
#     ),
# )
# ! UDATEd
# main_species = ui.nav_panel(
#     "❸ Main Species",
#     ui.page_fluid(
#         # Define the UI
#         ui.div(
#             # Outer grey container
#             ui.div(
#                 # Flex container for left (input) and right (text)
#                 ui.div(
#                     # Left Section: Input Selection
#                     ui.div(
#                         ui.p("Which plant data do you want to display?", class_="bold-text"),
#                         ui.input_selectize("overview_plants", 
#                                         "", 
#                                         choices=get_Plants(FILE_NAME),  # Populate dynamically in server
#                                         multiple=True,
#                                         options={
#                                             "placeholder": "Type common or scientific name here...",
#                                             "create": True,
#                                         },
#                         ),
#                         class_="left-section-sm"
#                     ),

#                     # Right Section: Text Instructions
#                     ui.div(
#                         ui.p("More than 1 species in the same rectangle below indicate that they will likely compete. You might still combine them, but would probably need to reduce the density of each."
#                             ),
#                         ui.div(ui.download_button("export_df", "Export chosen data")),
#                         class_="right-section-sm"
#                     ),
#                     class_="flex-container-ms"  # Flexbox container for layout
#                 ),
#                 class_="grey-container"  # Apply the grey background
#             ),
#             ui.div(
#             output_widget("intercrops"),
#             ),
#             ui.p("Lifetime"),
#             ui.help_text(
#                     "Visualize the growth of every species over time (in year)"
#                 ),
#             ui.div(
#             ui.input_slider("life_time", "", min=0, max=101, value=1), class_="input-selectize",
#                 ),
#             ui.div(
#                 output_widget("plot_plants"),
#             ),
#         )
#     )
# )
# ! WORKING ABOVE

main_species = ui.nav_panel(
    "❸ Species",
    ui.page_fluid(
        # Define the UI
        ui.div(
            # Outer grey container
            ui.div(
                # Flex container for left (input) and right (text)
                ui.div(
                    # Left Section: Input Selection
                    ui.div(
                        ui.p("Which plant data do you want to display?", class_="bold-text"),
                        ui.input_selectize("overview_plants", 
                                        "", 
                                        choices=get_Plants(FILE_NAME),  # Populate dynamically in server
                                        multiple=True,
                                        options={
                                            "placeholder": "Type name here...",
                                            "create": True,
                                        },
                        ),
                        class_="left-section-sm"
                    ),

                    # Right Section: Text Instructions
                    ui.div(
                        ui.p("More than 1 species in the same rectangle below indicate that they will likely compete. You might still combine them, but would probably need to reduce the density of each."
                            ),
                        ui.div(ui.download_button("export_df", "Export chosen data")),
                        class_="right-section-sm"
                    ),
                    class_="flex-container-ms"  # Flexbox container for layout
                ),
                class_="grey-container"  # Apply the grey background
            ),
            # Visualization Output
            ui.div(
                output_widget("intercrops"),
            ),
            ui.p(""),
            # New Grey Container for Lifetime Section
            ui.div(
                ui.div(
                    ui.p("Lifetime", class_="bold-text"),
                    ui.help_text("Visualize the growth of selected species over time"),
                    ui.input_slider("life_time", "", min=0, max=101, value=1, step = 0.5), 
                    class_="center-content"
                ),
                class_="grey-container"
            ),
            # Growth Visualization Output
            ui.div(
                output_widget("plot_plants"),
                ui.output_image("growth_form_image", height="auto", width="100%"),
                class_="main-content",
            ),
        )
    )
)
