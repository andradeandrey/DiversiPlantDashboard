"""Admin panel server logic for DiversiPlant Dashboard."""
from shiny import render, reactive, ui
from datetime import datetime, timedelta
import os

# Database connection (will use when database is available)
DB_AVAILABLE = False

try:
    from database.connection import get_db
    DB_AVAILABLE = True
except ImportError:
    pass


def server_admin(input, output, session):
    """Server logic for admin panel."""

    # ==========================================
    # Crawler Status Cards
    # ==========================================

    @output
    @render.ui
    def crawler_status_cards():
        """Render crawler status cards."""
        if not DB_AVAILABLE:
            return ui.div(
                ui.p("Database not connected. Configure DATABASE_URL to view crawler status."),
                class_="alert alert-warning"
            )

        try:
            db = get_db()
            result = db.execute("""
                SELECT crawler_name, status, last_run, last_success,
                       records_processed, error_count
                FROM crawler_status
                ORDER BY crawler_name
            """)

            cards = []
            for row in result:
                name, status, last_run, last_success, records, errors = row

                status_class = {
                    'running': 'status-running',
                    'completed': 'status-completed',
                    'failed': 'status-failed',
                    'idle': 'status-idle'
                }.get(status, 'status-idle')

                last_success_str = last_success.strftime('%Y-%m-%d %H:%M') if last_success else 'Never'

                cards.append(
                    ui.div(
                        ui.strong(name.upper()),
                        ui.br(),
                        ui.span(status, class_=f"status-badge {status_class}"),
                        ui.br(),
                        ui.small(f"Last: {last_success_str}"),
                        ui.br(),
                        ui.small(f"Records: {records or 0}"),
                        class_="crawler-card"
                    )
                )

            return ui.div(*cards, style="display: flex; flex-wrap: wrap;")

        except Exception as e:
            return ui.div(
                ui.p(f"Error loading crawler status: {e}"),
                class_="alert alert-danger"
            )

    # ==========================================
    # Database Metrics
    # ==========================================

    @output
    @render.ui
    def database_metrics():
        """Render database metrics."""
        if not DB_AVAILABLE:
            return ui.div(
                ui.p("Database not connected."),
                class_="alert alert-warning"
            )

        try:
            db = get_db()

            # Get counts
            species_count = db.execute_scalar("SELECT COUNT(*) FROM species") or 0
            traits_count = db.execute_scalar("SELECT COUNT(*) FROM species_traits") or 0
            names_count = db.execute_scalar("SELECT COUNT(*) FROM common_names") or 0

            # Traits coverage
            coverage = 0
            if species_count > 0:
                with_traits = db.execute_scalar(
                    "SELECT COUNT(DISTINCT species_id) FROM species_traits"
                ) or 0
                coverage = round(with_traits / species_count * 100, 1)

            return ui.div(
                ui.div(
                    ui.strong("Species: "), f"{species_count:,}",
                    class_="mb-2"
                ),
                ui.div(
                    ui.strong("Common Names: "), f"{names_count:,}",
                    class_="mb-2"
                ),
                ui.div(
                    ui.strong("Traits Records: "), f"{traits_count:,}",
                    class_="mb-2"
                ),
                ui.div(
                    ui.strong("Traits Coverage: "), f"{coverage}%",
                    class_="mb-2"
                ),
            )

        except Exception as e:
            return ui.div(
                ui.p(f"Error loading metrics: {e}"),
                class_="alert alert-danger"
            )

    # ==========================================
    # Crawler Logs
    # ==========================================

    @output
    @render.ui
    def crawler_logs_table():
        """Render crawler logs table."""
        if not DB_AVAILABLE:
            return ui.pre("Database not connected.", class_="log-viewer")

        crawler_filter = input.log_crawler_filter()
        level_filter = input.log_level_filter()

        try:
            db = get_db()

            query = """
                SELECT timestamp, crawler_name, level, message
                FROM crawler_logs
                WHERE 1=1
            """
            params = {}

            if crawler_filter and crawler_filter != 'all':
                query += " AND crawler_name = :crawler"
                params['crawler'] = crawler_filter

            if level_filter and level_filter != 'all':
                query += " AND level = :level"
                params['level'] = level_filter

            query += " ORDER BY timestamp DESC LIMIT 100"

            result = db.execute(query, params)

            log_lines = []
            for row in result:
                ts, crawler, level, msg = row
                ts_str = ts.strftime('%Y-%m-%d %H:%M:%S') if ts else ''
                log_lines.append(f"[{ts_str}] [{level}] [{crawler}] {msg}")

            if not log_lines:
                log_lines = ["No log entries found."]

            return ui.pre("\n".join(log_lines), class_="log-viewer")

        except Exception as e:
            return ui.pre(f"Error loading logs: {e}", class_="log-viewer")

    # ==========================================
    # Species Search
    # ==========================================

    @output
    @render.ui
    def species_search_results():
        """Render species search results."""
        if not DB_AVAILABLE:
            return ui.p("Database not connected.")

        search_term = input.species_search()
        if not search_term or len(search_term) < 2:
            return ui.p("Enter at least 2 characters to search.")

        try:
            db = get_db()

            result = db.execute("""
                SELECT s.id, s.canonical_name, s.family, st.growth_form
                FROM species s
                LEFT JOIN species_traits st ON s.id = st.species_id
                WHERE s.canonical_name ILIKE :term
                ORDER BY s.canonical_name
                LIMIT 20
            """, {'term': f'%{search_term}%'})

            rows = list(result)
            if not rows:
                return ui.p("No species found.")

            table_rows = []
            for row in rows:
                id_, name, family, growth_form = row
                table_rows.append(
                    ui.tags.tr(
                        ui.tags.td(str(id_)),
                        ui.tags.td(name),
                        ui.tags.td(family or '-'),
                        ui.tags.td(growth_form or '-'),
                    )
                )

            return ui.tags.table(
                ui.tags.thead(
                    ui.tags.tr(
                        ui.tags.th("ID"),
                        ui.tags.th("Name"),
                        ui.tags.th("Family"),
                        ui.tags.th("Growth Form"),
                    )
                ),
                ui.tags.tbody(*table_rows),
                class_="table table-striped"
            )

        except Exception as e:
            return ui.p(f"Error searching: {e}")

    # ==========================================
    # Common Names Stats
    # ==========================================

    @output
    @render.ui
    def common_names_stats():
        """Render common names statistics."""
        if not DB_AVAILABLE:
            return ui.p("Database not connected.")

        try:
            db = get_db()

            result = db.execute("""
                SELECT language, COUNT(*) as count
                FROM common_names
                GROUP BY language
                ORDER BY count DESC
            """)

            rows = list(result)
            if not rows:
                return ui.p("No common names in database.")

            items = []
            for lang, count in rows:
                lang_name = {'en': 'English', 'pt': 'Portuguese'}.get(lang, lang)
                items.append(ui.li(f"{lang_name}: {count:,} names"))

            return ui.tags.ul(*items)

        except Exception as e:
            return ui.p(f"Error: {e}")

    # ==========================================
    # User Metrics
    # ==========================================

    @output
    @render.text
    def page_views_24h():
        """Get page views in last 24 hours."""
        if not DB_AVAILABLE:
            return "N/A"

        try:
            db = get_db()
            count = db.execute_scalar("""
                SELECT COUNT(*)
                FROM user_access_log
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """) or 0
            return str(count)
        except Exception:
            return "0"

    @output
    @render.text
    def unique_sessions_24h():
        """Get unique sessions in last 24 hours."""
        if not DB_AVAILABLE:
            return "N/A"

        try:
            db = get_db()
            count = db.execute_scalar("""
                SELECT COUNT(DISTINCT session_id)
                FROM user_access_log
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """) or 0
            return str(count)
        except Exception:
            return "0"

    @output
    @render.text
    def species_searches_24h():
        """Get species searches in last 24 hours."""
        if not DB_AVAILABLE:
            return "N/A"

        try:
            db = get_db()
            count = db.execute_scalar("""
                SELECT COUNT(*)
                FROM user_access_log
                WHERE timestamp > NOW() - INTERVAL '24 hours'
                AND action = 'species_search'
            """) or 0
            return str(count)
        except Exception:
            return "0"

    @output
    @render.ui
    def access_log_table():
        """Render recent access log."""
        if not DB_AVAILABLE:
            return ui.p("Database not connected.")

        try:
            db = get_db()

            result = db.execute("""
                SELECT timestamp, session_id, page, action, ip_address
                FROM user_access_log
                ORDER BY timestamp DESC
                LIMIT 50
            """)

            rows = list(result)
            if not rows:
                return ui.p("No access logs.")

            table_rows = []
            for row in rows:
                ts, session, page, action, ip = row
                ts_str = ts.strftime('%Y-%m-%d %H:%M') if ts else ''
                table_rows.append(
                    ui.tags.tr(
                        ui.tags.td(ts_str),
                        ui.tags.td(session[:8] + '...' if session else '-'),
                        ui.tags.td(page or '-'),
                        ui.tags.td(action or '-'),
                    )
                )

            return ui.tags.table(
                ui.tags.thead(
                    ui.tags.tr(
                        ui.tags.th("Time"),
                        ui.tags.th("Session"),
                        ui.tags.th("Page"),
                        ui.tags.th("Action"),
                    )
                ),
                ui.tags.tbody(*table_rows),
                class_="table table-striped"
            )

        except Exception as e:
            return ui.p(f"Error: {e}")

    # ==========================================
    # Crawler Run Status
    # ==========================================

    @output
    @render.ui
    def crawler_run_status():
        """Show status of manual crawler run."""
        return ui.div()

    @output
    @render.ui
    def schedule_config():
        """Show current schedule configuration."""
        schedules = [
            ("REFLORA", "Sunday 2:00 AM"),
            ("GBIF", "Sunday 3:00 AM"),
            ("GIFT", "1st of month 4:00 AM"),
            ("WCVP", "1st of month 5:00 AM"),
            ("WorldClim", "Jan 1 & Jul 1, 6:00 AM"),
            ("TreeGOER", "15th of month 2:00 AM"),
            ("IUCN", "1st of month 3:00 AM"),
        ]

        rows = []
        for name, schedule in schedules:
            rows.append(
                ui.tags.tr(
                    ui.tags.td(name),
                    ui.tags.td(schedule),
                )
            )

        return ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Crawler"),
                    ui.tags.th("Schedule"),
                )
            ),
            ui.tags.tbody(*rows),
            class_="table table-striped"
        )
