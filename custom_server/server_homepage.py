# This would go in your custom_server/server_homepage.py file

from shiny import reactive, ui

def server_homepage(input, output, session):
    # This function will handle the begin button click
    @reactive.effect
    @reactive.event(input.begin_button)
    def _handle_begin_button():
        # Check which database is selected
        if input.database_choice() == "✔️ Practical management traits. ✔️ Fast.  ❌ Few common species. ❌ Ignores location.":
            # If using Practitioner's Database, navigate to the Species tab
            # using JavaScript
            session.send_custom_message("navigate_to_tab", "Main Species")
        else:
            # If using GIFT Database, navigate to the Location tab
            # using JavaScript
            session.send_custom_message("navigate_to_tab", "Location (GIFT Database)")