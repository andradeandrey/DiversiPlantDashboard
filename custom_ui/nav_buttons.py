"""Reusable Voltar / Próximo navigation buttons."""
from shiny import ui
from custom_ui.i18n import t


def nav_buttons(back_value=None, next_value=None):
    """Navigation buttons at the bottom of each tab.

    Args:
        back_value: Tab value to navigate back to (None = no back button).
        next_value: Tab value to navigate forward to (None = no next button).
    """
    items = []

    if back_value:
        items.append(
            ui.tags.button(
                t("Voltar", "Back"),
                class_="btn btn-outline-secondary nav-btn",
                onclick=f"Shiny.setInputValue('_nav_to', '{back_value}', {{priority: 'event'}});",
            )
        )

    items.append(ui.div(style="flex-grow: 1;"))

    if next_value:
        items.append(
            ui.tags.button(
                t("Próximo", "Next"),
                class_="btn btn-success nav-btn",
                onclick=f"Shiny.setInputValue('_nav_to', '{next_value}', {{priority: 'event'}});",
            )
        )

    return ui.div(*items, class_="nav-buttons d-flex mt-4 mb-3")
