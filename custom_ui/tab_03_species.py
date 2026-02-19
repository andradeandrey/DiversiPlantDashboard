"""Species / Espécies tab — discovery-based layout."""
import os
from shiny import ui, App
from pathlib import Path
from custom_server.agroforestry_server import get_Plants
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

FILE_NAME = os.path.join(
    Path(__file__).parent.parent, "data", "MgmtTraitData_updated.csv"
)

# Growth form symbols for the legend — Figma design colors & icons
_GF_SVGS = {
    'tree': '<svg width="10" height="18" viewBox="0 0 10 20"><ellipse cx="5" cy="5.5" rx="4" ry="5" fill="none" stroke="white" stroke-width="1.8"/><line x1="5" y1="10.5" x2="5" y2="20" stroke="white" stroke-width="1.8"/></svg>',
    'shrub': '<svg width="16" height="16" viewBox="0 0 16 16"><polygon points="8,1.5 14.9,5.5 12.3,13.5 3.7,13.5 1.1,5.5" fill="none" stroke="white" stroke-width="1.8"/></svg>',
    'subshrub': '<svg width="16" height="16" viewBox="0 0 16 16"><rect x="2" y="2" width="12" height="12" fill="none" stroke="white" stroke-width="2" rx="0.8"/></svg>',
    'forb': '<svg width="16" height="16" viewBox="0 0 20 18"><polygon points="10,1 19,17 1,17" fill="none" stroke="white" stroke-width="2"/></svg>',
    'graminoid': '<svg width="4" height="16" viewBox="0 0 4 16"><rect x="1" y="0" width="2" height="16" fill="white" rx="1"/></svg>',
    'palm': '<svg width="14" height="18" viewBox="0 0 14 20"><line x1="7" y1="20" x2="7" y2="12" stroke="white" stroke-width="1.8"/><path d="M7,12 L2,1" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M7,12 L7,1" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M7,12 L12,1" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg>',
    'bamboo': '<svg width="14" height="16" viewBox="0 0 14 16"><path d="M1,2 L7,14 L13,2" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    'liana': '<svg width="8" height="18" viewBox="0 0 6 20"><path d="M1,0 C1,1.3 5,1.8 5,3.3 C5,4.8 1,5.3 1,6.7 C1,8.1 5,8.6 5,10.1 C5,11.6 1,12.1 1,13.5 C1,14.9 5,15.4 5,16.9 C5,18.4 1,18.9 1,20" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>',
    'vine': '<svg width="8" height="18" viewBox="-0.2 0 4.8 11"><path d="M0.786 0.5C1.714 0.491 3.057 0.695 3.528 1.72C3.817 2.347 3.784 3.071 3.581 3.722L3.557 3.753V3.735C3.275 2.944 2.75 2.573 2.319 2.4C1.777 2.181 1.031 2.32 0.661 2.839C0.514 3.045 0.476 3.306 0.514 3.562C0.637 4.378 1.198 4.649 1.198 4.649C1.198 4.649 2.105 5.193 2.84 4.649C3.221 4.367 3.437 4.012 3.556 3.735L3.55 3.716C4.016 4.782 4.127 6.316 3.67 7.313L3.556 7.375C3.436 7.652 3.278 7.961 2.897 8.244C2.162 8.787 1.255 8.244 1.255 8.244C1.255 8.244 0.694 7.972 0.571 7.156C0.533 6.9 0.571 6.639 0.718 6.433C1.088 5.914 1.834 5.776 2.377 5.994C2.807 6.167 3.332 6.539 3.614 7.329L3.67 7.438C3.872 8.089 3.874 8.653 3.586 9.28C3.114 10.305 1.772 10.509 0.843 10.5" fill="none" stroke="white" stroke-width="0.7" stroke-linecap="round"/></svg>',
    'scrambler': '<svg width="24" height="8" viewBox="0 0 24 8"><path d="M0,7 C1.3,7 1.8,2.5 3.3,2.5 C4.8,2.5 5.3,7 6.7,7 C8.1,7 8.6,2.5 10.1,2.5 C11.6,2.5 12.1,7 13.5,7 C14.9,7 15.4,2.5 16.9,2.5 C18.4,2.5 18.9,7 20.3,7 L22,7" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>',
    'other': '<svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="white" stroke-width="2"/><line x1="4" y1="4" x2="12" y2="12" stroke="white" stroke-width="2"/></svg>',
}

_SYMBOLS = [
    ("Arbusto", "Shrub", "#0095c6", "shrub"),
    ("Sub-arbusto", "Subshrub", "#612e14", "subshrub"),
    ("Trepadeira herbácea", "Vine", "#cc4fb9", "vine"),
    ("Gramíneas e afins", "Graminoid", "#633096", "graminoid"),
    ("Árvore", "Tree", "#2a43d1", "tree"),
    ("Herbácea", "Forb", "#d77d28", "forb"),
    ("Palmeira", "Palm", "#63a355", "palm"),
    ("Bambu", "Bamboo", "#fd2f6d", "bamboo"),
    ("Trepadeira lenhosa", "Liana", "#be2843", "liana"),
    ("Rasteira", "Scrambler", "#017201", "scrambler"),
    ("Outro", "Other", "#171717", "other"),
]


def _symbol_badge(pt, en, color, icon_key):
    svg = _GF_SVGS.get(icon_key, '')
    return ui.span(
        ui.HTML(f'<span style="margin-right:4px; display:inline-flex; align-items:center; vertical-align:middle;">{svg}</span>'),
        ui.span(pt, class_="i18n-pt"),
        ui.span(en, class_="i18n-en"),
        class_="symbol-badge",
        style=f"background-color: {color}; color: white; padding: 4px 10px; "
              f"border-radius: 4px; margin: 3px; display: inline-flex; align-items: center; font-size: 0.85em; font-weight: 600;",
    )


main_species = ui.nav_panel(
    tab_title(3, "Espécies", "Species"),
    ui.page_fluid(
        # Hidden selectize — data store for selected species
        ui.div(
            ui.input_selectize(
                "overview_plants",
                "",
                choices=get_Plants(FILE_NAME),
                multiple=True,
                options={
                    "placeholder": "",
                    "create": True,
                },
            ),
            class_="hidden-selectize-store",
        ),

        # Discovery row: Filters+Search (col-6) + Results (col-6), bordered
        ui.row(
            # Left: Search + Filters column
            ui.column(6,
                ui.div(
                    # Search inside left column
                    ui.div(
                        ui.tags.label(
                            ui.span("Busca:", class_="i18n-pt"),
                            ui.span("Search:", class_="i18n-en"),
                            class_="species-filter-label",
                        ),
                        ui.input_text("species_search", "",
                            placeholder="Buscar espécie por nome... / Search species by name..."),
                        class_="species-search-inline",
                    ),
                    ui.div(
                        ui.input_selectize(
                            "filter_growth_form", "",
                            choices={
                                "tree": "Árvore / Tree",
                                "shrub": "Arbusto / Shrub",
                                "subshrub": "Sub-arbusto / Subshrub",
                                "forb": "Herbácea / Forb",
                                "graminoid": "Gramínea / Graminoid",
                                "palm": "Palmeira / Palm",
                                "bamboo": "Bambu / Bamboo",
                                "liana": "Liana",
                                "vine": "Trepadeira / Vine",
                                "scrambler": "Rasteira / Scrambler",
                            },
                            multiple=True,
                            options={"plugins": ["remove_button"],
                                     "placeholder": "Forma de crescimento"},
                        ),
                        ui.tags.button("Todos", class_="btn-select-all",
                            onclick="var s=$('#filter_growth_form')[0].selectize;Object.keys(s.options).forEach(function(k){s.addItem(k,true)});s.close();"),
                        class_="species-filter-item species-filter-multi",
                    ),
                    ui.div(
                        ui.input_selectize(
                            "filter_plant_use", "",
                            choices={
                                "food": "Alimento / Food",
                                "timber": "Madeira / Timber",
                                "medicinal": "Medicinal",
                                "ornamental": "Ornamental",
                                "fodder": "Forragem / Fodder",
                            },
                            multiple=True,
                            options={"plugins": ["remove_button"],
                                     "placeholder": "Uso da planta"},
                        ),
                        ui.tags.button("Todos", class_="btn-select-all",
                            onclick="var s=$('#filter_plant_use')[0].selectize;Object.keys(s.options).forEach(function(k){s.addItem(k,true)});s.close();"),
                        class_="species-filter-item species-filter-multi",
                    ),
                    ui.div(
                        ui.input_selectize(
                            "filter_threat", "",
                            choices={
                                "LC": "Pouco preocupante (LC)",
                                "NT": "Quase ameaçada (NT)",
                                "VU": "Vulnerável (VU)",
                                "EN": "Em perigo (EN)",
                                "CR": "Criticamente em perigo (CR)",
                            },
                            multiple=True,
                            options={"plugins": ["remove_button"],
                                     "placeholder": "Ameaça à conservação"},
                        ),
                        ui.tags.button("Todos", class_="btn-select-all",
                            onclick="var s=$('#filter_threat')[0].selectize;Object.keys(s.options).forEach(function(k){s.addItem(k,true)});s.close();"),
                        class_="species-filter-item species-filter-multi",
                    ),
                    ui.div(
                        ui.input_selectize(
                            "filter_nfix", "",
                            choices={
                                "yes": "Sim / Yes",
                                "no": "Não / No",
                            },
                            multiple=True,
                            options={"plugins": ["remove_button"],
                                     "placeholder": "Fixador de N"},
                        ),
                        ui.tags.button("Todos", class_="btn-select-all",
                            onclick="var s=$('#filter_nfix')[0].selectize;Object.keys(s.options).forEach(function(k){s.addItem(k,true)});s.close();"),
                        class_="species-filter-item species-filter-multi",
                    ),
                    ui.div(
                        ui.input_selectize(
                            "filter_deciduousness", "",
                            choices={
                                "deciduous": "Decídua / Deciduous",
                                "evergreen": "Perene / Evergreen",
                                "semi": "Semi-decídua / Semi-deciduous",
                            },
                            multiple=True,
                            options={"plugins": ["remove_button"],
                                     "placeholder": "Deciduidade"},
                        ),
                        ui.tags.button("Todos", class_="btn-select-all",
                            onclick="var s=$('#filter_deciduousness')[0].selectize;Object.keys(s.options).forEach(function(k){s.addItem(k,true)});s.close();"),
                        class_="species-filter-item species-filter-multi",
                    ),
                    class_="species-filters-col",
                ),
            ),
            # Right: Discovery results (new + selected)
            ui.column(6,
                ui.output_ui("discovery_results"),
            ),
            class_="species-discovery-row",
        ),

        # Simplify modal
        ui.HTML("""
        <div class="modal fade" id="simplifyModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title">
                  <span class="i18n-pt">Simplificar sistema</span>
                  <span class="i18n-en">Simplify system</span>
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
                ui.p("Nº de categorias de Estrato", class_="bold-text"),
                ui.input_radio_buttons(
                    "stratum_bins", "",
                    choices={"2": "2", "3": "3", "4": "4", "5": "5", "9": "9"},
                    selected="4",
                    inline=True,
                ),
                style="margin-bottom: 24px;",
            ),
            ui.div(
                ui.p("Nº de períodos de colheita feito", class_="bold-text"),
                ui.input_slider("harvest_bins", "", min=2, max=10, value=4, step=1),
            ),
            id="binning-controls",
            style="display: none; padding: 8px 0;",
        ),

        # Chart toolbar (Simplificar + Símbolos) + chart full width
        ui.div(
            # Simplify button
            ui.tags.button(
                "Simplificar sistema",
                class_="btn btn-outline-secondary btn-sm species-simplify-btn",
                **{"data-bs-toggle": "modal", "data-bs-target": "#simplifyModal"},
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
                style="position: relative; display: inline-block;",
            ),
            class_="chart-toolbar",
        ),
        ui.div(
            ui.output_ui("intercrops"),
            class_="species-grid-area",
        ),

        # Brush selection results panel
        ui.panel_conditional(
            "input.brush_range",
            ui.div(
                ui.tags.button(
                    "×",
                    class_="btn-close",
                    style="position:absolute; top:12px; right:16px;",
                    onclick="window._brushActive=false;Shiny.setInputValue('brush_range',null,{priority:'event'});var w=document.getElementById('lifetime-growth-wrapper');if(w)w.style.display='';",
                ),
                ui.h5("Espécies no setor selecionado", style="margin-bottom:8px;"),
                ui.output_ui("brush_results"),
                class_="brush-results-panel",
                id="brush-results-panel",
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
