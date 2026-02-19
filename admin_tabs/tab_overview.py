"""Admin Tab — Visão Geral (Stats cards + growth form + sources mini)."""
from shiny import render, ui
from .helpers import _DB_OK, _html_table, _stat_card, _no_db, get_db


def overview_ui():
    return ui.nav_panel(
        "Visão Geral",
        ui.output_ui("qe_stats"),
        ui.div("Growth Forms", class_="qe-section-title"),
        ui.div(ui.output_ui("qe_growth"), class_="qe-card"),
        ui.div("Fontes de Dados", class_="qe-section-title"),
        ui.div(ui.output_ui("qe_sources_mini"), class_="qe-card"),
    )


def overview_server(input, output, session):

    @output
    @render.ui
    def qe_stats():
        if not _DB_OK:
            return _no_db()
        TABLES = [
            ("species",          "Espécies"),
            ("species_unified",  "Traits"),
            ("species_regions",  "Regiões"),
            ("species_geometry", "Geometrias"),
            ("tdwg_level3",      "TDWG L3"),
            ("tdwg_climate",     "Clima TDWG"),
        ]
        db = get_db()
        cards = []
        for tbl, lbl in TABLES:
            try:
                n = db.execute_scalar(f"SELECT COUNT(*) FROM {tbl}") or 0
                val = f"{n:,}"
            except Exception:
                val = "—"
            cards.append(_stat_card(val, lbl))
        return ui.div(*cards, class_="stat-grid")

    @output
    @render.ui
    def qe_growth():
        if not _DB_OK:
            return ui.p("—")
        try:
            db = get_db()
            rows = db.execute("""
                SELECT growth_form, COUNT(*) AS total
                FROM species_unified
                WHERE growth_form IS NOT NULL
                GROUP BY growth_form ORDER BY total DESC LIMIT 15
            """)
            return ui.HTML(_html_table(["growth_form", "total"], rows))
        except Exception as e:
            return ui.p(str(e), style="color:#f87171")

    @output
    @render.ui
    def qe_sources_mini():
        if not _DB_OK:
            return ui.p("—")
        try:
            db = get_db()
            rows = db.execute("""
                SELECT growth_form_source, COUNT(*) AS total
                FROM species_unified
                WHERE growth_form_source IS NOT NULL
                GROUP BY growth_form_source ORDER BY total DESC
            """)
            return ui.HTML(_html_table(["fonte", "total"], rows))
        except Exception as e:
            return ui.p(str(e), style="color:#f87171")
