import os
from shiny import ui,App
from pathlib import Path



FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_updated.csv")

# Updated Results Panel UI with sidebar for column selection
results = ui.nav_panel(
    ui.div(
        ui.span("4", class_="badge bg-secondary rounded-circle me-2"),  # Changed to bg-success for green
        ui.span("Results"),
        class_="d-flex align-items-center"
    ),
    ui.page_sidebar(
        # Sidebar content
        ui.sidebar(
            ui.h4("Filter Results"),
            ui.input_checkbox_group(
                "selected_columns", 
                "Select columns to display:",
                [], # Will be populated dynamically
                selected=[]
            ),
            ui.hr(),
            ui.download_button("export_df_os", "Download Data", class_="btn-primary btn-block mt-2")
        ),
        # Main content
        ui.output_ui("suggestion_plants", class_="input-selectize")
    )
)