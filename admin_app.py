"""DiversiPlant — Admin Query Explorer (standalone Shiny app).

Montado em /admin pelo app.py principal.
Coordena todos os módulos em admin_tabs/.
"""
from shiny import App, ui

from admin_tabs.helpers import _CSS
from admin_tabs.tab_overview import overview_ui, overview_server
from admin_tabs.tab_sql import sql_ui, sql_server
from admin_tabs.tab_climate import climate_ui, climate_server
from admin_tabs.tab_location import location_ui, location_server
from admin_tabs.tab_ecoregion import ecoregion_ui, ecoregion_server
from admin_tabs.tab_recommend import recommend_ui, recommend_server
from admin_tabs.tab_upload import upload_ui, upload_server
from admin_tabs.tab_sources import sources_ui, sources_server
from admin_tabs.tab_health import health_ui, health_server


# ── UI ────────────────────────────────────────────────────────────────────────

app_ui = ui.page_fluid(
    ui.tags.style(_CSS),

    # Header
    ui.div(
        ui.div(class_="qe-dot", id="qe-status-dot"),
        ui.div(
            ui.tags.h1("DiversiPlant Admin"),
            ui.div("Database · Query Explorer", class_="sub"),
        ),
        class_="qe-header",
    ),

    ui.div(
        ui.navset_tab(
            overview_ui(),
            sql_ui(),
            climate_ui(),
            location_ui(),
            ecoregion_ui(),
            recommend_ui(),
            upload_ui(),
            sources_ui(),
            health_ui(),
        ),
        class_="qe-body",
    ),
)


# ── Server ────────────────────────────────────────────────────────────────────

def server(input, output, session):
    overview_server(input, output, session)
    sql_server(input, output, session)
    climate_server(input, output, session)
    location_server(input, output, session)
    ecoregion_server(input, output, session)
    recommend_server(input, output, session)
    upload_server(input, output, session)
    sources_server(input, output, session)
    health_server(input, output, session)


admin_app = App(app_ui, server)
