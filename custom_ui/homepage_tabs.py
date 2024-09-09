from shiny import ui

homepage = ui.nav_panel(
    "Home",
    ui.page_fluid(
        ui.row(
            ui.div(
                ui.div(
                    ui.div(
                        ui.div(
                            ui.h1("DiversiPlant", class_="text-sc"),
                            ui.p(
                                "A practical decision app to help combine different plant species that are likely to thrive together in the same agriculture, forestry or restoration plot.",
                                class_="lead",
                            ),
                            class_="homepage-lead-text-block",
                        ),
                        class_="homepage-head",
                    ),
                    ui.div(
                        ui.div(
                            ui.div(
                                ui.h2("How does it work ?", class_="text-sc"),
                                ui.p(
                                    """From 100,000s of plant species filter out those not adapted (and not native if you prefer) to your planting project.
Skip tabs if you want to keep all available options open. Revert to change previous filtering selections at any time on any tab.
This app does NOT (yet) tackle spacing, spatial arrangements, rooting physiology, nor insect/microbe interactions.
"""
                                ),
                                ui.p(
                                    """Location/Climate → Main species → Compatible Growth forms → Compatible Growth cycles & Heights & Light demands → Selected compatible species output with direct hyperlinks to external databases"""
                                ),
                                class_="lead",
                            ),
                            class_="homepage-lead-text-block",
                        ),
                        class_="homepage-head",
                    ),
                    ui.div(
                        class_="homepage-head homepage-actions",
                    ),
                    class_="homepage-content homepage-background cover light",
                )
            )
        )
    ),
)
