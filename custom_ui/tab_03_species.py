"""Species / Espécies tab — matches Figma design."""
import os
from shiny import ui, App
from pathlib import Path
from shinywidgets import output_widget
from custom_server.agroforestry_server import get_Plants
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

FILE_NAME = os.path.join(
    Path(__file__).parent.parent, "data", "MgmtTraitData_updated.csv"
)

# Growth form symbols for the legend modal (matching Figma screenshot 7)
_SYMBOLS = [
    ("Arbusto", "Shrub", "#6cb043", "●"),
    ("Sub-arbusto", "Subshrub", "#8B0A50", "■"),
    ("Trepadeira herbácea", "Herbaceous climber", "#E91E63", "S"),
    ("Gramíneas e afins", "Graminoids", "#2E7D32", "≋"),
    ("Árvore", "Tree", "#AD1457", "♣"),
    ("Herbáceas", "Herbs", "#F57C00", "△"),
    ("Palmeira", "Palm", "#4CAF50", "¥"),
    ("Bambu", "Bamboo", "#BF360C", "¥"),
    ("Trepadeira lenhosa", "Woody climber", "#880E4F", "S"),
    ("Rasteira", "Creeper", "#1B5E20", "···"),
    ("Outro", "Other", "#757575", "◎"),
]


def _symbol_badge(pt, en, color, icon):
    return ui.span(
        ui.span(icon, style=f"margin-right: 4px;"),
        ui.span(pt, class_="i18n-pt"),
        ui.span(en, class_="i18n-en"),
        class_="symbol-badge",
        style=f"background-color: {color}; color: white; padding: 4px 10px; "
              f"border-radius: 4px; margin: 3px; display: inline-block; font-size: 0.85em; font-weight: 600;",
    )


main_species = ui.nav_panel(
    tab_title(3, "Espécies", "Species"),
    ui.page_fluid(
        # Search input — centered
        ui.div(
            ui.input_selectize(
                "overview_plants",
                "",
                choices=get_Plants(FILE_NAME),
                multiple=True,
                options={
                    "placeholder": "Digite aqui as espécies que você gostaria de plantar...",
                    "create": True,
                },
            ),
            class_="species-search-bar",
        ),

        # Filter dropdowns row
        ui.div(
            ui.div(
                ui.input_select(
                    "filter_growth_form",
                    "",
                    choices={
                        "": "Forma de crescimento",
                        "tree": "Árvore",
                        "shrub": "Arbusto",
                        "subshrub": "Sub-arbusto",
                        "forb": "Herbácea (forb)",
                        "graminoid": "Gramínea",
                        "climber": "Trepadeira",
                        "palm": "Palmeira",
                        "bamboo": "Bambu",
                        "cactus": "Cacto",
                    },
                ),
                class_="species-filter-item",
            ),
            ui.div(
                ui.input_select(
                    "filter_plant_use",
                    "",
                    choices={
                        "": "Uso da planta",
                        "food": "Alimento",
                        "timber": "Madeira",
                        "medicinal": "Medicinal",
                        "ornamental": "Ornamental",
                        "fodder": "Forragem",
                    },
                ),
                class_="species-filter-item",
            ),
            ui.div(
                ui.input_select(
                    "filter_threat",
                    "",
                    choices={
                        "": "Ameaça à conservação",
                        "LC": "Pouco preocupante (LC)",
                        "NT": "Quase ameaçada (NT)",
                        "VU": "Vulnerável (VU)",
                        "EN": "Em perigo (EN)",
                        "CR": "Criticamente em perigo (CR)",
                    },
                ),
                class_="species-filter-item",
            ),
            ui.div(
                ui.input_select(
                    "filter_nfix",
                    "",
                    choices={
                        "": "Fixador biológico de N",
                        "yes": "Sim",
                        "no": "Não",
                    },
                ),
                class_="species-filter-item",
            ),
            ui.div(
                ui.input_select(
                    "filter_deciduousness",
                    "",
                    choices={
                        "": "Deciduidade",
                        "deciduous": "Decídua",
                        "evergreen": "Perene",
                        "semi": "Semi-decídua",
                    },
                ),
                class_="species-filter-item",
            ),
            # Simplify button
            ui.div(
                ui.tags.button(
                    "Simplificar sistema",
                    class_="btn btn-outline-secondary btn-sm species-simplify-btn",
                    **{"data-bs-toggle": "modal", "data-bs-target": "#simplifyModal"},
                ),
                class_="species-filter-simplify",
            ),
            # Symbols button + dropdown panel
            ui.div(
                ui.tags.button(
                    "Símbolos",
                    class_="btn btn-sm species-symbols-btn",
                    onclick="document.getElementById('symbolsDropdown').classList.toggle('symbols-open');",
                ),
                ui.div(
                    ui.div(
                        ui.span("Símbolos", style="font-weight: 600; font-size: 15px;"),
                        ui.tags.button(
                            "×",
                            class_="btn-close",
                            onclick="document.getElementById('symbolsDropdown').classList.remove('symbols-open');",
                        ),
                        class_="symbols-dropdown-header",
                    ),
                    ui.div(
                        *[_symbol_badge(pt, en, color, icon) for pt, en, color, icon in _SYMBOLS],
                        class_="symbols-dropdown-grid",
                    ),
                    id="symbolsDropdown",
                    class_="symbols-dropdown",
                ),
                class_="species-filter-simplify",
                style="position: relative;",
            ),
            class_="species-filters-row",
        ),

        # Simplify modal
        ui.HTML("""
        <div class="modal fade" id="simplifyModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">
                  <span class="i18n-pt">Simplificar gráfico</span>
                  <span class="i18n-en">Simplify chart</span>
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body" id="simplify-modal-body"></div>
            </div>
          </div>
        </div>
        """),


        # Binning controls (hidden; moved into simplify modal via JS)
        ui.div(
            ui.div(
                ui.div(
                    ui.p(
                        "Nº de categorias de demanda de luz",
                        class_="bold-text",
                    ),
                    ui.input_select(
                        "stratum_bins",
                        "",
                        choices={
                            "2": "2", "3": "3", "4": "4", "5": "5",
                            "6": "6", "7": "7", "8": "8", "9": "9",
                        },
                        selected="4",
                    ),
                    style="flex: 1; padding-right: 10px;",
                ),
                ui.div(
                    ui.p(
                        "Nº de períodos de colheita",
                        class_="bold-text",
                    ),
                    ui.input_select(
                        "harvest_bins",
                        "",
                        choices={
                            "2": "2", "3": "3", "4": "4", "5": "5",
                            "6": "6", "7": "7", "8": "8", "9": "9", "10": "10",
                        },
                        selected="4",
                    ),
                    style="flex: 1; padding-left: 10px;",
                ),
                style="display: flex; gap: 20px;",
            ),
            class_="grey-container",
            id="binning-controls",
            style="display: none;",
        ),

        # Main grid visualization
        ui.div(
            output_widget("intercrops"),
            class_="species-grid-area",
        ),

        # Lifetime Section — hidden until species are selected
        ui.panel_conditional(
            "input.overview_plants && input.overview_plants.length > 0",
            ui.div(
                ui.div(
                    ui.p(
                        "Tempo de vida",
                        class_="bold-text",
                    ),
                    ui.help_text(
                        "Visualize o crescimento das espécies selecionadas ao longo do tempo",
                    ),
                    ui.input_slider("life_time", "", min=0, max=101, value=1, step=0.5),
                    class_="center-content",
                ),
                class_="grey-container",
            ),
            # Growth Visualization Output
            ui.div(
                output_widget("plot_plants"),
                class_="main-content",
            ),
        ),

        # JS: move binning controls into simplify modal
        ui.tags.script("""
            document.addEventListener('DOMContentLoaded', function() {
                var binning = document.getElementById('binning-controls');
                var simplifyBody = document.getElementById('simplify-modal-body');
                if (binning && simplifyBody) {
                    simplifyBody.appendChild(binning);
                    binning.style.display = '';
                }
            });
        """),

        nav_buttons(back_value="tab_climate", next_value="tab_results"),
        style="position: relative; padding-bottom: 70px;",
    ),
    value="tab_species",
)
