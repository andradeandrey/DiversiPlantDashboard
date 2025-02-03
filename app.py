import sys
from pathlib import Path
from shiny import ui, App
import os

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
sys.dont_write_bytecode = True

from custom_ui.details_tabs import details
from custom_ui.homepage_tabs import homepage
from custom_ui.os_tabs import other_species
from custom_ui.location_tabs import location
from custom_ui.climate_tabs import climate
from custom_ui.ms_tabs import main_species

from custom_server.server_app import server_app

css_file = os.path.join(Path(__file__).parent,"data","ui.css")

app_ui=ui.page_fluid(
    ui.include_css(css_file),
    ui.page_navbar(
    homepage,
    location,
    climate,
    main_species,
    # details,
    other_species,
    title=ui.div("Agroforestry Dashboard", class_="title"),
    )
)


static_dir = Path(__file__).parent / "data"
shiny_app = App(app_ui, server_app, static_assets=static_dir)

# Redirect root to your shiny app
async def redirect_handler(request):
    return RedirectResponse(url="/shiny")

# Set up routes
routes = [
    Route("/", endpoint=redirect_handler),
    Mount("/shiny", app=shiny_app)
]

# Create the Starlette app
app = Starlette(routes=routes)
app.add_middleware(SessionMiddleware, secret_key="feur")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host='0.0.0.0', port=8000)
