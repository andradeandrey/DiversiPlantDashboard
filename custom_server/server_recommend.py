"""Server logic for the Climate-Adapted Species Recommendation tab."""
from shiny import render, reactive, ui
import httpx
import json

import os
GO_API_URL = os.environ.get("GO_API_URL", "http://127.0.0.1:8080/api/recommend")


def server_recommend(input, output, session):
    """Server logic for recommend tab."""

    # Reactive value to store results
    rec_data = reactive.Value(None)
    rec_error = reactive.Value(None)
    rec_loading = reactive.Value(False)

    @reactive.effect
    @reactive.event(input.rec_generate)
    async def _do_recommend():
        rec_loading.set(True)
        rec_error.set(None)
        rec_data.set(None)

        # Build request payload
        n_species = 0 if input.rec_all_species() else input.rec_n_species()
        payload = {
            "n_species": n_species,
            "climate_threshold": input.rec_climate_threshold(),
            "preferences": {},
        }

        # Location
        tdwg_or_state = (input.rec_tdwg_code() or "").strip()
        lat = input.rec_lat()
        lon = input.rec_lon()

        if tdwg_or_state:
            if "-" in tdwg_or_state:
                payload["state_code"] = tdwg_or_state.upper()
            else:
                payload["tdwg_code"] = tdwg_or_state.upper()
        elif lat is not None and lon is not None:
            payload["latitude"] = float(lat)
            payload["longitude"] = float(lon)
        else:
            rec_loading.set(False)
            rec_error.set("Please provide a TDWG code, state code, or lat/lon coordinates.")
            return

        # Growth forms
        growth_forms = list(input.rec_growth_forms())
        if growth_forms:
            payload["preferences"]["growth_forms"] = growth_forms

        # Filters
        if input.rec_nitrogen_fixers():
            payload["preferences"]["nitrogen_fixers_only"] = True
        if input.rec_exclude_threatened():
            payload["preferences"]["include_threatened"] = False
        if input.rec_include_introduced():
            payload["preferences"]["include_introduced"] = True
        if input.rec_endemics_only():
            payload["preferences"]["endemics_only"] = True

        import logging
        logging.warning(f"[RECOMMEND] Payload: {json.dumps(payload)}")

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(GO_API_URL, json=payload)

            if resp.status_code != 200:
                error_text = resp.text
                try:
                    error_text = resp.json().get("error", resp.text)
                except Exception:
                    pass
                rec_error.set(f"API error ({resp.status_code}): {error_text}")
            else:
                rec_data.set(resp.json())
        except httpx.ConnectError:
            rec_error.set(
                "Cannot connect to the Go API server (port 8080). "
                "Make sure the query-explorer server is running."
            )
        except Exception as e:
            rec_error.set(f"Request failed: {e}")
        finally:
            rec_loading.set(False)

    # ==========================================
    # Loading indicator
    # ==========================================
    @output
    @render.ui
    def rec_loading_indicator():
        if rec_loading():
            return ui.div(
                ui.div(
                    ui.span(class_="spinner-border spinner-border-sm me-2"),
                    "Generating recommendations...",
                    class_="d-flex align-items-center",
                ),
                class_="alert alert-info",
            )
        return ui.div()

    # ==========================================
    # Results section
    # ==========================================
    @output
    @render.ui
    def rec_results_section():
        error = rec_error()
        if error:
            return ui.div(
                ui.strong("Error: "),
                error,
                class_="alert alert-danger",
            )

        data = rec_data()
        if data is None:
            return ui.div(
                ui.div(
                    ui.h4("How it works"),
                    ui.tags.ol(
                        ui.tags.li("Enter a location (TDWG code like BZS, state like BR-SP, or coordinates)"),
                        ui.tags.li("Adjust parameters and filters as needed"),
                        ui.tags.li("Click Generate to get climate-adapted, functionally diverse species"),
                    ),
                    class_="text-muted mt-3",
                ),
            )

        metrics = data.get("diversity_metrics", {})
        location = data.get("location_info", {})
        species_list = data.get("species", [])
        query_time = data.get("query_time", "")

        # Metric cards
        metric_cards = ui.row(
            _metric_card("Functional Diversity", f"{metrics.get('functional_diversity', 0):.3f}", 4),
            _metric_card("Families", str(metrics.get("n_families", 0)), 2),
            _metric_card("Growth Forms", str(metrics.get("n_growth_forms", 0)), 2),
            _metric_card("Total Score", f"{metrics.get('total_diversity_score', 0):.3f}", 4),
        )

        # Location info
        location_info = ui.div(
            ui.strong("Location: "),
            f"{location.get('tdwg_name', '')} ({location.get('tdwg_code', '')})",
            ui.span(f" | {len(species_list)} species | {query_time}", class_="text-muted ms-2"),
            class_="mb-3",
        )

        # Growth form summary
        from collections import Counter
        gf_counts = Counter(sp.get("growth_form", "") for sp in species_list)
        gf_summary = ", ".join(f"{k}: {v}" for k, v in gf_counts.most_common())

        # Species table (show first 500 to avoid browser freeze)
        MAX_DISPLAY = 500
        display_list = species_list[:MAX_DISPLAY]
        table_rows = []
        for i, sp in enumerate(display_list, 1):
            climate_pct = sp.get("climate_match_score", 0) * 100
            diversity_pct = sp.get("diversity_contribution", 0) * 100
            nfix = ui.span("N-Fix", class_="rec-nfix-badge") if sp.get("is_nitrogen_fixer") else ""
            threat = sp.get("threat_status") or ""
            native_badge = "Native" if sp.get("is_native") else "Introduced"

            table_rows.append(
                ui.tags.tr(
                    ui.tags.td(str(i)),
                    ui.tags.td(
                        ui.tags.em(sp.get("canonical_name", "")),
                        ui.br() if sp.get("common_name_pt") else "",
                        ui.small(sp["common_name_pt"], class_="text-muted") if sp.get("common_name_pt") else "",
                    ),
                    ui.tags.td(sp.get("family", "")),
                    ui.tags.td(sp.get("growth_form", "")),
                    ui.tags.td(f"{climate_pct:.1f}%"),
                    ui.tags.td(f"{diversity_pct:.1f}%"),
                    ui.tags.td(nfix),
                    ui.tags.td(threat),
                    ui.tags.td(native_badge),
                )
            )

        species_table = ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("#"),
                    ui.tags.th("Species"),
                    ui.tags.th("Family"),
                    ui.tags.th("Growth Form"),
                    ui.tags.th("Climate Match"),
                    ui.tags.th("Diversity+"),
                    ui.tags.th("N-Fix"),
                    ui.tags.th("Threat"),
                    ui.tags.th("Status"),
                )
            ),
            ui.tags.tbody(*table_rows),
            class_="table table-striped table-hover",
        )

        truncation_note = ui.div()
        if len(species_list) > MAX_DISPLAY:
            truncation_note = ui.div(
                ui.p(
                    f"Showing first {MAX_DISPLAY} of {len(species_list)} species. "
                    f"Use growth form filters to narrow results.",
                    class_="text-warning",
                    style="font-weight: 500;",
                ),
            )

        gf_info = ui.div(
            ui.strong("Growth forms: "),
            gf_summary,
            class_="mb-2 text-muted",
            style="font-size: 0.9em;",
        )

        return ui.div(
            metric_cards,
            ui.hr(),
            location_info,
            gf_info,
            truncation_note,
            species_table,
        )


def _metric_card(label, value, width):
    """Helper to create a metric card."""
    return ui.column(
        width,
        ui.card(
            ui.card_body(
                ui.div(value, class_="rec-metric-value"),
                ui.div(label, class_="rec-metric-label"),
                class_="rec-metric-card",
            ),
        ),
    )
