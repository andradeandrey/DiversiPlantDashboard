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
        # Title
        ui.h5(
            t(
                "Adicione mais colunas à sua tabela de resultados:",
                "Add more columns to your results table:",
            ),
            class_="mt-3 mb-2",
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
            ui.output_ui("suggestion_plants", class_="input-selectize"),
            class_="mt-3",
        ),

        # Bottom actions
        ui.div(
            nav_buttons(back_value="tab_species"),
            ui.div(
                ui.download_button(
                    "export_df_os",
                    t("Baixar", "Download"),
                    class_="btn-success",
                ),
                style="position: absolute; right: 20px; bottom: 16px;",
            ),
            style="position: relative;",
        ),

        # CSS: transform checkboxes into green pills
        ui.tags.style("""
            .column-pills-container .shiny-input-checkboxgroup {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                padding: 10px 0;
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
            .column-pills-container .checkbox label,
            .column-pills-container .form-check-label {
                display: inline-block;
                padding: 5px 14px;
                border-radius: 20px;
                border: 1.5px solid #6cb043;
                color: #6cb043;
                background: white;
                font-size: 0.85em;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.15s ease;
                white-space: nowrap;
                user-select: none;
            }
            .column-pills-container .checkbox label:hover,
            .column-pills-container .form-check-label:hover {
                background: #f0f9e8;
            }
            .column-pills-container .checkbox input:checked + label,
            .column-pills-container .form-check-input:checked + .form-check-label {
                background: #6cb043;
                color: white;
            }
            .column-pills-container .checkbox input:checked + label::after,
            .column-pills-container .form-check-input:checked + .form-check-label::after {
                content: " \\00d7";
                margin-left: 6px;
                font-weight: bold;
            }
        """),
    ),
    value="tab_results",
)
