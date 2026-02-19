"""Admin Tab — Practitioners CSV Upload.

Ports: handleUploadPractitioners (validates CSV + runs PractitionersCrawler).
"""
import asyncio
import os
import shutil
from shiny import reactive, render, ui
from .helpers import _DB_OK, _no_db, _stat_card


def upload_ui():
    return ui.nav_panel(
        "Upload",
        ui.div(
            ui.p("Upload de CSV de Practitioners", style="color:#ccc;font-size:1em;margin-bottom:8px"),
            ui.p("Colunas obrigatórias: sci_names, family, growth_form",
                 style="color:#666;font-size:0.82em;margin-bottom:16px"),
        ),
        ui.input_file("upl_file", "Arquivo CSV:", accept=[".csv"], multiple=False),
        ui.input_action_button("upl_go", "Processar CSV",
                               class_="btn btn-success",
                               style="margin-top:10px"),
        ui.output_ui("upl_result"),
    )


def upload_server(input, output, session):

    @output
    @render.ui
    @reactive.event(input.upl_go)
    async def upl_result():
        if not _DB_OK:
            return _no_db()

        file_info = input.upl_file()
        if not file_info:
            return ui.div("Nenhum arquivo selecionado.", class_="qe-err")

        file_data = file_info[0]
        src_path = file_data["datapath"]
        filename = file_data["name"]

        # Read and validate header
        import csv
        try:
            with open(src_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
        except Exception as e:
            return ui.div(f"Erro ao ler CSV: {e}", class_="qe-err")

        header_clean = [h.strip() for h in header]
        required = {"sci_names", "family", "growth_form"}
        found = set(header_clean)
        missing = required - found

        if missing:
            return ui.div(
                f"Colunas faltando: {', '.join(sorted(missing))}. "
                f"Encontradas: {', '.join(header_clean)}",
                class_="qe-err",
            )

        # Copy to data/practitioners.csv
        dest = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "practitioners.csv")
        try:
            shutil.copy2(src_path, dest)
        except Exception as e:
            return ui.div(f"Erro ao copiar arquivo: {e}", class_="qe-err")

        # Run PractitionersCrawler in background thread
        try:
            from database.connection import get_database_url
            db_url = get_database_url()

            def _run():
                from crawlers.practitioners import PractitionersCrawler
                crawler = PractitionersCrawler(db_url)
                crawler.run(mode="full")
                return dict(crawler.stats)

            stats = await asyncio.to_thread(_run)

            processed = stats.get("processed", 0)
            inserted = stats.get("inserted", 0)
            updated = stats.get("updated", 0)
            errors = stats.get("errors", 0)

            return ui.div(
                ui.p(f"Arquivo: {filename}", style="color:#888;font-size:0.85em;margin-bottom:12px"),
                ui.div(
                    _stat_card(f"{processed:,}", "Processados"),
                    _stat_card(f"{inserted:,}", "Inseridos", "#22d3ee"),
                    _stat_card(f"{updated:,}", "Atualizados", "#f59e0b"),
                    _stat_card(f"{errors:,}", "Erros", "#f87171" if errors else "#34d399"),
                    class_="stat-grid",
                ),
            )

        except Exception as e:
            return ui.div(f"Erro ao executar crawler: {e}", class_="qe-err")
