"""Admin Tab — Recommendation Engine with Gower distance diversity maximization.

Full port of recommendation.go (~500 lines) to Python.
"""
import math
from shiny import reactive, render, ui
from .helpers import (
    _DB_OK, _html_table, _fmt, _stat_card, _no_db, get_db,
    VALID_GROWTH_FORMS, STATE_TO_TDWG,
)


# ── Gower Distance ───────────────────────────────────────────────────────────

def _gower_distance(a: dict, b: dict) -> float:
    """Compute Gower distance between two trait vectors (11 features)."""
    cat_diffs = 0.0
    for k in ("is_tree", "is_shrub", "is_herb", "is_climber", "is_palm",
              "is_nitrogen_fixer", "dispersal_animal", "dispersal_wind"):
        if a.get(k, False) != b.get(k, False):
            cat_diffs += 1.0
    cont_diffs = (
        abs(a.get("height_norm", 0.25) - b.get("height_norm", 0.25))
        + abs(a.get("lifespan_norm", 0.3) - b.get("lifespan_norm", 0.3))
    )
    family_diff = 1.0 if a.get("family_code", 0) != b.get("family_code", 0) else 0.0
    return (cat_diffs + cont_diffs + family_diff) / 11.0


def _marginal_diversity(selected_traits, candidate_trait, all_traits):
    """Min Gower distance from candidate to any already-selected species."""
    if not selected_traits:
        return 1.0
    min_d = 1.0
    for sid in selected_traits:
        d = _gower_distance(candidate_trait, all_traits[sid])
        if d < min_d:
            min_d = d
    return min_d


def _greedy_select(candidates, traits, n):
    """Greedy diversity maximization: pick n species from candidates."""
    if not candidates or n <= 0:
        return candidates

    selected = [candidates[0]]
    selected_ids = {candidates[0]["species_id"]}
    remaining = candidates[1:]

    while len(selected) < n and remaining:
        best_idx, best_score = -1, -1.0
        for i, c in enumerate(remaining):
            sid = c["species_id"]
            ct = traits.get(sid, {})
            div_gain = _marginal_diversity(selected_ids, ct, traits)
            combined = div_gain * 0.7 + c.get("climate_score", 0) * 0.3
            if combined > best_score:
                best_score = combined
                best_idx = i
        if best_idx >= 0:
            pick = remaining.pop(best_idx)
            selected.append(pick)
            selected_ids.add(pick["species_id"])
        else:
            break

    for i, sp in enumerate(selected):
        sp["rank"] = i + 1
        if i == 0:
            sp["diversity_contribution"] = 1.0
        else:
            ct = traits.get(sp["species_id"], {})
            prev_ids = {s["species_id"] for s in selected[:i]}
            sp["diversity_contribution"] = _marginal_diversity(prev_ids, ct, traits)

    return selected


def _calc_metrics(species, traits):
    """Calculate diversity metrics for selected species."""
    if not species:
        return {}
    families = {s["family"] for s in species}
    gforms = {s["growth_form"] for s in species}

    total_d, pairs = 0.0, 0
    for i in range(len(species)):
        for j in range(i + 1, len(species)):
            total_d += _gower_distance(
                traits.get(species[i]["species_id"], {}),
                traits.get(species[j]["species_id"], {}),
            )
            pairs += 1
    func_div = total_d / pairs if pairs else 0.0
    phylo_div = len(families) / len(species) if species else 0.0
    gf_rich = len(gforms) / 5.0
    total_score = func_div * 0.5 + phylo_div * 0.25 + gf_rich * 0.25

    return {
        "functional_diversity": round(func_div, 3),
        "phylogenetic_diversity": round(phylo_div, 3),
        "growth_form_richness": round(gf_rich, 3),
        "total_diversity_score": round(total_score, 3),
        "n_species": len(species),
        "n_families": len(families),
        "n_growth_forms": len(gforms),
    }


# ── UI / Server ──────────────────────────────────────────────────────────────

def recommend_ui():
    gf_choices = {g: g for g in VALID_GROWTH_FORMS}
    return ui.nav_panel(
        "Recomendação",
        ui.row(
            ui.column(3, ui.input_text("rec_tdwg", "TDWG / Estado:", placeholder="BZS ou BR-SC")),
            ui.column(2, ui.input_numeric("rec_lat", "Latitude:", value=None)),
            ui.column(2, ui.input_numeric("rec_lon", "Longitude:", value=None)),
            ui.column(2, ui.input_numeric("rec_n", "N Espécies:", value=20, min=1, max=200)),
            ui.column(3,
                ui.input_slider("rec_threshold", "Climate Threshold:",
                                min=0.3, max=1.0, value=0.6, step=0.05),
            ),
        ),
        ui.row(
            ui.column(9,
                ui.input_checkbox_group(
                    "rec_gf", "Growth Forms (filtrar):",
                    choices=gf_choices, inline=True,
                ),
            ),
            ui.column(3,
                ui.input_action_button("rec_go", "Recomendar",
                                       class_="btn btn-success",
                                       style="margin-top:25px;width:100%"),
            ),
        ),
        ui.row(
            ui.column(3, ui.input_checkbox("rec_introduced", "Incluir introduzidas", value=False)),
            ui.column(3, ui.input_checkbox("rec_nfixer", "Apenas fixadoras N", value=False)),
            ui.column(3, ui.input_checkbox("rec_endemic", "Apenas endêmicas", value=False)),
            ui.column(3,
                ui.input_checkbox("rec_no_threat", "Excluir ameaçadas", value=False),
            ),
        ),
        ui.row(
            ui.column(3, ui.input_numeric("rec_min_h", "Altura mín (m):", value=None)),
            ui.column(3, ui.input_numeric("rec_max_h", "Altura máx (m):", value=None)),
        ),
        ui.output_ui("rec_result"),
    )


def recommend_server(input, output, session):

    @output
    @render.ui
    @reactive.event(input.rec_go)
    def rec_result():
        if not _DB_OK:
            return _no_db()

        db = get_db()
        try:
            # ── 1. Resolve location ──────────────────────────────────────
            tdwg_input = (input.rec_tdwg() or "").strip().upper()
            lat = input.rec_lat()
            lon = input.rec_lon()

            loc_code = None
            loc_name = ""
            bio1 = bio5 = bio6 = bio12 = bio15 = None

            if tdwg_input:
                # Check if it's a state code
                if tdwg_input in STATE_TO_TDWG:
                    tdwg_input = STATE_TO_TDWG[tdwg_input]

                rows = db.execute("""
                    SELECT c.tdwg_code, COALESCE(t.level3_name, c.tdwg_code),
                           c.bio1_mean, c.bio5_mean, c.bio6_mean, c.bio12_mean, c.bio15_mean
                    FROM tdwg_climate c
                    LEFT JOIN tdwg_level3 t ON c.tdwg_code = t.level3_code
                    WHERE c.tdwg_code = :code
                """, {"code": tdwg_input})
                if not rows:
                    return ui.div(f"TDWG '{tdwg_input}' não encontrado.", class_="qe-err")
                r = rows[0]
                loc_code, loc_name = r[0], r[1]
                bio1, bio5, bio6, bio12, bio15 = r[2], r[3], r[4], r[5], r[6]

            elif lat is not None and lon is not None:
                from database.connection import get_tdwg_by_coords, get_bioclim_at_coords
                tdwg = get_tdwg_by_coords(lat, lon)
                if not tdwg:
                    return ui.div("Coordenadas fora de regiões TDWG.", class_="qe-err")
                loc_code = tdwg["level3_code"]
                loc_name = tdwg["level3_name"]
                bioclim = get_bioclim_at_coords(lat, lon)
                if bioclim:
                    bio1 = bioclim["bio1"]
                    bio5 = bioclim["bio5"]
                    bio6 = bioclim["bio6"]
                    bio12 = bioclim["bio12"]
                    bio15 = bioclim["bio15"]
                else:
                    # Fallback to TDWG climate
                    rows = db.execute("""
                        SELECT bio1_mean, bio5_mean, bio6_mean, bio12_mean, bio15_mean
                        FROM tdwg_climate WHERE tdwg_code = :code
                    """, {"code": loc_code})
                    if rows:
                        bio1, bio5, bio6, bio12, bio15 = rows[0]
            else:
                return ui.div("Informe TDWG/estado ou coordenadas.", class_="qe-err")

            if bio1 is None:
                return ui.div("Sem dados climáticos para esta localização.", class_="qe-err")

            n_species = int(input.rec_n() or 20)
            threshold = float(input.rec_threshold())
            growth_forms = list(input.rec_gf() or [])
            include_introduced = input.rec_introduced()
            nfixer_only = input.rec_nfixer()
            endemic_only = input.rec_endemic()
            no_threat = input.rec_no_threat()
            min_h = input.rec_min_h()
            max_h = input.rec_max_h()

            # ── 2. Query climate-adapted candidates ──────────────────────
            native_clause = "AND sr.is_native = TRUE"
            if include_introduced:
                native_clause = "AND (sr.is_native = TRUE OR sr.is_introduced = TRUE)"

            where_extra = ""
            if growth_forms:
                gf_list = ", ".join(f"'{g}'" for g in growth_forms if g in VALID_GROWTH_FORMS)
                if gf_list:
                    where_extra += f" AND su.growth_form IN ({gf_list})"
            if no_threat:
                where_extra += " AND (su.threat_status IS NULL OR su.threat_status NOT IN ('CR', 'EN', 'VU'))"
            if nfixer_only:
                where_extra += " AND tv.is_nitrogen_fixer = TRUE"
            if endemic_only:
                where_extra += " AND sr.is_endemic = TRUE"
            if min_h is not None:
                where_extra += f" AND su.max_height_m >= {float(min_h)}"
            if max_h is not None:
                where_extra += f" AND su.max_height_m <= {float(max_h)}"

            params = {
                "bio1": float(bio1), "bio5": float(bio5), "bio6": float(bio6),
                "bio12": float(bio12), "bio15": float(bio15),
                "tdwg": loc_code, "threshold": threshold,
            }

            candidates_rows = db.execute(f"""
                SELECT s.id, s.canonical_name,
                       COALESCE(s.family, 'Unknown') as family,
                       COALESCE(su.growth_form, 'unknown') as growth_form,
                       su.max_height_m, su.lifespan_years,
                       COALESCE(tv.is_nitrogen_fixer, false) as is_n_fixer,
                       su.threat_status,
                       COALESCE(sr.is_native, false) as is_native,
                       calculate_climate_match(s.id, :bio1, :bio5, :bio6, :bio12, :bio15) as climate_score,
                       cn_pt.common_name as common_name_pt
                FROM species s
                JOIN species_unified su ON s.id = su.species_id
                JOIN species_regions sr ON s.id = sr.species_id
                JOIN species_climate_envelope_unified sce ON s.id = sce.species_id
                LEFT JOIN species_trait_vectors tv ON s.id = tv.species_id
                LEFT JOIN common_names cn_pt ON s.id = cn_pt.species_id AND cn_pt.language = 'pt'
                WHERE sr.tdwg_code = :tdwg
                  {native_clause}
                  AND su.growth_form IS NOT NULL
                  AND calculate_climate_match(s.id, :bio1, :bio5, :bio6, :bio12, :bio15) >= :threshold
                  {where_extra}
                ORDER BY climate_score DESC
            """, params)

            if not candidates_rows:
                return ui.div(
                    "Nenhuma espécie encontrada. Tente reduzir o threshold.",
                    class_="qe-err",
                )

            candidates = []
            for r in candidates_rows:
                candidates.append({
                    "species_id": r[0],
                    "canonical_name": r[1],
                    "family": r[2],
                    "growth_form": r[3],
                    "max_height_m": r[4],
                    "lifespan_years": r[5],
                    "is_n_fixer": r[6],
                    "threat_status": r[7],
                    "is_native": r[8],
                    "climate_score": float(r[9]) if r[9] is not None else 0.5,
                    "common_name_pt": r[10],
                })

            # ── 3. Load trait vectors ────────────────────────────────────
            sp_ids = [c["species_id"] for c in candidates]
            # Build parameterized query for trait vectors
            id_placeholders = ", ".join(f":id{i}" for i in range(len(sp_ids)))
            tv_params = {f"id{i}": sid for i, sid in enumerate(sp_ids)}

            tv_rows = db.execute(f"""
                SELECT species_id,
                       COALESCE(is_tree, false), COALESCE(is_shrub, false),
                       COALESCE(is_herb, false), COALESCE(is_climber, false),
                       COALESCE(is_palm, false), COALESCE(is_nitrogen_fixer, false),
                       COALESCE(height_normalized, 0.25), COALESCE(lifespan_normalized, 0.3),
                       COALESCE(dispersal_animal, false), COALESCE(dispersal_wind, false),
                       COALESCE(family_code, 0)
                FROM species_trait_vectors
                WHERE species_id IN ({id_placeholders})
            """, tv_params)

            traits = {}
            for r in tv_rows:
                traits[r[0]] = {
                    "is_tree": r[1], "is_shrub": r[2], "is_herb": r[3],
                    "is_climber": r[4], "is_palm": r[5], "is_nitrogen_fixer": r[6],
                    "height_norm": float(r[7]) if r[7] else 0.25,
                    "lifespan_norm": float(r[8]) if r[8] else 0.3,
                    "dispersal_animal": r[9], "dispersal_wind": r[10],
                    "family_code": r[11],
                }

            # ── 4. Greedy diversity selection ────────────────────────────
            if n_species > 0 and n_species < len(candidates):
                selected = _greedy_select(candidates, traits, n_species)
            else:
                selected = candidates
                for i, sp in enumerate(selected):
                    sp["rank"] = i + 1
                    sp["diversity_contribution"] = 0.0

            # ── 5. Metrics ───────────────────────────────────────────────
            metrics = _calc_metrics(selected, traits)

            # ── 6. Render ────────────────────────────────────────────────
            loc_card = ui.div(
                _stat_card(f"{loc_code}", "TDWG"),
                _stat_card(loc_name, "Região"),
                _stat_card(f"{len(candidates_rows):,}", "Candidatos"),
                _stat_card(f"{len(selected)}", "Selecionados"),
                class_="stat-grid",
                style="margin-bottom:16px",
            )

            metric_cards = ui.div(
                ui.div(
                    ui.div(f"{metrics.get('total_diversity_score', 0):.3f}", class_="val",
                           style="color:#34d399"),
                    ui.div("Diversity Score", class_="lbl"),
                    class_="metric-card",
                ),
                ui.div(
                    ui.div(f"{metrics.get('functional_diversity', 0):.3f}", class_="val",
                           style="color:#22d3ee"),
                    ui.div("Functional Div", class_="lbl"),
                    class_="metric-card",
                ),
                ui.div(
                    ui.div(f"{metrics.get('phylogenetic_diversity', 0):.3f}", class_="val",
                           style="color:#a78bfa"),
                    ui.div(f"Phylo Div ({metrics.get('n_families', 0)} fam)", class_="lbl"),
                    class_="metric-card",
                ),
                ui.div(
                    ui.div(f"{metrics.get('growth_form_richness', 0):.3f}", class_="val",
                           style="color:#f59e0b"),
                    ui.div(f"GF Richness ({metrics.get('n_growth_forms', 0)})", class_="lbl"),
                    class_="metric-card",
                ),
                class_="metrics-row",
            )

            # Table
            table_rows = []
            for sp in selected:
                table_rows.append((
                    sp.get("rank", ""),
                    sp["canonical_name"],
                    sp["family"],
                    sp["growth_form"],
                    f"{sp['climate_score']*100:.0f}%",
                    f"{sp.get('diversity_contribution', 0):.3f}",
                    "Yes" if sp.get("is_n_fixer") else "",
                    sp.get("threat_status") or "",
                    sp.get("common_name_pt") or "",
                ))

            tbl = ui.HTML(_html_table(
                ["#", "espécie", "família", "growth_form", "clima %", "diversidade", "N-fix", "ameaça", "nome PT"],
                table_rows,
            ))

            return ui.div(loc_card, metric_cards, ui.div(tbl, class_="qe-card"))

        except Exception as e:
            return ui.div(str(e), class_="qe-err")
