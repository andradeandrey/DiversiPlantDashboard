"""Admin Tab — Saúde do banco."""
import time
from shiny import render, ui
from .helpers import _DB_OK, _html_table, get_db


def health_ui():
    return ui.nav_panel("Saúde", ui.output_ui("qe_health"))


def health_server(input, output, session):

    @output
    @render.ui
    def qe_health():
        if not _DB_OK:
            return ui.div(
                ui.span("● ", class_="health-err"),
                ui.span("Módulo de banco não disponível."),
            )
        try:
            db = get_db()
            t0 = time.perf_counter()
            db.execute_scalar("SELECT 1")
            ping_ms = round((time.perf_counter() - t0) * 1000, 1)

            try:
                postgis = db.execute_scalar("SELECT PostGIS_version()") or "—"
            except Exception:
                postgis = "não disponível"

            TABLES = [
                "species", "species_unified", "species_regions",
                "species_geometry", "tdwg_level3", "tdwg_climate",
            ]
            rows = []
            for tbl in TABLES:
                try:
                    n = db.execute_scalar(f"SELECT COUNT(*) FROM {tbl}") or 0
                    rows.append((tbl, f"{n:,}"))
                except Exception as e:
                    rows.append((tbl, f"erro: {e}"))

            return ui.div(
                ui.p(
                    ui.span("● ", class_="health-ok"),
                    ui.span(f"Banco conectado · ping {ping_ms} ms"),
                    style="font-size:1.05em; margin-bottom:6px",
                ),
                ui.p(
                    ui.strong("PostGIS: "),
                    ui.span(str(postgis)),
                    style="color:#666; font-size:0.9em; margin-bottom:20px",
                ),
                ui.HTML(_html_table(["tabela", "linhas"], rows)),
            )
        except Exception as e:
            return ui.div(
                ui.span("● ", class_="health-err"),
                ui.span(f"Erro de conexão: {e}"),
            )
