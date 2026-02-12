"""Location / Localização tab."""
import os
from shiny import ui, App
from pathlib import Path
from shinywidgets import output_widget
import faicons as fa
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

FILE_NAME = os.path.join(Path(__file__).parent.parent, "data", "MgmtTraitData_updated.csv")

location = ui.nav_panel(
    tab_title(1, "Localização", "Location"),
    ui.page_fluid(
        # Container for flexbox layout
        ui.div(
            ui.div(
                ui.h4(
                    t(
                        "Cole suas coordenadas do ",
                        "Copy your Project Coordinates from ",
                    ),
                    ui.a("Google Maps", href="https://www.google.com/maps", target="_blank", class_="link"),
                    t(" ou ", " or "),
                    ui.a("OpenStreetMap", href="https://www.openstreetmap.org", target="_blank", class_="link"),
                ),
                ui.div(
                    ui.h5(
                        t(
                            "Ou ative a localização automática no seu navegador/dispositivo OU amplie e clique no local do seu projeto.",
                            "OR enable automatic 'Location' in your web browser OR device OR Zoom & click on your planting project location.",
                        ),
                    ),
                    ui.p(
                        t(
                            "O clima e bioma serão retornados automaticamente para filtrar espécies adaptadas nas próximas páginas.",
                            "Your climate & biome will then be returned automatically to filter adapted species on following pages.",
                        ),
                    ),
                ),
                class_="left-section",
            ),
            ui.div(
                # Coordinates Input and Update Map Button
                ui.div(
                    ui.input_text(
                        "longitude_latitude",
                        t("Cole suas coordenadas:", "Paste your coordinates:"),
                        placeholder="-23.5505, -46.6333",
                    ),
                    ui.input_action_button(
                        "update_map",
                        t("Enviar ➔", "Send ➔"),
                    ),
                    class_="coordinates-container",
                ),
                ui.div(
                    ui.help_text(t("OU", "OR")),
                ),
                ui.input_action_button(
                    "current_location",
                    t("📍 Obter localização atual", "📍 Current Location"),
                    class_="btn-primary",
                ),
                ui.tags.script("""
                    document.addEventListener('DOMContentLoaded', function() {
                        setTimeout(function() {
                            var btn = document.getElementById('current_location');
                            if (btn) {
                                btn.addEventListener('click', function(e) {
                                    e.preventDefault();
                                    if (navigator.geolocation) {
                                        btn.disabled = true;
                                        btn.textContent = '⏳ Localizando...';
                                        navigator.geolocation.getCurrentPosition(
                                            function(position) {
                                                var lat = position.coords.latitude.toFixed(6);
                                                var lon = position.coords.longitude.toFixed(6);
                                                var input = document.getElementById('longitude_latitude');
                                                if (input) {
                                                    input.value = lat + ', ' + lon;
                                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                                }
                                                btn.disabled = false;
                                                btn.textContent = '📍 Localização atual';
                                                setTimeout(function() {
                                                    var sendBtn = document.getElementById('update_map');
                                                    if (sendBtn) sendBtn.click();
                                                }, 100);
                                            },
                                            function(error) {
                                                alert('Erro de geolocalização: ' + error.message);
                                                btn.disabled = false;
                                                btn.textContent = '📍 Localização atual';
                                            },
                                            { enableHighAccuracy: true, timeout: 10000 }
                                        );
                                    } else {
                                        alert('Geolocalização não suportada pelo navegador');
                                    }
                                });
                            }
                        }, 1000);
                    });
                """),
                ui.div(
                    ui.p(""),
                    ui.help_text(t("Filtrar espécies por", "Filter species by")),
                    ui.input_selectize(
                        "floristic_group",
                        "",
                        choices=["All Species", "Endemic", "Native", "Naturalized"],
                        multiple=False,
                    ),
                ),
                class_="right-section",
            ),
            class_="flex-container",
        ),
        # Map Section
        ui.div(
            ui.output_ui("world_map"),
            class_="map",
        ),
        nav_buttons(back_value="tab_start", next_value="tab_climate"),
    ),
    value="tab_location",
)
