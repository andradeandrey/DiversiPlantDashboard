import sys
from pathlib import Path
from shiny import ui, App, reactive
import os
import uvicorn

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
sys.dont_write_bytecode = True

# from custom_ui.details_tabs import details
from custom_ui.tab_00_start import start
from custom_ui.tab_04_results import results
from custom_ui.tab_01_location import location
from custom_ui.tab_02_climate import climate
from custom_ui.tab_03_species import main_species
from custom_ui.tab_05_admin import admin
from custom_ui.tab_06_recommend import recommend
from custom_ui.i18n import lang_toggle, lang_init_script

from custom_server.server_app import server_app
from custom_server.server_admin import server_admin
from custom_server.server_homepage import server_homepage
from custom_server.server_recommend import server_recommend
css_file = os.path.join(Path(__file__).parent, "data", "ui.css")


# TODO: mount each tab like litefarm dashboard.

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.script(src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"),
    ),
    ui.include_css(css_file),
    lang_init_script(),
    ui.page_navbar(
        start,
        location,
        climate,
        main_species,
        # details,
        results,
        recommend,
        admin,
        ui.nav_spacer(),
        ui.nav_control(ui.output_ui("location_badge")),
        ui.nav_control(lang_toggle()),
        title=ui.img(
            src="img/menu-logo.png",
            style="height: 32px; width: auto; margin-right: 30px;",
        ),
        id="main_nav",
    ),
)


def combined_server(input, output, session):
    """Combined server function that includes all server logic."""
    server_app(input, output, session)
    server_admin(input, output, session)
    server_recommend(input, output, session)

    # Navigation handler for Voltar/Próximo buttons
    @reactive.effect
    @reactive.event(input._nav_to)
    def _navigate():
        ui.update_navs("main_nav", selected=input._nav_to())

static_dir = Path(__file__).parent / "data"
shiny_app = App(app_ui, combined_server, static_assets=static_dir)

# Redirect root to your shiny app
async def redirect_handler(request):
    return RedirectResponse(url="/diversiplant")


async def run_crawler_handler(request):
    """Receive practitioners CSV upload, save to disk, and run the crawler."""
    import asyncio

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return JSONResponse({"error": "multipart/form-data required"}, status_code=400)

    form = await request.form()
    upload = form.get("file")
    if upload is None:
        return JSONResponse({"error": "No file field in upload"}, status_code=400)

    # Save CSV to data/practitioners.csv
    data_dir = Path(__file__).parent / "data"
    csv_path = data_dir / "practitioners.csv"

    contents = await upload.read()
    csv_path.write_bytes(contents)

    # Build DATABASE_URL from env vars
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_user = os.environ.get("DB_USER", "diversiplant")
    db_password = os.environ.get("DB_PASSWORD", "diversiplant")
    db_name = os.environ.get("DB_NAME", "diversiplant")
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    # Run crawler in a thread to avoid blocking the event loop
    def _run_crawler():
        from crawlers import get_crawler
        crawler = get_crawler('practitioners', db_url)
        crawler.run(mode='full')
        return dict(crawler.stats)

    try:
        stats = await asyncio.to_thread(_run_crawler)
        return JSONResponse(stats)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Set up routes
routes = [
    Route("/", endpoint=redirect_handler),
    Route("/api/admin/run-crawler", endpoint=run_crawler_handler, methods=["POST"]),
    Mount("/diversiplant", app=shiny_app)
]

# Create the Starlette app
app = Starlette(routes=routes)
app.add_middleware(SessionMiddleware, secret_key="feur")

if __name__ == "__main__":
    uvicorn.run("app:app", host='0.0.0.0', port=8001, workers=4, ws_ping_interval = 48000, ws_ping_timeout= None)
