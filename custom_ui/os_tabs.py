import os
from shiny import ui,App
from pathlib import Path



FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_updated.csv")

# other_species = ui.nav_panel("❹ Other Species",
#     ui.page_fluid(ui.page_fluid(               
#                 ui.div(ui.output_ui(
#                     "suggestion_plants",
#                     ),class_="input-selectize"),

#                 open="always",
#                 width="17%"
#                 ),
#         # ui.div(ui.output_ui("suggestion")),
#         ui.download_button("export_df_os", "Export data"),
#         ))

# Define the UI for the 'Other Species' tab
other_species = ui.nav_panel("❹ Other Species",
    ui.page_fluid(
        ui.row(
            ui.column(
                12,  # Full-width column
                ui.output_ui("suggestion_plants", class_="input-selectize"),  # Display the suggestions
                ui.download_button("export_df_os", "Download Data", class_="mt-2 float-right")  # Download button with margin top and float right
            )
        )
    )
)