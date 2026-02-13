"""Start / Início tab — two-step welcome flow."""
from shiny import ui
import faicons as fa
from custom_ui.i18n import t, tab_title
from custom_ui.nav_buttons import nav_buttons


def _step_card(number, icon_name, pt_text, en_text):
    """A numbered step card for the right-side overlay."""
    return ui.div(
        ui.div(str(number), class_="step-card-number"),
        ui.div(fa.icon_svg(icon_name), class_="step-card-icon"),
        ui.p(t(pt_text, en_text), class_="step-card-text"),
        class_="step-card",
    )


start = ui.nav_panel(
    tab_title(0, "Início", "Start"),
    ui.page_fluid(
        # Set default database_choice value on load
        ui.tags.script(
            "document.addEventListener('DOMContentLoaded', function() {"
            "  var _checkShiny = setInterval(function() {"
            "    if (window.Shiny && Shiny.setInputValue) {"
            "      Shiny.setInputValue('database_choice', 'try');"
            "      clearInterval(_checkShiny);"
            "    }"
            "  }, 200);"
            "});"
        ),
        # ── Step 1: Welcome ──────────────────────────────
        ui.div(
            ui.row(
                # Left column: text + Começar button
                ui.column(
                    6,
                    ui.div(
                        ui.h2(
                            t(
                                "Combine espécies compatíveis para seu projeto de plantio",
                                "Combine compatible species for your planting project",
                            ),
                            class_="bold-text",
                            style="font-size: 19px; margin-bottom: 16px;",
                        ),
                        ui.p(
                            t(
                                "Encontre informações práticas sobre plantas que provavelmente "
                                "prosperarão juntas em seu terreno agrícola, florestal ou de restauração.",
                                "Find practical information about plants that are likely to thrive "
                                "together in your agricultural, forestry or restoration plot.",
                            ),
                            style="letter-spacing: 0.3px; font-size: 15px; color: #555; margin-bottom: 24px;",
                        ),
                        # Bullet points
                        ui.div(
                            ui.div(
                                ui.span(fa.icon_svg("table-cells"), class_="bullet-icon"),
                                ui.span(
                                    t(
                                        "Entre centenas de milhares de espécies de plantas, filtre aquelas que "
                                        "não são adequadas para sua localização e seus propósitos.",
                                        "From 100,000s of plant species, filter out those not suited "
                                        "for your location and purposes.",
                                    ),
                                ),
                                class_="welcome-bullet",
                            ),
                            ui.div(
                                ui.span(fa.icon_svg("wand-magic-sparkles"), class_="bullet-icon"),
                                ui.span(
                                    t(
                                        "Inspire-se na vegetação natural que prospera na sua região "
                                        "para estruturar o seu plantio.",
                                        "Get inspired by the natural vegetation that thrives in your region "
                                        "to structure your planting.",
                                    ),
                                ),
                                class_="welcome-bullet",
                            ),
                            ui.div(
                                ui.span(fa.icon_svg("paper-plane"), class_="bullet-icon"),
                                ui.span(
                                    t(
                                        "Pule abas se quiser manter todas as opções disponíveis abertas. "
                                        "Reverta as seleções de filtragem anteriores a qualquer momento.",
                                        "Skip tabs to keep all options open. Revert previous filtering "
                                        "selections at any time.",
                                    ),
                                ),
                                class_="welcome-bullet",
                            ),
                            ui.div(
                                ui.span(fa.icon_svg("share-nodes"), class_="bullet-icon"),
                                ui.span(
                                    t(
                                        "Compartilhe a lista das espécies selecionadas para encontrar "
                                        "sementes ou mudas na sua região.",
                                        "Share your selected species list to find seeds or seedlings "
                                        "in your region.",
                                    ),
                                ),
                                class_="welcome-bullet",
                            ),
                            class_="welcome-bullets-container",
                        ),
                        # Começar button
                        ui.div(
                            ui.tags.button(
                                t("Começar →", "Get started →"),
                                class_="btn btn-success btn-comecar",
                                onclick=(
                                    "document.getElementById('start-step-1').style.display='none';"
                                    "document.getElementById('start-step-2').style.display='block';"
                                ),
                            ),
                            style="margin-top: 32px;",
                        ),
                    ),
                    style="padding: 60px 50px; font-size: 15px; display: flex; flex-direction: column; justify-content: center;",
                ),
                # Right column: hero image with step cards overlay
                ui.column(
                    6,
                    ui.img(
                        src="img/homepage.jpg",
                        style="width: 95%; height: 100%; object-fit: cover; border-radius: 8px;",
                    ),
                    style="display: flex; align-items: stretch; padding: 0;",
                ),
            ),
            id="start-step-1",
        ),
        # ── Step 2: Database selection ───────────────────
        ui.div(
            ui.div(
                ui.h4(
                    t("Escolha um banco de dados:", "Choose a database:"),
                    class_="bold-text",
                    style="margin-bottom: 24px;",
                ),
                # Custom radio group
                ui.div(
                    # Option 1
                    ui.div(
                        ui.tags.label(
                            ui.tags.input(
                                type="radio",
                                name="db_choice",
                                value="try",
                                checked="checked",
                                onchange="document.querySelectorAll('.db-option-card').forEach(c=>c.classList.remove('selected')); this.closest('.db-option-card').classList.add('selected');",
                            ),
                            ui.span(
                                t("Poucas espécies comuns.", "Few common species."),
                                class_="db-option-title",
                            ),
                            class_="db-option-header",
                        ),
                        ui.div(
                            ui.div("✗ ", t("Poucas espécies comuns.", "Few common species."), class_="db-trait db-con"),
                            ui.div("✓ ", t("Rápido.", "Fast."), class_="db-trait db-pro"),
                            ui.div("✓ ", t("Traços de gestão prática.", "Practical management traits."), class_="db-trait db-pro"),
                            ui.div("✗ ", t("Desconsidera localização.", "Ignores location."), class_="db-trait db-con"),
                            class_="db-traits-list",
                        ),
                        class_="db-option-card selected",
                    ),
                    # Option 2
                    ui.div(
                        ui.tags.label(
                            ui.tags.input(
                                type="radio",
                                name="db_choice",
                                value="gift",
                                onchange="document.querySelectorAll('.db-option-card').forEach(c=>c.classList.remove('selected')); this.closest('.db-option-card').classList.add('selected');",
                            ),
                            ui.span(
                                t("Espécies mais conhecidas.", "Most known species."),
                                class_="db-option-title",
                            ),
                            class_="db-option-header",
                        ),
                        ui.div(
                            ui.div("✗ ", t("Lento.", "Slow."), class_="db-trait db-con"),
                            ui.div("✓ ", t("Detalhes botânicos.", "Botanical details."), class_="db-trait db-pro"),
                            ui.div("✓ ", t("Filtrado por sua localização.", "Filtered by your location."), class_="db-trait db-pro"),
                            class_="db-traits-list",
                        ),
                        class_="db-option-card",
                        style="margin-top: 16px;",
                    ),
                    class_="db-options-container",
                ),
                ui.p(
                    t(
                        "Em construção: integrando e expandindo ambos os bancos de dados para um único fluxo de pesquisa.",
                        "Under construction: integrating & expanding both databases for a single search flow.",
                    ),
                    style="color: #808080; font-size: 13px; margin-top: 20px;",
                ),
                # Buttons: Voltar + Próximo
                ui.div(
                    ui.tags.button(
                        t("← Voltar", "← Back"),
                        class_="btn btn-outline-secondary nav-btn",
                        onclick=(
                            "document.getElementById('start-step-2').style.display='none';"
                            "document.getElementById('start-step-1').style.display='block';"
                        ),
                    ),
                    ui.div(style="flex-grow: 1;"),
                    ui.tags.button(
                        t("Próximo →", "Next →"),
                        class_="btn btn-success nav-btn",
                        onclick=(
                            "var sel = document.querySelector('input[name=db_choice]:checked').value;"
                            "Shiny.setInputValue('database_choice', sel, {priority: 'event'});"
                            "Shiny.setInputValue('_nav_to', 'tab_location', {priority: 'event'});"
                        ),
                    ),
                    class_="nav-buttons d-flex mt-4 mb-3",
                ),
                class_="db-selection-panel",
            ),
            id="start-step-2",
            style="display: none;",
        ),
        style="display: flex; flex-direction: column; align-items: stretch; padding: 10px 20px;",
    ),
    value="tab_start",
)
