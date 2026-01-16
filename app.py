import sys
from pathlib import Path
from shiny import ui, App
import os
import uvicorn

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
sys.dont_write_bytecode = True

# from custom_ui.details_tabs import details
from custom_ui.tab_00_start import start
from custom_ui.tab_04_results import results
from custom_ui.tab_01_location import location
from custom_ui.tab_02_climate import climate
from custom_ui.tab_03_species import main_species
from custom_ui.tab_05_admin import admin

from custom_server.server_app import server_app
from custom_server.server_admin import server_admin
from custom_server.server_homepage import server_homepage
css_file = os.path.join(Path(__file__).parent,"data","ui.css")


# TODO: mount each tab like litefarm dashboard.

app_ui=ui.page_fluid(
    ui.include_css(css_file),
    ui.page_navbar(
    start,
    location,
    climate,
    main_species,
    # details,
    results,
    admin,
    title=ui.div("DiversiPlant", class_="title"),
    )
)


def combined_server(input, output, session):
    """Combined server function that includes all server logic."""
    server_app(input, output, session)
    server_admin(input, output, session)

static_dir = Path(__file__).parent / "data"
shiny_app = App(app_ui, combined_server, static_assets=static_dir)

# Redirect root to your shiny app
async def redirect_handler(request):
    return RedirectResponse(url="/diversiplant")

# Set up routes
routes = [
    Route("/", endpoint=redirect_handler),
    Mount("/diversiplant", app=shiny_app)
]

# Create the Starlette app
app = Starlette(routes=routes)
app.add_middleware(SessionMiddleware, secret_key="feur")

if __name__ == "__main__":
    uvicorn.run("app:app", host='127.0.0.1', port=8001, workers=16, ws_ping_interval = 48000, ws_ping_timeout= None)