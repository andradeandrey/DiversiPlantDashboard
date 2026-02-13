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
        # Coordinates bar — centered, minimal
        ui.div(
            ui.input_text(
                "longitude_latitude",
                "",
                placeholder="Cole suas coordenadas (latitude, longitude)....",
                width="100%",
            ),
            # Hidden update_map button (triggered by Enter or geolocation)
            ui.div(
                ui.input_action_button("update_map", ""),
                style="display: none;",
            ),
            # Submit on Enter key
            ui.tags.script(
                "document.addEventListener('DOMContentLoaded',function(){"
                "  setTimeout(function(){"
                "    var inp=document.getElementById('longitude_latitude');"
                "    if(inp) inp.addEventListener('keydown',function(e){"
                "      if(e.key==='Enter'){ e.preventDefault();"
                "        Shiny.setInputValue('update_map', Math.random(), {priority:'event'});"
                "      }"
                "    });"
                "  },1000);"
                "});"
            ),
            ui.p(
                t("Encontre suas coordenadas no ", "Find your coordinates on "),
                ui.a("Google Maps", href="https://www.google.com/maps", target="_blank"),
                t(" ou no ", " or "),
                ui.a("OSM", href="https://www.openstreetmap.org", target="_blank"),
                ".",
                style="text-align: center; font-size: 13px; color: #666; margin-top: 4px;",
            ),
            ui.div(
                ui.tags.button(
                    t("Ou ativar localização atual", "Or enable current location"),
                    id="current_location",
                    class_="btn btn-outline-secondary loc-btn",
                    onclick="",
                ),
                style="text-align: center; margin-top: 12px;",
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
                                            var coords = lat + ', ' + lon;
                                            var input = document.getElementById('longitude_latitude');
                                            if (input) {
                                                input.value = coords;
                                                input.dispatchEvent(new Event('input', { bubbles: true }));
                                            }
                                            Shiny.setInputValue('longitude_latitude', coords);
                                            btn.disabled = false;
                                            btn.textContent = 'Ou ativar localização atual';
                                            setTimeout(function() {
                                                Shiny.setInputValue('update_map', Math.random(), {priority: 'event'});
                                            }, 200);
                                        },
                                        function(error) {
                                            alert('Erro de geolocalização: ' + error.message);
                                            btn.disabled = false;
                                            btn.textContent = 'Ou ativar localização atual';
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
            class_="location-bar",
        ),
        # Hidden floristic_group (server depends on it)
        ui.div(
            ui.input_selectize(
                "floristic_group",
                "",
                choices=["All Species", "Endemic", "Native", "Naturalized"],
                multiple=False,
            ),
            style="display: none;",
        ),
        # Map + nav buttons overlay
        ui.div(
            ui.div(
                ui.output_ui("world_map"),
                class_="map",
            ),
            nav_buttons(back_value="tab_start", next_value="tab_climate"),
            style="position: relative;",
        ),
    ),
    value="tab_location",
)
