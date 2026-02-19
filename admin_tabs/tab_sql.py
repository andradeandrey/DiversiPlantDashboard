"""Admin Tab — SQL Explorer."""
from shiny import reactive, render, ui
from .helpers import _DB_OK, _run_query, _html_table

# ── Exemplos SQL ─────────────────────────────────────────────────────────────

_EXAMPLES = {
    "": "-- selecione um exemplo --",
    "count_species":    "SELECT COUNT(*) AS total FROM species",
    "growth_forms":     "SELECT growth_form, COUNT(*) AS total\nFROM species_unified\nWHERE growth_form IS NOT NULL\nGROUP BY growth_form\nORDER BY total DESC",
    "top_families":     "SELECT family, COUNT(*) AS n\nFROM species\nWHERE family IS NOT NULL\nGROUP BY family\nORDER BY n DESC\nLIMIT 20",
    "native_brazil":    "SELECT s.canonical_name, s.family, su.growth_form\nFROM species s\nJOIN species_unified su ON s.id = su.species_id\nJOIN species_regions sr ON s.id = sr.species_id\nWHERE sr.tdwg_code = 'BZL' AND sr.is_native = TRUE\nORDER BY s.canonical_name\nLIMIT 50",
    "climate_biomes":   "SELECT whittaker_biome, COUNT(*) AS regioes,\n       ROUND(AVG(bio1_mean)::numeric, 1) AS temp_media_c,\n       ROUND(AVG(bio12_mean)::numeric) AS precip_mm\nFROM tdwg_climate\nWHERE whittaker_biome IS NOT NULL\nGROUP BY whittaker_biome\nORDER BY regioes DESC",
    "threat_status":    "SELECT threat_status, threat_status_source, COUNT(*) AS total\nFROM species_unified\nWHERE threat_status IS NOT NULL\nGROUP BY threat_status, threat_status_source\nORDER BY total DESC",
    "lifespan_by_form": "SELECT growth_form,\n       COUNT(*) AS n,\n       ROUND(AVG(lifespan_years)::numeric, 1) AS media,\n       ROUND(MIN(lifespan_years)::numeric, 1) AS min,\n       ROUND(MAX(lifespan_years)::numeric, 1) AS max\nFROM species_unified\nWHERE lifespan_years IS NOT NULL AND growth_form IS NOT NULL\nGROUP BY growth_form\nORDER BY media DESC",
    "sources_coverage": "SELECT growth_form_source,\n       COUNT(*) AS total,\n       COUNT(*) FILTER (WHERE is_tree)    AS arvores,\n       COUNT(*) FILTER (WHERE is_shrub)   AS arbustos,\n       COUNT(*) FILTER (WHERE is_herb)    AS herbaceas,\n       COUNT(*) FILTER (WHERE is_climber) AS trepadeiras,\n       COUNT(*) FILTER (WHERE is_palm)    AS palmeiras\nFROM species_unified\nWHERE growth_form_source IS NOT NULL\nGROUP BY growth_form_source\nORDER BY total DESC",
}

_EXAMPLE_LABELS = {
    "":                 "-- selecione um exemplo --",
    "count_species":    "Total de espécies",
    "growth_forms":     "Growth forms (contagem)",
    "top_families":     "Top 20 famílias",
    "native_brazil":    "Nativas do Brasil (BZL)",
    "climate_biomes":   "Biomas (clima)",
    "threat_status":    "Status de ameaça",
    "lifespan_by_form": "Longevidade por growth form",
    "sources_coverage": "Coverage por fonte",
}


def sql_ui():
    return ui.nav_panel(
        "SQL",
        ui.row(
            ui.column(5,
                ui.input_select("qe_example", "Exemplo:",
                                choices=_EXAMPLE_LABELS, selected=""),
            ),
            ui.column(3,
                ui.input_numeric("qe_limit", "Limite:", value=100, min=1, max=1000),
            ),
            ui.column(4,
                ui.input_action_button("qe_run", "Executar",
                                       class_="btn btn-success",
                                       style="margin-top:25px;width:100%"),
            ),
        ),
        ui.input_text_area("qe_sql", None,
                           placeholder="SELECT canonical_name, family FROM species LIMIT 10",
                           rows=9, width="100%"),
        ui.output_ui("qe_results"),
    )


def sql_server(input, output, session):

    @reactive.effect
    @reactive.event(input.qe_example)
    def _fill():
        key = input.qe_example()
        if key and key in _EXAMPLES:
            ui.update_text_area("qe_sql", value=_EXAMPLES[key])

    @output
    @render.ui
    @reactive.event(input.qe_run)
    def qe_results():
        sql = input.qe_sql()
        if not sql or not sql.strip():
            return ui.p("Escreva uma query SQL e clique em Executar.",
                        style="color:#666; margin-top:12px")
        if not _DB_OK:
            return ui.div("Banco não conectado.", class_="qe-err")
        limit = int(input.qe_limit() or 100)
        try:
            cols, rows, ms = _run_query(sql, limit)
            n = len(rows)
            meta = f"{n} linha{'s' if n != 1 else ''} · {ms} ms"
            body = _html_table(cols, rows) if n > 0 else "<p style='color:#666'>Nenhuma linha.</p>"
            return ui.div(
                ui.p(meta, class_="qe-meta"),
                ui.HTML(body),
            )
        except Exception as e:
            return ui.div(str(e), class_="qe-err")
