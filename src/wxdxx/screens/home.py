"""Home screen for SPC Dash."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Static


class HomeScreen(Screen):
    """Initial home/dashboard screen."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Welcome to SPC Dash", classes="title"),
            Static(
                "Select a product category from the sidebar to get started.",
                classes="subtitle",
            ),
            classes="home-container",
        )
