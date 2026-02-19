"""Admin Tab — Location Query (TDWG + PostGIS + species listing).

Ports: handleTDWG + handleSpecies from Go.
"""
from shiny import reactive, render, ui
from .helpers import (
    _DB_OK, _html_table, _stat_card, _no_db, get_db,
    VALID_GROWTH_FORMS,
)


def location_ui():
    gf_choices = {"": "Todos"} | {g: g for g in VALID_GROWTH_FORMS}
    return ui.nav_panel(
        "Localizar",
        ui.row(
            ui.column(3, ui.input_numeric("loc_lat", "Latitude:", value=-27.59)),
            ui.column(3, ui.input_numeric("loc_lon", "Longitude:", value=-48.54)),
            ui.column(3, ui.input_select("loc_gf", "Growth Form:", choices=gf_choices)),
            ui.column(3,
                ui.input_action_button("loc_go", "Localizar",
                                       class_="btn btn-success",
                                       style="margin-top:25px;width:100%"),
            ),
        ),
        ui.row(
            ui.column(4, ui.input_numeric("loc_limit", "Limite:", value=50, min=1, max=500)),
            ui.column(4,
                ui.input_checkbox("loc_native", "Apenas nativas", value=False),
            ),
        ),
        ui.output_ui("loc_result"),
    )


def location_server(input, output, session):

    @output
    @render.ui
    @reactive.event(input.loc_go)
    def loc_result():
        if not _DB_OK:
            return _no_db()

        lat = input.loc_lat()
        lon = input.loc_lon()
        if lat is None or lon is None:
            return ui.div("Informe latitude e longitude.", class_="qe-err")

        db = get_db()
        try:
            # Resolve TDWG region
            from database.connection import get_tdwg_by_coords
            tdwg = get_tdwg_by_coords(lat, lon)
            if not tdwg:
                return ui.div("Nenhuma região TDWG encontrada para essas coordenadas.", class_="qe-err")

            code = tdwg["level3_code"]
            name = tdwg["level3_name"]
            continent = tdwg.get("continent", "—")

            region_info = ui.div(
                _stat_card(code, "Código TDWG", "#22d3ee"),
                _stat_card(name, "Região", "#34d399"),
                _stat_card(continent, "Continente", "#a78bfa"),
                class_="stat-grid",
                style="margin-bottom:20px",
            )

            # Build species query
            gf = input.loc_gf() or ""
            native_only = input.loc_native()
            limit = int(input.loc_limit() or 50)

            params = {"tdwg": code, "limit": limit}
            where_extra = ""

            if gf:
                where_extra += " AND su.growth_form = :gf"
                params["gf"] = gf
            if native_only:
                where_extra += " AND sr.is_native = TRUE"

            species_rows = db.execute(f"""
                SELECT DISTINCT ON (s.id)
                       s.canonical_name, COALESCE(s.family, ''),
                       COALESCE(su.growth_form, ''),
                       COALESCE(sr.is_native::text, ''),
                       cn.common_name
                FROM species s
                JOIN species_unified su ON s.id = su.species_id
                JOIN species_regions sr ON s.id = sr.species_id
                LEFT JOIN common_names cn ON s.id = cn.species_id AND cn.language = 'pt'
                WHERE sr.tdwg_code = :tdwg
                  AND su.growth_form IS NOT NULL
                  {where_extra}
                ORDER BY s.id, s.canonical_name
                LIMIT :limit
            """, params)

            # Count total
            count_params = {"tdwg": code}
            count_where = ""
            if gf:
                count_where += " AND su.growth_form = :gf"
                count_params["gf"] = gf
            if native_only:
                count_where += " AND sr.is_native = TRUE"

            total = db.execute_scalar(f"""
                SELECT COUNT(DISTINCT s.id)
                FROM species s
                JOIN species_unified su ON s.id = su.species_id
                JOIN species_regions sr ON s.id = sr.species_id
                WHERE sr.tdwg_code = :tdwg
                  AND su.growth_form IS NOT NULL
                  {count_where}
            """, count_params) or 0

            meta = ui.p(
                f"{len(species_rows)} de {total:,} espécies",
                class_="qe-meta",
            )

            tbl = ui.HTML(_html_table(
                ["espécie", "família", "growth_form", "nativa", "nome comum"],
                species_rows,
            ))

            return ui.div(region_info, meta, ui.div(tbl, class_="qe-card"))

        except Exception as e:
            return ui.div(str(e), class_="qe-err")
