"""Admin Tab — Climate Data Explorer.

Ports: handleClimate, handleClimateStats, handleClimatePoint, handleClimateSpecies
"""
from shiny import reactive, render, ui
from .helpers import (
    _DB_OK, _html_table, _fmt, _stat_card, _no_db, get_db,
    BIO_LABELS,
)


def climate_ui():
    return ui.nav_panel(
        "Clima",
        # Quick buttons
        ui.div(
            ui.p("Regiões rápidas:", style="color:#888;font-size:0.82em;margin:0 0 6px"),
            ui.div(
                ui.input_action_button("clim_bzn", "BZN (Norte)", class_="btn btn-sm btn-outline-secondary"),
                ui.input_action_button("clim_bzs", "BZS (Sul)", class_="btn btn-sm btn-outline-secondary"),
                ui.input_action_button("clim_bze", "BZE (Leste)", class_="btn btn-sm btn-outline-secondary"),
                ui.input_action_button("clim_bzc", "BZC (Centro)", class_="btn btn-sm btn-outline-secondary"),
                ui.input_action_button("clim_bzl", "BZL (Sudeste)", class_="btn btn-sm btn-outline-secondary"),
                class_="qe-quick-btns",
            ),
        ),
        ui.row(
            ui.column(3, ui.input_text("clim_tdwg", "Código TDWG:", placeholder="BZS")),
            ui.column(3, ui.input_numeric("clim_lat", "Latitude:", value=None)),
            ui.column(3, ui.input_numeric("clim_lon", "Longitude:", value=None)),
            ui.column(3,
                ui.input_action_button("clim_go", "Consultar Clima",
                                       class_="btn btn-success",
                                       style="margin-top:25px;width:100%"),
            ),
        ),
        ui.output_ui("clim_result"),

        ui.tags.hr(style="border-color:#2a2a2a;margin:28px 0"),

        # Climate stats
        ui.div("Estatísticas Globais de Clima", class_="qe-section-title"),
        ui.output_ui("clim_stats"),

        ui.tags.hr(style="border-color:#2a2a2a;margin:28px 0"),

        # Species climate profile
        ui.div("Perfil Climático de Espécie", class_="qe-section-title"),
        ui.row(
            ui.column(8, ui.input_text("clim_species", "Nome da espécie:",
                                       placeholder="Solanum lycopersicum")),
            ui.column(4,
                ui.input_action_button("clim_sp_go", "Buscar",
                                       class_="btn btn-success",
                                       style="margin-top:25px;width:100%"),
            ),
        ),
        ui.output_ui("clim_species_result"),
    )


def climate_server(input, output, session):

    # Quick buttons fill TDWG code
    @reactive.effect
    @reactive.event(input.clim_bzn)
    def _bzn():
        ui.update_text("clim_tdwg", value="BZN")

    @reactive.effect
    @reactive.event(input.clim_bzs)
    def _bzs():
        ui.update_text("clim_tdwg", value="BZS")

    @reactive.effect
    @reactive.event(input.clim_bze)
    def _bze():
        ui.update_text("clim_tdwg", value="BZE")

    @reactive.effect
    @reactive.event(input.clim_bzc)
    def _bzc():
        ui.update_text("clim_tdwg", value="BZC")

    @reactive.effect
    @reactive.event(input.clim_bzl)
    def _bzl():
        ui.update_text("clim_tdwg", value="BZL")

    # ── Main climate query ───────────────────────────────────────────────
    @output
    @render.ui
    @reactive.event(input.clim_go)
    def clim_result():
        if not _DB_OK:
            return _no_db()

        tdwg = (input.clim_tdwg() or "").strip().upper()
        lat = input.clim_lat()
        lon = input.clim_lon()

        if not tdwg and (lat is None or lon is None):
            return ui.div("Informe código TDWG ou lat/lon.", class_="qe-err")

        db = get_db()
        try:
            if tdwg:
                rows = db.execute("""
                    SELECT c.tdwg_code, t.level3_name,
                           c.bio1_mean, c.bio1_min, c.bio1_max,
                           c.bio2_mean, c.bio3_mean, c.bio4_mean,
                           c.bio5_mean, c.bio6_mean, c.bio7_mean,
                           c.bio8_mean, c.bio9_mean, c.bio10_mean, c.bio11_mean,
                           c.bio12_mean, c.bio12_min, c.bio12_max,
                           c.bio13_mean, c.bio14_mean, c.bio15_mean,
                           c.bio16_mean, c.bio17_mean, c.bio18_mean, c.bio19_mean,
                           c.koppen_zone, c.whittaker_biome, c.aridity_index
                    FROM tdwg_climate c
                    JOIN tdwg_level3 t ON c.tdwg_code = t.level3_code
                    WHERE c.tdwg_code = :code
                """, {"code": tdwg})
            else:
                rows = db.execute("""
                    SELECT c.tdwg_code, t.level3_name,
                           c.bio1_mean, c.bio1_min, c.bio1_max,
                           c.bio2_mean, c.bio3_mean, c.bio4_mean,
                           c.bio5_mean, c.bio6_mean, c.bio7_mean,
                           c.bio8_mean, c.bio9_mean, c.bio10_mean, c.bio11_mean,
                           c.bio12_mean, c.bio12_min, c.bio12_max,
                           c.bio13_mean, c.bio14_mean, c.bio15_mean,
                           c.bio16_mean, c.bio17_mean, c.bio18_mean, c.bio19_mean,
                           c.koppen_zone, c.whittaker_biome, c.aridity_index
                    FROM tdwg_level3 t
                    JOIN tdwg_climate c ON t.level3_code = c.tdwg_code
                    WHERE ST_Contains(t.geom, ST_SetSRID(ST_Point(:lon, :lat), 4326))
                    LIMIT 1
                """, {"lat": lat, "lon": lon})

            if not rows:
                return ui.div("Nenhum dado climático encontrado.", class_="qe-err")

            r = rows[0]
            code, name = r[0], r[1]
            bio1m, bio1mn, bio1mx = r[2], r[3], r[4]
            bio_means = list(r[5:23])  # bio2..bio19 means
            koppen, biome, aridity = r[25], r[26], r[27]
            bio12m, bio12mn, bio12mx = r[15], r[16], r[17]

            # Header cards
            cards = ui.div(
                _stat_card(name or code, "Região", "#22d3ee"),
                _stat_card(biome or "—", "Whittaker Biome", "#a78bfa"),
                _stat_card(koppen or "—", "Köppen Zone", "#f59e0b"),
                _stat_card(_fmt(aridity), "Aridity Index", "#ec4899"),
                class_="climate-grid",
            )

            # Temperature panel
            temp_panel = ui.div(
                ui.div("Temperatura", class_="qe-section-title"),
                ui.div(
                    _stat_card(f"{_fmt(bio1m)}°C", "BIO1 Média Anual"),
                    _stat_card(f"{_fmt(bio1mn)}°C", "BIO1 Mínima"),
                    _stat_card(f"{_fmt(bio1mx)}°C", "BIO1 Máxima"),
                    class_="stat-grid",
                ),
            )

            # Precipitation panel
            precip_panel = ui.div(
                ui.div("Precipitação", class_="qe-section-title"),
                ui.div(
                    _stat_card(f"{_fmt(bio12m, 0)} mm", "BIO12 Média Anual"),
                    _stat_card(f"{_fmt(bio12mn, 0)} mm", "BIO12 Mínima"),
                    _stat_card(f"{_fmt(bio12mx, 0)} mm", "BIO12 Máxima"),
                    class_="stat-grid",
                ),
            )

            # All 19 bio variables grid
            bio_keys = [f"bio{i}" for i in range(1, 20)]
            # Reconstruct all values: bio1_mean at index 2, bio2_mean at 5, ...
            all_bio = {
                "bio1": bio1m, "bio2": r[5], "bio3": r[6], "bio4": r[7],
                "bio5": r[8], "bio6": r[9], "bio7": r[10],
                "bio8": r[11], "bio9": r[12], "bio10": r[13], "bio11": r[14],
                "bio12": bio12m, "bio13": r[18], "bio14": r[19],
                "bio15": r[20], "bio16": r[21], "bio17": r[22],
                "bio18": r[23], "bio19": r[24],
            }
            bio_items = []
            for k in bio_keys:
                lbl = BIO_LABELS.get(k, k)
                val = _fmt(all_bio.get(k), 1)
                bio_items.append(
                    ui.div(
                        ui.span(lbl, class_="bio-lbl"),
                        ui.span(val, class_="bio-val"),
                        class_="bio-item",
                    )
                )
            bio_grid = ui.div(
                ui.div("Todas as 19 Variáveis BIO", class_="qe-section-title"),
                ui.div(*bio_items, class_="bio-grid"),
            )

            return ui.div(cards, temp_panel, precip_panel, bio_grid)

        except Exception as e:
            return ui.div(str(e), class_="qe-err")

    # ── Climate global stats ─────────────────────────────────────────────
    @output
    @render.ui
    def clim_stats():
        if not _DB_OK:
            return _no_db()
        try:
            db = get_db()

            stats = db.execute("""
                SELECT COUNT(*), COUNT(bio1_mean), COUNT(bio12_mean),
                       ROUND(AVG(bio1_mean)::numeric, 1),
                       ROUND(MIN(bio1_mean)::numeric, 1),
                       ROUND(MAX(bio1_mean)::numeric, 1),
                       ROUND(AVG(bio12_mean)::numeric, 0)
                FROM tdwg_climate
            """)
            s = stats[0] if stats else [0]*7

            stat_cards = ui.div(
                _stat_card(f"{s[0]:,}" if s[0] else "—", "Regiões Total"),
                _stat_card(f"{_fmt(s[3])}°C", "Temp Média Global"),
                _stat_card(f"{_fmt(s[4])}°C", "Temp Mín Global"),
                _stat_card(f"{_fmt(s[5])}°C", "Temp Máx Global"),
                _stat_card(f"{_fmt(s[6], 0)} mm", "Precip Média Global"),
                class_="stat-grid",
            )

            # Biome breakdown
            biome_rows = db.execute("""
                SELECT whittaker_biome, COUNT(*),
                       ROUND(AVG(bio1_mean)::numeric, 1),
                       ROUND(AVG(bio12_mean)::numeric, 0)
                FROM tdwg_climate
                WHERE whittaker_biome IS NOT NULL
                GROUP BY whittaker_biome
                ORDER BY COUNT(*) DESC
            """)
            biome_tbl = ui.HTML(_html_table(
                ["bioma", "regiões", "temp média (°C)", "precip média (mm)"],
                biome_rows,
            ))

            # Köppen breakdown
            koppen_rows = db.execute("""
                SELECT koppen_zone, COUNT(*)
                FROM tdwg_climate
                WHERE koppen_zone IS NOT NULL
                GROUP BY koppen_zone
                ORDER BY COUNT(*) DESC
            """)
            koppen_tbl = ui.HTML(_html_table(["zona Köppen", "regiões"], koppen_rows))

            return ui.div(
                stat_cards,
                ui.div("Biomas (Whittaker)", class_="qe-section-title"),
                ui.div(biome_tbl, class_="qe-card"),
                ui.div("Zonas Köppen", class_="qe-section-title"),
                ui.div(koppen_tbl, class_="qe-card"),
            )
        except Exception as e:
            return ui.div(str(e), class_="qe-err")

    # ── Species climate profile ──────────────────────────────────────────
    @output
    @render.ui
    @reactive.event(input.clim_sp_go)
    def clim_species_result():
        if not _DB_OK:
            return _no_db()

        name = (input.clim_species() or "").strip()
        if not name:
            return ui.div("Informe o nome da espécie.", class_="qe-err")

        db = get_db()
        try:
            rows = db.execute("""
                SELECT s.id, s.canonical_name, COALESCE(s.family, ''),
                       COUNT(DISTINCT sr.tdwg_code),
                       ROUND(AVG(c.bio1_mean)::numeric, 1),
                       ROUND(MIN(c.bio1_min)::numeric, 1),
                       ROUND(MAX(c.bio1_max)::numeric, 1),
                       ROUND(AVG(c.bio12_mean)::numeric, 0),
                       ROUND(MIN(c.bio12_min)::numeric, 0),
                       ROUND(MAX(c.bio12_max)::numeric, 0),
                       ROUND(AVG(c.aridity_index)::numeric, 1),
                       MODE() WITHIN GROUP (ORDER BY c.whittaker_biome),
                       MODE() WITHIN GROUP (ORDER BY c.koppen_zone)
                FROM species s
                JOIN species_regions sr ON s.id = sr.species_id AND sr.is_native = TRUE
                LEFT JOIN tdwg_climate c ON sr.tdwg_code = c.tdwg_code
                WHERE s.canonical_name ILIKE :name AND c.bio1_mean IS NOT NULL
                GROUP BY s.id, s.canonical_name, s.family
            """, {"name": name})

            if not rows:
                return ui.div("Espécie não encontrada ou sem dados climáticos.", class_="qe-err")

            r = rows[0]
            sp_id, cname, family = r[0], r[1], r[2]
            n_regions = r[3]
            temp_avg, temp_min, temp_max = r[4], r[5], r[6]
            precip_avg, precip_min, precip_max = r[7], r[8], r[9]
            aridity, dom_biome, dom_koppen = r[10], r[11], r[12]

            # Get list of biomes
            biome_rows = db.execute("""
                SELECT DISTINCT c.whittaker_biome
                FROM species s
                JOIN species_regions sr ON s.id = sr.species_id AND sr.is_native = TRUE
                JOIN tdwg_climate c ON sr.tdwg_code = c.tdwg_code
                WHERE s.id = :sid AND c.whittaker_biome IS NOT NULL
                ORDER BY c.whittaker_biome
            """, {"sid": sp_id})
            biomes = [b[0] for b in biome_rows]

            header = ui.div(
                ui.tags.h4(f"{cname}", style="color:#34d399;margin:0"),
                ui.p(f"Família: {family} · {n_regions} regiões nativas",
                     style="color:#888;font-size:0.85em;margin:4px 0 12px"),
            )

            cards = ui.div(
                _stat_card(dom_biome or "—", "Bioma Dominante", "#a78bfa"),
                _stat_card(dom_koppen or "—", "Köppen Dominante", "#f59e0b"),
                _stat_card(_fmt(aridity), "Aridez Média", "#ec4899"),
                _stat_card(str(n_regions), "Regiões Nativas", "#22d3ee"),
                class_="climate-grid",
            )

            range_tbl = _html_table(
                ["", "Média", "Mínima", "Máxima"],
                [
                    ("Temperatura (°C)", _fmt(temp_avg), _fmt(temp_min), _fmt(temp_max)),
                    ("Precipitação (mm)", _fmt(precip_avg, 0), _fmt(precip_min, 0), _fmt(precip_max, 0)),
                ],
            )

            biome_list = ", ".join(biomes) if biomes else "—"

            return ui.div(
                header, cards,
                ui.div(ui.HTML(range_tbl), class_="qe-card", style="margin-bottom:12px"),
                ui.p(f"Biomas: {biome_list}", style="color:#888;font-size:0.85em"),
            )

        except Exception as e:
            return ui.div(str(e), class_="qe-err")
