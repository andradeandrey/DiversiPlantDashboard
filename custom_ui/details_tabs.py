import os

from shiny import ui
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants


FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")



details = ui.nav_panel(
    "Details", ui.page_fluid(
        ui.layout_sidebar(
            ui.sidebar(
                ui.h3("Lifetime"),
                ui.help_text("Visualize the growth of every species over time (in year)"),
                ui.div(ui.input_slider(
                    "life_time",
                    "",
                    min=0,
                    max=101,
                    value=1
                    ),class_="input-selectize"),
                    open="always",
                    width="17%"
                    ),
            ui.div(output_widget("plot_plants")),
            
            height="2000px"
        )
    )
)