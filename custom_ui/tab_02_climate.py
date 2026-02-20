"""Climate / Clima tab — matches Figma design with ecoregion map."""
from shiny import ui
from shinywidgets import output_widget
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

# Biome types mapping to WWF biome numbers
BIOME_TYPES = {
    "Boreal Forest (Taiga)": "Boreal Forest (Taiga)",
    "Deserts & Xeric Shrublands": "Deserts & Xeric Shrublands",
    "Mangroves": "Mangroves",
    "Mediterranean Forests, Woodlands & Scrub": "Mediterranean Forests, Woodlands & Scrub",
    "Montane Grasslands & Shrublands": "Montane Grasslands & Shrublands",
    "Rock and Ice": "Rock and Ice",
    "Temperate Broadleaf & Mixed Forests": "Temperate Broadleaf & Mixed Forests",
    "Temperate Conifer Forests": "Temperate Conifer Forests",
    "Tropical & Subtropical Moist Broadleaf Forests": "Tropical & Subtropical Moist Broadleaf Forests",
    "Tropical & Subtropical Dry Broadleaf Forests": "Tropical & Subtropical Dry Broadleaf Forests",
    "Tropical & Subtropical Grasslands, Savannas & Shrublands": "Tropical & Subtropical Grasslands, Savannas & Shrublands",
    "Temperate Grasslands, Savannas & Shrublands": "Temperate Grasslands, Savannas & Shrublands",
}

climate = ui.nav_panel(
    tab_title(2, "Clima", "Climate"),
    ui.page_fluid(
        # Dynamic context message — ecoregion + biome detected at user location
        ui.output_ui("climate_context_info"),

        # Main content: map (left) + biome controls (right)
        ui.div(
            # Left: ecoregion map only
            ui.div(
                ui.output_ui("ecoregion_map"),
                class_="climate-map-col",
            ),
            # Right: biome correction guidance + biome selection
            ui.div(
                ui.p(
                    t(
                        "Se o bioma não foi reconhecido corretamente, a resolução do mapa "
                        "retornou outro bioma próximo a você. Para selecionar a ecorregião/bioma "
                        "correto, verifique neste mapa qual localização próxima cairia na ecorregião "
                        "correta do seu projeto, depois volte à aba Localização para selecionar "
                        "essa localização e retorne aqui. Se o seu projeto está localizado em "
                        "uma transição para outro bioma, você pode selecionar manualmente "
                        "bioma(s) adicional(is) abaixo para ampliar a filtragem de espécies.",
                        "If your biome is not recognized correctly, the map resolution returned "
                        "another biome close to you. To select the correct ecoregion/biome, "
                        "please check on this map which closeby location would fall into your "
                        "project's correct ecoregion, then go back to Location tab to select "
                        "that location and return here. If your project is located within a "
                        "transition to another biome, you may manually select an additional "
                        "biome(s) below, to broaden species filtering.",
                    ),
                    style="font-size: 13px; color: #666; margin-bottom: 16px; line-height: 1.5;",
                ),
                # Biome Types
                ui.h6(
                    t("Bioma", "Biome"),
                    style="font-weight: 600; margin-top: 4px;",
                ),
                ui.input_checkbox_group(
                    "biome_types",
                    "",
                    choices=BIOME_TYPES,
                    inline=True,
                ),
                class_="climate-right-col",
            ),
            class_="climate-main-row",
        ),

        # Optional Whittaker diagram — at the bottom, below the two-column layout
        ui.div(
            ui.p(
                t(
                    "OPCIONAL: O gráfico de Whittaker abaixo pode ajudá-lo a identificar "
                    "qual(is) bioma(s) adicional(is) selecionar, com base na precipitação "
                    "anual e temperatura média.",
                    "OPTIONAL: The Whittaker graph below may help you identify which "
                    "additional biome(s) to select, based on its annual rainfall and "
                    "mean temperature.",
                ),
                style="font-weight: 600; font-size: 13px; color: #555; margin-bottom: 16px; "
                       "max-width: 80%; margin-left: auto; margin-right: auto; text-align: center;",
            ),
            output_widget("whittaker_diagram"),
            style="clear: both; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0;",
        ),

        # Floating nav buttons footer
        nav_buttons(back_value="tab_location", next_value="tab_species"),
        style="position: relative; padding-bottom: 70px;",
    ),
    value="tab_climate",
)
