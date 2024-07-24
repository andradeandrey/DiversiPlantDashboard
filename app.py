from pathlib import Path
from shiny import ui, App
import os
from custom_ui.details_tabs import details
from custom_ui.intercrops_tabs import intercrops
from custom_ui.homepage_tabs import homepage
from custom_ui.suggestion_tabs import suggestion
from custom_server.server_app import server_app

css_file = os.path.join(Path(__file__).parent,"data","ui.css")
print(f"path={css_file}")

app_ui=ui.page_fluid(ui.include_css(css_file),ui.page_navbar(
    homepage,
    intercrops,
    details,
    suggestion,
    title=ui.div("Agroforestry Dashboard", class_="title")
))

app = App(app_ui, server_app)
