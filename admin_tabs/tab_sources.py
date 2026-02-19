"""Admin Tab — Fontes detalhadas."""
from shiny import render, ui
from .helpers import _DB_OK, _html_table, _no_db, get_db


def sources_ui():
    return ui.nav_panel(
        "Fontes",
        ui.div("Growth Form por Fonte", class_="qe-section-title"),
        ui.div(ui.output_ui("qe_src_gf"), class_="qe-card"),
        ui.div("Ameaça (IUCN) por Fonte", class_="qe-section-title"),
        ui.div(ui.output_ui("qe_src_threat"), class_="qe-card"),
        ui.div("Longevidade por Fonte", class_="qe-section-title"),
        ui.div(ui.output_ui("qe_src_lifespan"), class_="qe-card"),
    )


def sources_server(input, output, session):

    @output
    @render.ui
    def qe_src_gf():
        if not _DB_OK:
            return _no_db()
        try:
            db = get_db()
            rows = db.execute("""
                SELECT growth_form_source,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE is_tree)    AS arvores,
                       COUNT(*) FILTER (WHERE is_shrub)   AS arbustos,
                       COUNT(*) FILTER (WHERE is_herb)    AS herbaceas,
                       COUNT(*) FILTER (WHERE is_climber) AS trepadeiras,
                       COUNT(*) FILTER (WHERE is_palm)    AS palmeiras
                FROM species_unified
                WHERE growth_form_source IS NOT NULL
                GROUP BY growth_form_source ORDER BY total DESC
            """)
            return ui.HTML(_html_table(
                ["fonte", "total", "árvores", "arbustos", "herbáceas", "trepadeiras", "palmeiras"],
                rows))
        except Exception as e:
            return ui.p(str(e), style="color:#f87171")

    @output
    @render.ui
    def qe_src_threat():
        if not _DB_OK:
            return _no_db()
        try:
            db = get_db()
            rows = db.execute("""
                SELECT threat_status_source,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE threat_status = 'CR') AS cr,
                       COUNT(*) FILTER (WHERE threat_status = 'EN') AS en,
                       COUNT(*) FILTER (WHERE threat_status = 'VU') AS vu,
                       COUNT(*) FILTER (WHERE threat_status = 'NT') AS nt,
                       COUNT(*) FILTER (WHERE threat_status = 'LC') AS lc
                FROM species_unified
                WHERE threat_status_source IS NOT NULL
                GROUP BY threat_status_source ORDER BY total DESC
            """)
            return ui.HTML(_html_table(["fonte", "total", "CR", "EN", "VU", "NT", "LC"], rows))
        except Exception as e:
            return ui.p(str(e), style="color:#f87171")

    @output
    @render.ui
    def qe_src_lifespan():
        if not _DB_OK:
            return _no_db()
        try:
            db = get_db()
            rows = db.execute("""
                SELECT lifespan_source,
                       COUNT(*) AS total,
                       ROUND(AVG(lifespan_years)::numeric, 1) AS media,
                       ROUND(MIN(lifespan_years)::numeric, 1) AS min,
                       ROUND(MAX(lifespan_years)::numeric, 1) AS max
                FROM species_unified
                WHERE lifespan_source IS NOT NULL
                GROUP BY lifespan_source ORDER BY total DESC
            """)
            return ui.HTML(_html_table(["fonte", "total", "média (anos)", "mín", "máx"], rows))
        except Exception as e:
            return ui.p(str(e), style="color:#f87171")
