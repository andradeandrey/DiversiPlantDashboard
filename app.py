from pathlib import Path
from shiny import ui, App
import os
from custom_ui.choices_tabs import choices
from custom_ui.intercrops_tabs import intercrops
from custom_ui.homepage_tabs import homepage
from custom_server.server_app import server_app

css_file = os.path.join(Path(__file__).parent,"data","ui.css")
print(f"path={css_file}")

app_ui=ui.page_fluid(ui.include_css(css_file),ui.page_navbar(
    homepage,
    intercrops,
    choices,
    title=ui.div("Agroforestry Dashboard", class_="title")
))

app = App(app_ui, server_app)
