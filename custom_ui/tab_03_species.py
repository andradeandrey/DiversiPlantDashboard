"""Species / Espécies tab — matches Figma design."""
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
    'tree': '<svg width="10" height="18" viewBox="0 0 10 20"><circle cx="5" cy="5" r="4" fill="none" stroke="white" stroke-width="1.8"/><line x1="5" y1="9" x2="5" y2="20" stroke="white" stroke-width="1.8"/></svg>',
    'shrub': '<svg width="16" height="16" viewBox="0 0 16 16"><polygon points="8,1.5 14.9,5.5 12.3,13.5 3.7,13.5 1.1,5.5" fill="none" stroke="white" stroke-width="1.8"/></svg>',
    'subshrub': '<svg width="16" height="16" viewBox="0 0 16 16"><rect x="2" y="2" width="12" height="12" fill="none" stroke="white" stroke-width="2" rx="0.8"/></svg>',
    'forb': '<svg width="16" height="16" viewBox="0 0 20 18"><polygon points="10,1 19,17 1,17" fill="none" stroke="white" stroke-width="2"/></svg>',
    'graminoid': '<svg width="4" height="16" viewBox="0 0 4 16"><rect x="1" y="0" width="2" height="16" fill="white" rx="1"/></svg>',
    'palm': '<svg width="14" height="18" viewBox="0 0 14 20"><line x1="7" y1="20" x2="7" y2="7" stroke="white" stroke-width="1.8"/><path d="M7,7 L2,1" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M7,7 L12,1" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg>',
    'bamboo': '<svg width="14" height="16" viewBox="0 0 14 16"><path d="M1,2 L7,14 L13,2" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    'liana': '<svg width="6" height="18" viewBox="0 0 6 20"><path d="M3,0 C0,5 6,10 3,15 C1.5,17.5 3,20 3,20" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>',
    'vine': '<svg width="10" height="18" viewBox="0 0 10 20"><path d="M2,20 C2,10 8,10 8,2" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/><circle cx="8" cy="2" r="2" fill="white"/></svg>',
    'scrambler': '<svg width="22" height="8" viewBox="0 0 22 8"><path d="M1,4 L5,1 L9,7 L13,1 L17,7 L21,4" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    'other': '<svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="white" stroke-width="2"/><line x1="4" y1="12" x2="12" y2="4" stroke="white" stroke-width="2"/></svg>',
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

        # Selected species tags — wider container below search bar
        ui.div(id="species-tags-container", class_="species-tags-container"),

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

        # Main grid visualization
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


        # JS: move binning controls into simplify modal + fix selectize input width + brush toggle
        ui.tags.script("""
            document.addEventListener('DOMContentLoaded', function() {
                var binning = document.getElementById('binning-controls');
                var simplifyBody = document.getElementById('simplify-modal-body');
                if (binning && simplifyBody) {
                    simplifyBody.appendChild(binning);
                    binning.style.display = '';
                }


                // Wait for Shiny selectize to initialize, then sync tags
                function initTagSync() {
                    var searchBar = document.querySelector('.species-search-bar .selectize-input');
                    var tagsContainer = document.getElementById('species-tags-container');
                    if (!searchBar || !tagsContainer) {
                        setTimeout(initTagSync, 200);
                        return;
                    }

                    var syncing = false;
                    function syncTags() {
                        if (syncing) return;
                        syncing = true;

                        // Force input width
                        var inp = searchBar.querySelector('input');
                        if (inp) inp.style.setProperty('width', '603px', 'important');

                        // Clone .item elements to external container
                        var items = searchBar.querySelectorAll('.item');
                        tagsContainer.innerHTML = '';
                        items.forEach(function(item) {
                            var clone = item.cloneNode(true);
                            clone.style.display = '';
                            var removeBtn = clone.querySelector('.remove');
                            if (removeBtn) {
                                removeBtn.addEventListener('click', function(e) {
                                    e.preventDefault();
                                    var origRemove = item.querySelector('.remove');
                                    if (origRemove) origRemove.click();
                                    // Blur selectize to prevent dropdown from opening
                                    setTimeout(function() {
                                        var inp = searchBar.querySelector('input');
                                        if (inp) inp.blur();
                                        var s = $('#overview_plants')[0];
                                        if (s && s.selectize) s.selectize.close();
                                    }, 50);
                                });
                            }
                            tagsContainer.appendChild(clone);
                            item.style.display = 'none';
                        });

                        syncing = false;
                    }

                    var obs = new MutationObserver(syncTags);
                    obs.observe(searchBar, { childList: true, subtree: true });
                    syncTags();
                }
                initTagSync();
            });
        """),

        nav_buttons(back_value="tab_climate", next_value="tab_results"),
        style="position: relative; padding-bottom: 70px;",
    ),
    value="tab_species",
)
