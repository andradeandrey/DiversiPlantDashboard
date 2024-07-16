import os

from shiny import ui
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Variables

FILE_NAME = os.path.join(Path(__file__).parent.parent,"data","MgmtTraitData_CSV.csv")



choices = ui.nav_panel(
    "Choices", ui.page_fluid(
        #ui.layout_sidebar(
            # """ui.sidebar(
            #     ui.h3("Growth Form"),
            #     ui.help_text("Select the plant you want to analyze"),
            #     ui.div(ui.input_selectize(
            #         "overview_plants",
            #         "",
            #         choices=get_Variables(FILE_NAME),
            #         multiple=True
            #         ),class_="input-selectize"),
            #         open="always",
            #         width="17%"
            #         )""",
            ui.div(output_widget("plot_plants")),
            ui.div(ui.output_ui("suggestion")),
            height="2000px"
        )
    )