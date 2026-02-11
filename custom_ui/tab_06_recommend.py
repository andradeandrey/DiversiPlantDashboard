"""Climate-Adapted Species Recommendation tab UI."""
from shiny import ui
import faicons as fa

GROWTH_FORM_CHOICES = {
    "tree": "Tree",
    "shrub": "Shrub",
    "subshrub": "Subshrub",
    "forb": "Forb",
    "graminoid": "Graminoid",
    "palm": "Palm",
    "bamboo": "Bamboo",
    "liana": "Liana",
    "vine": "Vine",
    "scrambler": "Scrambler",
    "other": "Other",
}

recommend = ui.nav_panel(
    ui.div(
        fa.icon_svg("seedling"),
        ui.span(" Recommend", style="margin-left: 6px;"),
        class_="d-flex align-items-center",
    ),
    ui.page_fluid(
        ui.h2("Climate-Adapted Species Filter"),
        ui.p(
            "Generate diverse species recommendations adapted to your location's climate. "
            "The algorithm maximizes functional diversity while filtering for climate compatibility.",
            class_="text-muted",
        ),

        ui.row(
            # Left column: inputs
            ui.column(
                4,
                ui.card(
                    ui.card_header("Location"),
                    ui.card_body(
                        ui.input_text(
                            "rec_tdwg_code",
                            "TDWG Code / State:",
                            placeholder="e.g. BZS, BR-SP",
                        ),
                        ui.p("-- or --", class_="text-center text-muted my-2"),
                        ui.row(
                            ui.column(
                                6,
                                ui.input_numeric(
                                    "rec_lat", "Latitude:", value=None,
                                    min=-90, max=90, step=0.01,
                                ),
                            ),
                            ui.column(
                                6,
                                ui.input_numeric(
                                    "rec_lon", "Longitude:", value=None,
                                    min=-180, max=180, step=0.01,
                                ),
                            ),
                        ),
                    ),
                ),
                ui.card(
                    ui.card_header("Parameters"),
                    ui.card_body(
                        ui.input_slider(
                            "rec_n_species",
                            "Number of species:",
                            min=5, max=100, value=20, step=5,
                        ),
                        ui.input_slider(
                            "rec_climate_threshold",
                            "Climate threshold:",
                            min=0.3, max=0.9, value=0.6, step=0.05,
                        ),
                    ),
                ),
                ui.card(
                    ui.card_header("Growth Forms"),
                    ui.card_body(
                        ui.input_checkbox_group(
                            "rec_growth_forms",
                            "Include (leave empty for all):",
                            choices=GROWTH_FORM_CHOICES,
                        ),
                    ),
                ),
                ui.card(
                    ui.card_header("Filters"),
                    ui.card_body(
                        ui.input_switch("rec_nitrogen_fixers", "Nitrogen fixers only", value=False),
                        ui.input_switch("rec_exclude_threatened", "Exclude threatened species", value=False),
                        ui.input_switch("rec_include_introduced", "Include introduced species", value=False),
                        ui.input_switch("rec_endemics_only", "Endemics only", value=False),
                    ),
                ),
                ui.input_action_button(
                    "rec_generate",
                    "Generate Recommendations",
                    class_="btn-success btn-lg w-100 mt-2",
                ),
            ),

            # Right column: results
            ui.column(
                8,
                ui.output_ui("rec_loading_indicator"),
                ui.output_ui("rec_results_section"),
            ),
        ),

        # Inline CSS
        ui.tags.style("""
            .rec-metric-card {
                text-align: center;
                padding: 15px;
            }
            .rec-metric-value {
                font-size: 1.8em;
                font-weight: bold;
                color: #27ae60;
            }
            .rec-metric-label {
                font-size: 0.85em;
                color: #7f8c8d;
            }
            .rec-nfix-badge {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.75em;
                font-weight: bold;
                background-color: #27ae60;
                color: white;
            }
        """),
    ),
)
