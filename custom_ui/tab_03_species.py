import os
from shiny import ui, App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants


FILE_NAME = os.path.join(
    Path(__file__).parent.parent, "data", "MgmtTraitData_updated.csv"
    # Path(__file__).parent.parent, "data", "practitioners.csv"
)

main_species = ui.nav_panel(
    ui.div(
        ui.span("3", class_="badge bg-secondary rounded-circle me-2"),
        ui.span("Main Species"),
        class_="d-flex align-items-center"
    ),
    ui.page_fluid(
        # Define the UI
        ui.div(
            # Outer grey container
            ui.div(
                # Flex container for left (input) and right (text)
                ui.div(
                    # Left Section: Input Selection
                    ui.div(
                        ui.p("Which species do you want to plant?", class_="bold-text"),
                        ui.input_selectize("overview_plants", 
                                        "", 
                                        choices=get_Plants(FILE_NAME),
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
                        class_="right-section-sm"
                    ),
                    class_="flex-container-ms"
                ),
                class_="grey-container"
            ),
            
            # NEW: Binning controls side by side
            ui.div(
                ui.div(
                    # Stratum Resolution Dropdown
                    ui.div(
                        ui.p("Stratum Resolution", class_="bold-text"),
                        ui.help_text("Number of vertical layers (light demand levels)"),
                        ui.input_select(
                            "stratum_bins",
                            "",
                            choices={
                                "2": "2 layers - Low detail",
                                "3": "3 layers",
                                "4": "4 layers - Medium detail",
                                "5": "5 layers",
                                "6": "6 layers - High detail",
                                "7": "7 layers",
                                "8": "8 layers",
                                "9": "9 layers - Maximum detail"
                            },
                            selected="4"
                        ),
                        style="flex: 1; padding-right: 10px;"
                    ),
                    
                    # Harvest Period Binning Dropdown
                    ui.div(
                        ui.p("Harvest Period Resolution", class_="bold-text"),
                        ui.help_text("Number of horizonal divisions (time period)"),
                        ui.input_select(
                            "harvest_bins",
                            "",
                            choices={
                                "2": "2 periods - Low detail",
                                "3": "3 periods",
                                "4": "4 periods - Medium detail",
                                "5": "5 periods",
                                "6": "6 periods - High detail",
                                "7": "7 periods",
                                "8": "8 periods",
                                "9": "9 periods",
                                "10": "10 periods - Maximum detail"
                            },
                            selected="4"
                        ),
                        style="flex: 1; padding-left: 10px;"
                    ),
                    style="display: flex; gap: 20px;"
                ),
                class_="grey-container"
            ),
            
            # Visualization Output
            ui.div(
                output_widget("intercrops"),
            ),
            ui.p(""),
            
            # Lifetime Section
            ui.div(
                ui.div(
                    ui.p("Lifetime", class_="bold-text"),
                    ui.help_text("Visualize the growth of selected species over time"),
                    ui.input_slider("life_time", "", min=0, max=101, value=1, step=0.5), 
                    class_="center-content"
                ),
                class_="grey-container"
            ),
            
            # Growth Visualization Output
            ui.div(
                output_widget("plot_plants"),
                class_="main-content",
            ),
        )
    )
)