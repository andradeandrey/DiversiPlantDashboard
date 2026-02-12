"""Bilingual (PT-BR / EN) support for DiversiPlant Dashboard.

Usage:
  - Body starts with class 'lang-pt' (default).
  - CSS hides .i18n-en when lang-pt, and .i18n-pt when lang-en.
  - Language toggle button switches body class via JS.
"""
from shiny import ui


def t(pt: str, en: str):
    """Return bilingual inline text. CSS controls which language is visible."""
    return ui.span(
        ui.span(pt, class_="i18n-pt"),
        ui.span(en, class_="i18n-en"),
    )


def tab_title(number, pt: str, en: str):
    """Tab title with numbered green badge + bilingual label."""
    return ui.div(
        ui.span(str(number), class_="tab-badge"),
        t(pt, en),
        class_="d-flex align-items-center gap-2",
    )


def lang_toggle():
    """Language toggle button for the navbar."""
    return ui.tags.button(
        ui.span("EN", class_="i18n-pt"),
        ui.span("PT", class_="i18n-en"),
        class_="btn btn-sm btn-outline-dark lang-toggle",
        onclick="document.body.classList.toggle('lang-en');document.body.classList.toggle('lang-pt');",
        title="Switch language / Trocar idioma",
    )


def lang_init_script():
    """Script to set default language to PT-BR on page load."""
    return ui.tags.script(
        "document.addEventListener('DOMContentLoaded',function(){"
        "document.body.classList.add('lang-pt');"
        "});"
    )
