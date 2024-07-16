from shiny import ui,App

homepage = ui.nav_panel(
    "Home",
    ui.page_fluid(
        ui.row(
        ui.div(
            ui.div(
                ui.div(
                    ui.div(
                        ui.h1(
                            "Welcome to the Agroforestry Dashboard!", class_="text-sc"
                        ),
                        ui.p(
                            "This dashboard is a decision tool to combine plant ecophysiology with practitioners knowledge for multifunctional intercropping",
                            class_="lead",
                        ),
                        class_="homepage-lead-text-block",
                    ),
                    class_="homepage-head",
                ),
                ui.div(
                    ui.div(
                        ui.div(ui.h2("How does it work ?", class_="text-sc"),
                        ui.p(
                            """This dashboard is composed of two tabs. In the first one, you can choose which plants in the database you are interested in. With the selected one, you'll find a graph detailing the period of productivity of each of the plants selected. If there's an important piece of information missing related to lifespan or stratum, you'll find the plant in a card below."""),
                        ui.p(
                            """On the second tab, you'll obtain a wealth of information, such as lifespan or maximum height, by hovering over the bar corresponding to the plant. Below, you'll also find suggested combinations with other plants, based on stratum only for the moment."""),
                            class_="lead",
                        ),
                        class_="homepage-lead-text-block",
                    ),
                    class_="homepage-head",
                ),
                ui.div(
                    class_="homepage-head homepage-actions",
                ),
                class_="homepage-content homepage-background cover light"
            )
        )
    )
))