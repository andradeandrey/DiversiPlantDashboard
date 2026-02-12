"""Admin panel UI for DiversiPlant Dashboard."""
from shiny import ui
import faicons as fa

# Admin panel icons
ADMIN_ICONS = {
    "database": fa.icon_svg("database"),
    "refresh": fa.icon_svg("rotate"),
    "log": fa.icon_svg("file-lines"),
    "chart": fa.icon_svg("chart-line"),
    "users": fa.icon_svg("users"),
    "check": fa.icon_svg("circle-check"),
    "error": fa.icon_svg("circle-exclamation"),
    "running": fa.icon_svg("spinner"),
}

admin = ui.nav_panel(
    "Admin",  # Admin tab stays English-only (internal tool)
    ui.page_fluid(
        ui.h2("Admin Panel", class_="admin-title"),

        # Status Overview Cards
        ui.div(
            ui.row(
                # Crawler Status Card
                ui.column(
                    6,
                    ui.card(
                        ui.card_header(
                            ui.div(
                                ADMIN_ICONS["database"],
                                ui.span(" Crawler Status", style="margin-left: 8px;"),
                                style="display: flex; align-items: center;"
                            )
                        ),
                        ui.card_body(
                            ui.output_ui("crawler_status_cards")
                        )
                    )
                ),
                # Database Metrics Card
                ui.column(
                    6,
                    ui.card(
                        ui.card_header(
                            ui.div(
                                ADMIN_ICONS["chart"],
                                ui.span(" Database Metrics", style="margin-left: 8px;"),
                                style="display: flex; align-items: center;"
                            )
                        ),
                        ui.card_body(
                            ui.output_ui("database_metrics")
                        )
                    )
                ),
            ),
            class_="admin-overview"
        ),

        ui.hr(),

        # Tabbed interface for admin functions
        ui.navset_tab(
            # Crawler Logs Tab
            ui.nav_panel(
                "Logs",
                ui.div(
                    ui.row(
                        ui.column(
                            4,
                            ui.input_select(
                                "log_crawler_filter",
                                "Filter by Crawler:",
                                choices={
                                    "all": "All Crawlers",
                                    "reflora": "REFLORA",
                                    "gbif": "GBIF",
                                    "gift": "GIFT",
                                    "wcvp": "WCVP",
                                    "worldclim": "WorldClim",
                                    "treegoer": "TreeGOER",
                                    "iucn": "IUCN",
                                }
                            )
                        ),
                        ui.column(
                            4,
                            ui.input_select(
                                "log_level_filter",
                                "Filter by Level:",
                                choices={
                                    "all": "All Levels",
                                    "ERROR": "Error",
                                    "WARNING": "Warning",
                                    "INFO": "Info",
                                    "DEBUG": "Debug",
                                }
                            )
                        ),
                        ui.column(
                            4,
                            ui.input_action_button(
                                "refresh_logs",
                                "Refresh Logs",
                                class_="btn-primary",
                                style="margin-top: 25px;"
                            )
                        ),
                    ),
                    ui.output_ui("crawler_logs_table"),
                    class_="admin-logs"
                )
            ),

            # Species CRUD Tab
            ui.nav_panel(
                "Species",
                ui.div(
                    ui.row(
                        ui.column(
                            8,
                            ui.input_text(
                                "species_search",
                                "Search Species:",
                                placeholder="Enter species name..."
                            )
                        ),
                        ui.column(
                            4,
                            ui.input_action_button(
                                "search_species_btn",
                                "Search",
                                class_="btn-primary",
                                style="margin-top: 25px;"
                            )
                        ),
                    ),
                    ui.output_ui("species_search_results"),
                    ui.hr(),
                    ui.h4("Add/Edit Species"),
                    ui.row(
                        ui.column(
                            6,
                            ui.input_text("species_canonical_name", "Canonical Name:"),
                            ui.input_text("species_genus", "Genus:"),
                            ui.input_text("species_family", "Family:"),
                        ),
                        ui.column(
                            6,
                            ui.input_select(
                                "species_growth_form",
                                "Growth Form:",
                                choices={
                                    "": "Select...",
                                    "tree": "Tree",
                                    "shrub": "Shrub",
                                    "herb": "Herb",
                                    "climber": "Climber",
                                    "palm": "Palm",
                                    "bamboo": "Bamboo",
                                    "fern": "Fern",
                                }
                            ),
                            ui.input_select(
                                "species_status",
                                "Status:",
                                choices={
                                    "accepted": "Accepted",
                                    "synonym": "Synonym",
                                    "unresolved": "Unresolved",
                                }
                            ),
                        ),
                    ),
                    ui.input_action_button(
                        "save_species_btn",
                        "Save Species",
                        class_="btn-success"
                    ),
                    class_="admin-species"
                )
            ),

            # Common Names Tab
            ui.nav_panel(
                "Common Names",
                ui.div(
                    ui.row(
                        ui.column(
                            6,
                            ui.input_text(
                                "common_name_species",
                                "Species (canonical name):",
                                placeholder="Araucaria angustifolia"
                            )
                        ),
                        ui.column(
                            3,
                            ui.input_text(
                                "common_name_value",
                                "Common Name:",
                                placeholder="Araucária"
                            )
                        ),
                        ui.column(
                            3,
                            ui.input_select(
                                "common_name_lang",
                                "Language:",
                                choices={"pt": "Portuguese", "en": "English"}
                            )
                        ),
                    ),
                    ui.input_action_button(
                        "add_common_name_btn",
                        "Add Common Name",
                        class_="btn-success"
                    ),
                    ui.hr(),
                    ui.h4("Common Names by Language"),
                    ui.output_ui("common_names_stats"),
                    class_="admin-names"
                )
            ),

            # Crawler Controls Tab
            ui.nav_panel(
                "Controls",
                ui.div(
                    ui.h4("Manual Crawler Execution"),
                    ui.p("Run crawlers manually for immediate data updates."),
                    ui.row(
                        ui.column(
                            4,
                            ui.input_select(
                                "manual_crawler",
                                "Select Crawler:",
                                choices={
                                    "reflora": "REFLORA",
                                    "gbif": "GBIF",
                                    "gift": "GIFT",
                                    "wcvp": "WCVP",
                                    "worldclim": "WorldClim",
                                    "treegoer": "TreeGOER",
                                    "iucn": "IUCN",
                                }
                            )
                        ),
                        ui.column(
                            4,
                            ui.input_select(
                                "crawler_mode",
                                "Mode:",
                                choices={
                                    "incremental": "Incremental",
                                    "full": "Full Refresh",
                                }
                            )
                        ),
                        ui.column(
                            4,
                            ui.input_action_button(
                                "run_crawler_btn",
                                "Run Crawler",
                                class_="btn-warning",
                                style="margin-top: 25px;"
                            )
                        ),
                    ),
                    ui.output_ui("crawler_run_status"),
                    ui.hr(),
                    ui.h4("Schedule Configuration"),
                    ui.output_ui("schedule_config"),
                    class_="admin-controls"
                )
            ),

            # User Metrics Tab
            ui.nav_panel(
                "Metrics",
                ui.div(
                    ui.row(
                        ui.column(
                            4,
                            ui.card(
                                ui.card_header("Page Views (24h)"),
                                ui.card_body(
                                    ui.output_text("page_views_24h"),
                                    class_="metric-value"
                                )
                            )
                        ),
                        ui.column(
                            4,
                            ui.card(
                                ui.card_header("Unique Sessions (24h)"),
                                ui.card_body(
                                    ui.output_text("unique_sessions_24h"),
                                    class_="metric-value"
                                )
                            )
                        ),
                        ui.column(
                            4,
                            ui.card(
                                ui.card_header("Species Searches (24h)"),
                                ui.card_body(
                                    ui.output_text("species_searches_24h"),
                                    class_="metric-value"
                                )
                            )
                        ),
                    ),
                    ui.hr(),
                    ui.h4("Access Log"),
                    ui.output_ui("access_log_table"),
                    class_="admin-metrics"
                )
            ),
        ),

        # Admin CSS
        ui.tags.style("""
            .admin-title {
                color: #2c3e50;
                margin-bottom: 20px;
            }
            .admin-overview {
                margin-bottom: 20px;
            }
            .metric-value {
                font-size: 2em;
                font-weight: bold;
                text-align: center;
                color: #27ae60;
            }
            .status-badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.85em;
                font-weight: bold;
            }
            .status-running {
                background-color: #3498db;
                color: white;
            }
            .status-completed {
                background-color: #27ae60;
                color: white;
            }
            .status-failed {
                background-color: #e74c3c;
                color: white;
            }
            .status-idle {
                background-color: #95a5a6;
                color: white;
            }
            .log-viewer {
                background-color: #1e1e1e;
                color: #d4d4d4;
                padding: 15px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.85em;
                max-height: 400px;
                overflow-y: auto;
            }
            .crawler-card {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
                margin: 5px;
                display: inline-block;
                min-width: 150px;
            }
        """)
    ),
    value="tab_admin",
)
