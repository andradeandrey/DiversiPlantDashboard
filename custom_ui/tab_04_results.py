"""Results / Resultados tab — column pill selector (Figma screenshots 16-17)."""
import os
from shiny import ui, App
from pathlib import Path
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

FILE_NAME = os.path.join(Path(__file__).parent.parent, "data", "MgmtTraitData_updated.csv")

results = ui.nav_panel(
    tab_title(4, "Resultados", "Results"),
    ui.page_fluid(
        ui.tags.style(".tab-pane[data-value='tab_results'] .container-fluid { padding: 0 80px; }"),
        # Title — centered
        ui.h5(
            t(
                "Adicione mais colunas à sua tabela de resultados:",
                "Add more columns to your results table:",
            ),
            class_="mt-3 mb-2 text-center",
        ),

        # Column pill selector (checkbox group styled as pills via CSS)
        ui.div(
            ui.input_checkbox_group(
                "selected_columns",
                "",
                [],  # Populated dynamically by server
                selected=[],
                inline=True,
            ),
            class_="column-pills-container",
        ),

        # Data table
        ui.div(
            ui.output_ui("suggestion_plants"),
            class_="mt-3",
        ),

        # Bottom actions: Voltar left, Baixar right (in nav-buttons row)
        ui.div(
            ui.tags.button(
                t("Voltar", "Back"),
                class_="btn btn-outline-secondary nav-btn",
                onclick="Shiny.setInputValue('_nav_to', 'tab_species', {priority: 'event'});",
            ),
            ui.div(style="flex-grow: 1;"),
            ui.download_button(
                "export_df_os",
                ui.span(t("Baixar", "Download"), " \u2228"),
                class_="results-download-btn",
            ),
            class_="nav-buttons d-flex mt-4 mb-3",
        ),

        # CSS: transform checkboxes into green pills with +/- prefix (Figma match)
        ui.tags.style("""
            .column-pills-container {
                text-align: center;
            }
            .column-pills-container > div,
            .column-pills-container .shiny-input-container,
            .column-pills-container .shiny-input-checkboxgroup,
            .column-pills-container .shiny-options-group {
                display: flex !important;
                flex-wrap: wrap !important;
                gap: 6px !important;
                padding: 10px 0;
                justify-content: center !important;
                width: 100% !important;
            }
            .column-pills-container .checkbox,
            .column-pills-container .form-check {
                margin: 0 !important;
                padding: 0 !important;
            }
            .column-pills-container .checkbox input[type="checkbox"],
            .column-pills-container .form-check-input {
                display: none !important;
            }
            /* Base pill style: white bg, green border, "+" prefix */
            .column-pills-container .checkbox label,
            .column-pills-container .form-check-label {
                display: inline-block;
                padding: 5px 14px;
                border-radius: 20px;
                border: 1.5px solid #3d6834;
                color: #3d6834;
                background: white;
                font-size: 0.85em;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.15s ease;
                white-space: nowrap;
                user-select: none;
            }
            .column-pills-container .checkbox label::before,
            .column-pills-container .form-check-label::before {
                content: "+ ";
                font-weight: 600;
            }
            .column-pills-container .checkbox label:hover,
            .column-pills-container .form-check-label:hover {
                background: #f0f9e8;
            }
            /* Selected pill: dark green bg, white text, "−" prefix */
            /* sibling selector (Bootstrap 5) */
            .column-pills-container .form-check-input:checked + .form-check-label,
            .column-pills-container .checkbox input:checked + label,
            /* :has() selector (input nested inside label) */
            .column-pills-container .checkbox label:has(input:checked),
            .column-pills-container .form-check-label:has(input:checked) {
                background: #3d6834 !important;
                color: white !important;
                border-color: #3d6834 !important;
            }
            .column-pills-container .form-check-input:checked + .form-check-label::before,
            .column-pills-container .checkbox input:checked + label::before,
            .column-pills-container .checkbox label:has(input:checked)::before,
            .column-pills-container .form-check-label:has(input:checked)::before {
                content: "\\2212  ";
            }
        """),

        # Auto-retry download on first click (Shiny handler may not be warm yet)
        ui.tags.script("""
        $(document).on('shiny:sessioninitialized', function() {
            var dlBtn = document.getElementById('export_df_os');
            if (!dlBtn) return;
            var origHref = null;
            var observer = new MutationObserver(function(muts) {
                muts.forEach(function(m) {
                    if (m.attributeName === 'href') origHref = dlBtn.getAttribute('href');
                });
            });
            observer.observe(dlBtn, {attributes: true});

            dlBtn.addEventListener('click', function(e) {
                if (dlBtn.dataset._retrying) return;
                var href = dlBtn.getAttribute('href');
                if (!href) return;
                e.preventDefault();
                e.stopImmediatePropagation();
                fetch(href).then(function(r) {
                    if (r.ok) {
                        r.blob().then(function(b) {
                            var a = document.createElement('a');
                            a.href = URL.createObjectURL(b);
                            var cd = r.headers.get('content-disposition');
                            var fn = 'selected_data.csv';
                            if (cd) { var m = cd.match(/filename="?([^"]+)"?/); if (m) fn = m[1]; }
                            a.download = fn;
                            document.body.appendChild(a);
                            a.click();
                            a.remove();
                        });
                    } else {
                        dlBtn.dataset._retrying = '1';
                        setTimeout(function() {
                            delete dlBtn.dataset._retrying;
                            dlBtn.click();
                        }, 500);
                    }
                }).catch(function() {
                    dlBtn.dataset._retrying = '1';
                    setTimeout(function() {
                        delete dlBtn.dataset._retrying;
                        dlBtn.click();
                    }, 500);
                });
            }, true);
        });
        """),
    ),
    value="tab_results",
)
