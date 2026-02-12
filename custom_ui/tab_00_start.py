"""Start / Início tab — matches Figma design."""
from shiny import ui
import faicons as fa
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons

start = ui.nav_panel(
    tab_title(0, "Início", "Start"),
    ui.page_fluid(
        ui.row(
            ui.column(
                6,
                ui.div(
                    ui.h2(
                        t(
                            "Combine espécies compatíveis para seu projeto de plantio",
                            "Combine compatible species for your planting project",
                        ),
                        class_="bold-text",
                        style="font-size: 19px;",
                    ),
                    ui.p(""),
                    ui.h6(
                        t(
                            "Encontre informações práticas sobre plantas que provavelmente "
                            "prosperarão juntas em sua parcela agrícola, florestal ou de restauração",
                            "Find practical information about plants that are likely to thrive "
                            "together in your agricultural, forestry or restoration plot",
                        ),
                        style="letter-spacing: 0.5px; font-size: 18px;",
                    ),
                    ui.p(""),
                    ui.div(
                        fa.icon_svg("list"),
                        " ",
                        t(
                            "De mais de 100.000 espécies, filtre as não adequadas para sua localização e propósitos",
                            "From 100,000s of plant species filter out those not suited for your location and purposes",
                        ),
                        style="margin-bottom: 10px;",
                    ),
                    ui.div(
                        fa.icon_svg("forward"),
                        " ",
                        t(
                            "Pule abas para manter todas as opções abertas. Volte para alterar seleções anteriores a qualquer momento.",
                            "Skip tabs if you want to keep all available options open. Revert to change previous filtering selections at any time.",
                        ),
                        style="margin-bottom: 10px;",
                    ),
                    ui.div(
                        fa.icon_svg("share-from-square"),
                        " ",
                        t(
                            "Compartilhe a lista de espécies selecionadas para encontrar sementes ou mudas na sua região.",
                            "Share list of your selected species to find seeds or seedlings in your region.",
                        ),
                        style="margin-bottom: 10px;",
                    ),
                    ui.p(""),
                    ui.h4(
                        t("Escolha um banco de dados:", "Choose a database:"),
                        class_="bold-text",
                        style="letter-spacing: 0.5px; font-size: 18px;",
                    ),
                    ui.help_text(
                        t(
                            "Para o banco GIFT, selecione uma localização.",
                            "For GIFT Database, select location.",
                        ),
                        style="font-weight: bold;",
                    ),
                    ui.tooltip(
                        ui.help_text(
                            t(" (Ajuda)", " (Help)"),
                        ),
                        "Para o banco GIFT, vá à aba Localização. / For GIFT, go to the Location tab.",
                        placement="right",
                    ),
                    ui.input_radio_buttons(
                        "database_choice",
                        "",
                        choices=[
                            "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.",
                            "✔️ Most known species. ✔️ Botanical details. ✔️ Filtered for your location. ❌ Slow.",
                        ],
                        inline=True,
                    ),
                    ui.p(
                        t(
                            "Em construção: integrando e expandindo ambos os bancos para um fluxo de busca único.",
                            "Under construction: Integrating & expanding both databases for single search flow.",
                        ),
                        style="color: #808080; font-size: 15px;",
                    ),
                    ui.p(
                        t(
                            "Este app ainda não aborda espaçamento, arranjos espaciais, fisiologia radicular, nem interações inseto/micróbio.",
                            "This app does not (yet) tackle spacing, spatial arrangements, rooting physiology, nor insect/microbe interactions.",
                        ),
                        style="color: #808080; font-size: 15px;",
                    ),
                ),
                style="padding: 60px 50px; font-size: 16px; display: flex; flex-direction: column; justify-content: space-between;",
            ),
            ui.column(
                6,
                ui.img(
                    src="img/homepage.jpg",
                    style="width: 95%; height: 100%; object-fit: cover;",
                ),
                style="display: flex; align-items: stretch; padding: 0px 0px;",
            ),
        ),
        nav_buttons(next_value="tab_location"),
        style="display: flex; flex-direction: column; align-items: stretch; padding: 10px 20px;",
    ),
    value="tab_start",
)
