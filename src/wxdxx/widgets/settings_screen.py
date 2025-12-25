"""Settings screen modal widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class SettingsScreen(ModalScreen[int | None]):
    """Modal screen for application settings.

    Returns the new refresh interval if changed, None if cancelled.
    """

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    SettingsScreen > Vertical {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    SettingsScreen .settings-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    SettingsScreen .settings-label {
        color: $text-muted;
        margin-bottom: 0;
    }

    SettingsScreen .settings-row {
        height: 3;
        margin-bottom: 1;
    }

    SettingsScreen .settings-row Input {
        width: 10;
    }

    SettingsScreen .settings-row Label {
        padding: 1 0 0 1;
    }

    SettingsScreen .wfo-list {
        padding-left: 2;
        color: $text;
        margin-bottom: 1;
    }

    SettingsScreen .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    SettingsScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(
        self,
        current_refresh_interval: int,
        tracked_wfos: list[str],
    ) -> None:
        super().__init__()
        self._refresh_interval = current_refresh_interval
        self._tracked_wfos = list(tracked_wfos)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Settings", classes="settings-title")

            # Refresh Interval Section
            yield Static("Refresh Interval", classes="settings-label")
            with Horizontal(classes="settings-row"):
                yield Input(
                    value=str(self._refresh_interval),
                    placeholder="60",
                    max_length=3,
                    id="refresh-input",
                )
                yield Label("seconds (10-600)")

            # Tracked WFOs Section
            yield Static("Tracked WFOs", classes="settings-label")
            wfo_text = ", ".join(self._tracked_wfos) if self._tracked_wfos else "(none)"
            yield Static(wfo_text, classes="wfo-list", id="wfo-display")
            yield Static(
                "Use 'w' to add, 'W' to remove WFOs",
                classes="settings-label",
            )

            # Buttons
            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Close", id="btn-close")

    def on_mount(self) -> None:
        """Focus the refresh input on mount."""
        self.query_one("#refresh-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-save":
            self._save_settings()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in input."""
        self._save_settings()

    def _save_settings(self) -> None:
        """Validate and save settings."""
        refresh_input = self.query_one("#refresh-input", Input)

        try:
            new_interval = int(refresh_input.value)
            if not (10 <= new_interval <= 600):
                raise ValueError("Out of range")
        except ValueError:
            self.notify(
                "Refresh interval must be a number between 10 and 600",
                severity="error",
            )
            return

        self.dismiss(new_interval)

    def action_close(self) -> None:
        """Close the settings screen."""
        self.dismiss(None)
