from shiny import ui
import faicons as fa

# Add main content
ICONS = {
    "list": fa.icon_svg("list"),
    "forward": fa.icon_svg("forward"),
    "share": fa.icon_svg("share"),

}
homepage = ui.nav_panel(
    "Start",
    ui.page_fluid(
        ui.row(
            ui.column(
                6,  # Left column taking half the width
                ui.div(
                    ui.h2("Discover compatible species for your planting project", class_="bold-text", style="font-size: 19px;"),
                    ui.p(""),
                    ui.h6("Find practical information about plants that are likely to thrive together in your agricultural, forestry or restoration plot", style="letter-spacing: 0.5px; font-size: 18px;"),
                    ui.p(""),
                    ui.HTML(f'<i class="fa fa-list" aria-hidden="true"></i> From 100,000s of plant species filter out those not suited for your location and purposes'),
                    ui.p(""),
                    ui.HTML(f'<i class="fa fa-forward" aria-hidden="true"></i> Skip tabs if you want to keep all available options open. Revert to change previous filtering selections at any time on any tab.'),
                    ui.p(""),
                    ui.HTML(f'<i class="fa fa-share" aria-hidden="true"></i> Share list of your selected species to find seeds or seedlings in your region.'),
                    ui.p(""),
                    ui.h4("Databases:", class_="bold-text", style="letter-spacing: 0.5px; font-size: 18px;"),
                    ui.p("Normal Database: ❌ Few common species. ✔️ Fast. ✔️ Practical management traits. ❌ Ignores location."),
                    ui.p(""),
                    ui.p("GIFT Database: ✔️ Most known species. ❌ Slow. ✔️ Botanical details. ✔️ Filtered for your location."),
                    ui.p("Under construction: Integrating & expanding both databases for single search flow", style="color: #808080; font-size: 15px;"),
                    ui.h4("Choose a Database:", class_="bold-text", style="letter-spacing: 0.5px; font-size: 18px;"),
                    ui.input_radio_buttons("database_choice", "", ["Normal Database", 
                                                    "GIFT Database"]),
                    ui.div(ui.input_action_button("update_database", "Update choices")),
                    ui.p(""),
                    # ui.input_action_button("begin", "Begin"),
                    ui.p(""),
                    ui.p("This app does not (yet) tackle spacing, spatial arrangements, rooting physiology, nor insect/microbe interactions.", style="color: #808080; font-size: 15px;")
                ),
                style="padding: 60px 50px; font-size: 16px; display: flex; flex-direction: column; justify-content: space-between;"
            ),
            ui.column(
                6,  # Right column taking the other half
                ui.img(src="/img/homepage.jpg", style="width: 95%; height: 100%; object-fit: cover;"),
                style="display: flex; align-items: stretch; padding: 0px 0px;"
            ),
        ),
        style="display: flex; align-items: stretch; padding: 10px 20px;",
    )
)
