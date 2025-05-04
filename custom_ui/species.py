import os
from shiny import ui, App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants


FILE_NAME = os.path.join(
    Path(__file__).parent.parent, "data", "MgmtTraitData_updated.csv"
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
