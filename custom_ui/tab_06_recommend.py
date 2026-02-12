"""Climate-Adapted Species Recommendation tab UI."""
from shiny import ui
import faicons as fa
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

GROWTH_FORM_CHOICES = {
    "tree": t("Árvore", "Tree"),
    "shrub": t("Arbusto", "Shrub"),
    "subshrub": t("Sub-arbusto", "Subshrub"),
    "forb": t("Herbácea", "Forb"),
    "graminoid": t("Gramínea", "Graminoid"),
    "palm": t("Palmeira", "Palm"),
    "bamboo": t("Bambu", "Bamboo"),
    "liana": t("Liana", "Liana"),
    "vine": t("Trepadeira", "Vine"),
    "scrambler": t("Escandente", "Scrambler"),
    "other": t("Outro", "Other"),
}

recommend = ui.nav_panel(
    tab_title(5, "Recomendar", "Recommend"),
    ui.page_fluid(
        ui.h2(t("Filtro de Espécies Adaptadas ao Clima", "Climate-Adapted Species Filter")),
        ui.p(
            t(
                "Gere recomendações diversificadas de espécies adaptadas ao clima da sua localização. "
                "O algoritmo maximiza a diversidade funcional enquanto filtra por compatibilidade climática.",
                "Generate diverse species recommendations adapted to your location's climate. "
                "The algorithm maximizes functional diversity while filtering for climate compatibility.",
            ),
            class_="text-muted",
        ),

        ui.row(
            # Left column: inputs
            ui.column(
                4,
                ui.card(
                    ui.card_header(t("Localização", "Location")),
                    ui.card_body(
                        ui.input_text(
                            "rec_tdwg_code",
                            t("Código TDWG / Estado:", "TDWG Code / State:"),
                            placeholder="e.g. BZS, BR-SP",
                        ),
                        ui.p(t("-- ou --", "-- or --"), class_="text-center text-muted my-2"),
                        ui.row(
                            ui.column(
                                6,
                                ui.input_numeric(
                                    "rec_lat",
                                    t("Latitude:", "Latitude:"),
                                    value=None,
                                    min=-90, max=90, step=0.01,
                                ),
                            ),
                            ui.column(
                                6,
                                ui.input_numeric(
                                    "rec_lon",
                                    t("Longitude:", "Longitude:"),
                                    value=None,
                                    min=-180, max=180, step=0.01,
                                ),
                            ),
                        ),
                    ),
                ),
                ui.card(
                    ui.card_header(t("Parâmetros", "Parameters")),
                    ui.card_body(
                        ui.input_switch(
                            "rec_all_species",
                            t("Retornar todas as espécies", "Return all species"),
                            value=True,
                        ),
                        ui.panel_conditional(
                            "!input.rec_all_species",
                            ui.input_slider(
                                "rec_n_species",
                                t("Número de espécies:", "Number of species:"),
                                min=5, max=500, value=50, step=5,
                            ),
                        ),
                        ui.input_slider(
                            "rec_climate_threshold",
                            t("Limiar climático:", "Climate threshold:"),
                            min=0.0, max=0.9, value=0.3, step=0.05,
                        ),
                    ),
                ),
                ui.card(
                    ui.card_header(t("Formas de Crescimento", "Growth Forms")),
                    ui.card_body(
                        ui.input_checkbox_group(
                            "rec_growth_forms",
                            t("Incluir (deixe vazio para todos):", "Include (leave empty for all):"),
                            choices=GROWTH_FORM_CHOICES,
                        ),
                    ),
                ),
                ui.card(
                    ui.card_header(t("Filtros", "Filters")),
                    ui.card_body(
                        ui.input_switch(
                            "rec_nitrogen_fixers",
                            t("Apenas fixadores de nitrogênio", "Nitrogen fixers only"),
                            value=False,
                        ),
                        ui.input_switch(
                            "rec_exclude_threatened",
                            t("Excluir espécies ameaçadas", "Exclude threatened species"),
                            value=False,
                        ),
                        ui.input_switch(
                            "rec_include_introduced",
                            t("Incluir espécies introduzidas", "Include introduced species"),
                            value=False,
                        ),
                        ui.input_switch(
                            "rec_endemics_only",
                            t("Apenas endêmicas", "Endemics only"),
                            value=False,
                        ),
                    ),
                ),
                ui.input_action_button(
                    "rec_generate",
                    t("Gerar Recomendações", "Generate Recommendations"),
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

        nav_buttons(back_value="tab_results"),

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
    value="tab_recommend",
)
