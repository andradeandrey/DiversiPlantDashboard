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
        # Top section: species search
        ui.div(
            ui.div(
                ui.div(
                    # Left: species input
                    ui.div(
                        ui.p(
                            t(
                                "Digite aqui as espécies que você gostaria de plantar...",
                                "Type the species you'd like to plant...",
                            ),
                            class_="bold-text",
                        ),
                        ui.input_selectize(
                            "overview_plants",
                            "",
                            choices=get_Plants(FILE_NAME),
                            multiple=True,
                            options={
                                "placeholder": "Type name here...",
                                "create": True,
                            },
                        ),
                        class_="left-section-sm",
                    ),
                    # Right: instructions
                    ui.div(
                        ui.p(
                            t(
                                "Mais de 1 espécie no mesmo retângulo abaixo indica que provavelmente "
                                "competirão. Você ainda pode combiná-las, mas precisaria reduzir a densidade.",
                                "More than 1 species in the same rectangle below indicate that they will "
                                "likely compete. You might still combine them, but would probably need to "
                                "reduce the density of each.",
                            ),
                        ),
                        class_="right-section-sm",
                    ),
                    class_="flex-container-ms",
                ),
                class_="grey-container",
            ),

            # Filter dropdowns (matching Figma)
            ui.div(
                ui.div(
                    ui.div(
                        ui.input_select(
                            "filter_growth_form",
                            t("Forma de crescimento", "Growth form"),
                            choices={
                                "": t("Todos", "All"),
                                "tree": t("Árvore", "Tree"),
                                "shrub": t("Arbusto", "Shrub"),
                                "subshrub": t("Sub-arbusto", "Subshrub"),
                                "herb": t("Herbácea", "Herb"),
                                "climber": t("Trepadeira", "Climber"),
                                "palm": t("Palmeira", "Palm"),
                                "bamboo": t("Bambu", "Bamboo"),
                                "cactus": t("Cacto", "Cactus"),
                            },
                        ),
                        style="flex: 1; min-width: 140px;",
                    ),
                    ui.div(
                        ui.input_select(
                            "filter_plant_use",
                            t("Uso da planta", "Plant use"),
                            choices={
                                "": t("Todos", "All"),
                                "food": t("Alimento", "Food"),
                                "timber": t("Madeira", "Timber"),
                                "medicinal": t("Medicinal", "Medicinal"),
                                "ornamental": t("Ornamental", "Ornamental"),
                            },
                        ),
                        style="flex: 1; min-width: 140px;",
                    ),
                    ui.div(
                        ui.input_select(
                            "filter_threat",
                            t("Ameaça à conservação", "Conservation threat"),
                            choices={
                                "": t("Todos", "All"),
                                "LC": "LC",
                                "NT": "NT",
                                "VU": "VU",
                                "EN": "EN",
                                "CR": "CR",
                            },
                        ),
                        style="flex: 1; min-width: 140px;",
                    ),
                    ui.div(
                        ui.input_select(
                            "filter_nfix",
                            t("Fixador biológico de N", "N-fixer"),
                            choices={
                                "": t("Todos", "All"),
                                "yes": t("Sim", "Yes"),
                                "no": t("Não", "No"),
                            },
                        ),
                        style="flex: 1; min-width: 140px;",
                    ),
                    ui.div(
                        ui.input_select(
                            "filter_deciduousness",
                            t("Deciduidade", "Deciduousness"),
                            choices={
                                "": t("Todos", "All"),
                                "deciduous": t("Decídua", "Deciduous"),
                                "evergreen": t("Perene", "Evergreen"),
                                "semi": t("Semi-decídua", "Semi-deciduous"),
                            },
                        ),
                        style="flex: 1; min-width: 140px;",
                    ),
                    # Simplify button
                    ui.div(
                        ui.tags.button(
                            t("Simplificar sistema", "Simplify system"),
                            class_="btn btn-outline-secondary btn-sm",
                            **{"data-bs-toggle": "modal", "data-bs-target": "#simplifyModal"},
                        ),
                        style="display: flex; align-items: end; padding-bottom: 16px;",
                    ),
                    style="display: flex; gap: 10px; flex-wrap: wrap;",
                ),
                class_="grey-container mt-2",
            ),

            # Simplify modal (Figma: "Simplificar gráfico")
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

            # Symbols modal (Figma screenshot 7)
            ui.div(
                ui.HTML("""
                <div class="modal fade" id="symbolsModal" tabindex="-1" aria-hidden="true">
                  <div class="modal-dialog">
                    <div class="modal-content">
                      <div class="modal-header">
                        <h5 class="modal-title">
                          <span class="i18n-pt">Símbolos</span>
                          <span class="i18n-en">Symbols</span>
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                      </div>
                      <div class="modal-body" id="symbols-modal-body"></div>
                    </div>
                  </div>
                </div>
                """),
            ),

            # Symbols modal body content (rendered by Shiny, moved into modal via JS)
            ui.div(
                *[_symbol_badge(pt, en, color, icon) for pt, en, color, icon in _SYMBOLS],
                id="symbols-content",
                style="display: none;",
            ),

            # Symbols button (floats near chart area)
            ui.div(
                ui.tags.button(
                    t("Símbolos", "Symbols"),
                    class_="btn btn-outline-success btn-sm",
                    **{"data-bs-toggle": "modal", "data-bs-target": "#symbolsModal"},
                ),
                style="text-align: right; margin-top: 8px; margin-bottom: 4px;",
            ),

            # Binning controls (hidden; moved into simplify modal via JS)
            ui.div(
                ui.div(
                    ui.div(
                        ui.p(
                            t("Nº de categorias de demanda de luz", "Light demand categories"),
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
                            t("Nº de períodos de colheita", "Harvest period divisions"),
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

            # Visualization Output
            ui.div(
                output_widget("intercrops"),
            ),
            ui.p(""),

            # Lifetime Section
            ui.div(
                ui.div(
                    ui.p(
                        t("Tempo de vida", "Lifetime"),
                        class_="bold-text",
                    ),
                    ui.help_text(
                        t(
                            "Visualize o crescimento das espécies selecionadas ao longo do tempo",
                            "Visualize the growth of selected species over time",
                        ),
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

        # JS: move binning controls into simplify modal, symbols content into symbols modal
        ui.tags.script("""
            document.addEventListener('DOMContentLoaded', function() {
                // Move binning controls into simplify modal body
                var binning = document.getElementById('binning-controls');
                var simplifyBody = document.getElementById('simplify-modal-body');
                if (binning && simplifyBody) {
                    simplifyBody.appendChild(binning);
                    binning.style.display = '';
                }
                // Move symbols content into symbols modal body
                var symbols = document.getElementById('symbols-content');
                var symbolsBody = document.getElementById('symbols-modal-body');
                if (symbols && symbolsBody) {
                    symbolsBody.appendChild(symbols);
                    symbols.style.display = '';
                }
            });
        """),

        nav_buttons(back_value="tab_climate", next_value="tab_results"),
    ),
    value="tab_species",
)
