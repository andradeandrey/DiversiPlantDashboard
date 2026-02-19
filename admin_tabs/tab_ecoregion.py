"""Admin Tab — Ecoregion Species with Leaflet map + climate scoring.

Ports: handleEcoregionSpecies from ecoregion.go
"""
import io
import csv
from shiny import reactive, render, ui
from .helpers import (
    _DB_OK, _html_table, _fmt, _stat_card, _no_db, get_db,
    VALID_GROWTH_FORMS,
)

_LEAFLET_HTML = """
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<div id="eco-map" class="qe-map"></div>
<script>
(function() {
    var map = L.map('eco-map').setView([-15.8, -47.9], 4);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; CartoDB', maxZoom: 18
    }).addTo(map);
    var marker = null;
    map.on('click', function(e) {
        var lat = Math.round(e.latlng.lat * 10000) / 10000;
        var lon = Math.round(e.latlng.lng * 10000) / 10000;
        if (marker) map.removeLayer(marker);
        marker = L.circleMarker([lat, lon], {radius: 7, color: '#34d399', fillOpacity: 0.8}).addTo(map);
        Shiny.setInputValue('eco_map_lat', lat);
        Shiny.setInputValue('eco_map_lon', lon);
    });
})();
</script>
"""


def ecoregion_ui():
    gf_choices = {g: g for g in VALID_GROWTH_FORMS}
    return ui.nav_panel(
        "Ecorregião",
        ui.HTML(_LEAFLET_HTML),
        ui.row(
            ui.column(3, ui.input_numeric("eco_lat", "Latitude:", value=None)),
            ui.column(3, ui.input_numeric("eco_lon", "Longitude:", value=None)),
            ui.column(3,
                ui.input_slider("eco_threshold", "Climate Threshold:",
                                min=0.1, max=0.9, value=0.3, step=0.05),
            ),
            ui.column(3,
                ui.input_numeric("eco_limit", "Limite:", value=100, min=0, max=5000),
            ),
        ),
        ui.row(
            ui.column(9,
                ui.input_checkbox_group(
                    "eco_gf", "Growth Forms:",
                    choices=gf_choices, inline=True,
                ),
            ),
            ui.column(3,
                ui.input_action_button("eco_go", "Buscar Espécies",
                                       class_="btn btn-success",
                                       style="margin-top:25px;width:100%"),
            ),
        ),
        ui.output_ui("eco_result"),
        ui.download_button("eco_download", "Download CSV",
                           class_="btn btn-outline-secondary btn-sm",
                           style="margin-top:10px"),
    )


def ecoregion_server(input, output, session):

    # Sync map clicks to inputs
    @reactive.effect
    @reactive.event(input.eco_map_lat)
    def _sync_lat():
        ui.update_numeric("eco_lat", value=input.eco_map_lat())

    @reactive.effect
    @reactive.event(input.eco_map_lon)
    def _sync_lon():
        ui.update_numeric("eco_lon", value=input.eco_map_lon())

    # Store last results for download
    _last_results = reactive.Value([])
    _last_columns = reactive.Value([])

    @output
    @render.ui
    @reactive.event(input.eco_go)
    def eco_result():
        if not _DB_OK:
            return _no_db()

        lat = input.eco_lat()
        lon = input.eco_lon()
        if lat is None or lon is None:
            return ui.div("Clique no mapa ou informe lat/lon.", class_="qe-err")

        threshold = input.eco_threshold()
        limit = int(input.eco_limit() or 100)
        growth_forms = list(input.eco_gf() or [])

        db = get_db()
        try:
            # Get ecoregion
            from database.connection import get_ecoregion_by_coords
            eco = get_ecoregion_by_coords(lat, lon)
            if not eco:
                return ui.div("Nenhuma ecorregião encontrada.", class_="qe-err")

            eco_name = eco.get("eco_name", "—")
            biome_name = eco.get("biome_name", "—")
            biome_num = eco.get("biome_num")
            realm = eco.get("realm", "—")

            # Get climate at point
            from database.connection import get_bioclim_at_coords
            climate = get_bioclim_at_coords(lat, lon)

            # Get TDWG code for WCVP enrichment
            from database.connection import get_tdwg_by_coords
            tdwg = get_tdwg_by_coords(lat, lon)
            tdwg_code = tdwg["level3_code"] if tdwg else None

            # Info cards
            info_cards = ui.div(
                _stat_card(eco_name, "Ecorregião", "#22d3ee"),
                _stat_card(biome_name, "Bioma", "#a78bfa"),
                _stat_card(realm, "Realm", "#f59e0b"),
                class_="climate-grid",
            )

            # Climate cards
            clim_cards = []
            if climate:
                clim_cards = [ui.div(
                    _stat_card(f"{_fmt(climate.get('bio1'))}°C", "BIO1 Temp"),
                    _stat_card(f"{_fmt(climate.get('bio5'))}°C", "BIO5 Máx"),
                    _stat_card(f"{_fmt(climate.get('bio6'))}°C", "BIO6 Mín"),
                    _stat_card(f"{_fmt(climate.get('bio12'), 0)} mm", "BIO12 Precip"),
                    _stat_card(f"{_fmt(climate.get('bio15'))}", "BIO15 Sazonalidade"),
                    class_="stat-grid",
                    style="margin-bottom:16px",
                )]

            # Build growth form filter
            gf_filter = ""
            if growth_forms:
                gf_list = ", ".join(f"'{g}'" for g in growth_forms if g in VALID_GROWTH_FORMS)
                if gf_list:
                    gf_filter = f" AND su.growth_form IN ({gf_list})"

            limit_clause = f"LIMIT {limit}" if limit > 0 else ""

            # Build combined CTE (GBIF ecoregions + WCVP/TDWG)
            if tdwg_code and biome_num is not None:
                combined_cte = f"""
                    WITH combined_species AS (
                        SELECT species_id, SUM(total_obs) as total_obs, MAX(n_ecoregions) as n_ecoregions
                        FROM (
                            SELECT se.species_id, SUM(se.n_observations) as total_obs,
                                   COUNT(DISTINCT se.eco_id) as n_ecoregions
                            FROM species_ecoregions se
                            JOIN ecoregions e ON se.eco_id = e.eco_id
                            WHERE e.biome_num = :biome_num
                            GROUP BY se.species_id
                            UNION ALL
                            SELECT sr.species_id, 0 as total_obs, 0 as n_ecoregions
                            FROM species_regions sr
                            WHERE sr.tdwg_code = :tdwg_code
                        ) sources
                        GROUP BY species_id
                    )
                """
                params = {"biome_num": biome_num, "tdwg_code": tdwg_code, "threshold": threshold}
            elif biome_num is not None:
                combined_cte = """
                    WITH combined_species AS (
                        SELECT se.species_id, SUM(se.n_observations) as total_obs,
                               COUNT(DISTINCT se.eco_id) as n_ecoregions
                        FROM species_ecoregions se
                        JOIN ecoregions e ON se.eco_id = e.eco_id
                        WHERE e.biome_num = :biome_num
                        GROUP BY se.species_id
                    )
                """
                params = {"biome_num": biome_num, "threshold": threshold}
            else:
                return ui.div("Bioma não identificado.", class_="qe-err")

            if climate and climate.get("bio1") is not None:
                params.update({
                    "bio1": climate["bio1"], "bio5": climate["bio5"],
                    "bio6": climate["bio6"],
                    "bio12": climate.get("bio12", 1000),
                    "bio15": climate.get("bio15", 50),
                })
                query = f"""
                    {combined_cte}
                    SELECT s.canonical_name, COALESCE(s.family, ''),
                           su.growth_form,
                           COALESCE(calculate_climate_match(s.id, :bio1, :bio5, :bio6, :bio12, :bio15), 0.5) as climate_score,
                           cs.n_ecoregions, cs.total_obs,
                           su.threat_status
                    FROM combined_species cs
                    JOIN species s ON cs.species_id = s.id
                    LEFT JOIN species_unified su ON s.id = su.species_id
                    WHERE COALESCE(calculate_climate_match(s.id, :bio1, :bio5, :bio6, :bio12, :bio15), 0.5) >= :threshold
                      AND su.growth_form IS NOT NULL
                      {gf_filter}
                    ORDER BY climate_score DESC, cs.total_obs DESC
                    {limit_clause}
                """
            else:
                query = f"""
                    {combined_cte}
                    SELECT s.canonical_name, COALESCE(s.family, ''),
                           su.growth_form,
                           0.5 as climate_score,
                           cs.n_ecoregions, cs.total_obs,
                           su.threat_status
                    FROM combined_species cs
                    JOIN species s ON cs.species_id = s.id
                    LEFT JOIN species_unified su ON s.id = su.species_id
                    WHERE su.growth_form IS NOT NULL
                      {gf_filter}
                    ORDER BY cs.total_obs DESC
                    {limit_clause}
                """

            species_rows = db.execute(query, params)

            # Count total in biome
            if tdwg_code and biome_num is not None:
                total_in_biome = db.execute_scalar(f"""
                    SELECT COUNT(DISTINCT species_id) FROM (
                        SELECT se.species_id FROM species_ecoregions se
                        JOIN ecoregions e ON se.eco_id = e.eco_id WHERE e.biome_num = :bn
                        UNION
                        SELECT sr.species_id FROM species_regions sr WHERE sr.tdwg_code = :tc
                    ) combined
                """, {"bn": biome_num, "tc": tdwg_code}) or 0
            else:
                total_in_biome = db.execute_scalar("""
                    SELECT COUNT(DISTINCT se.species_id)
                    FROM species_ecoregions se
                    JOIN ecoregions e ON se.eco_id = e.eco_id
                    WHERE e.biome_num = :bn
                """, {"bn": biome_num}) or 0

            cols = ["espécie", "família", "growth_form", "climate_score", "ecorregiões", "observações", "ameaça"]
            _last_columns.set(cols)
            _last_results.set(species_rows)

            meta = ui.p(
                f"{len(species_rows)} espécies (de {total_in_biome:,} no bioma) · threshold {threshold}",
                class_="qe-meta",
            )

            # Format score as percentage for display
            display_rows = []
            for r in species_rows:
                display_rows.append((
                    r[0], r[1], r[2],
                    f"{float(r[3])*100:.0f}%" if r[3] is not None else "—",
                    r[4], r[5], r[6] or "",
                ))

            tbl = ui.HTML(_html_table(cols, display_rows))

            return ui.div(info_cards, *clim_cards, meta, ui.div(tbl, class_="qe-card"))

        except Exception as e:
            return ui.div(str(e), class_="qe-err")

    @render.download(filename="ecoregion_species.csv")
    def eco_download():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_last_columns.get())
        for row in _last_results.get():
            writer.writerow(row)
        yield buf.getvalue()
