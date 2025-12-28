"""METAR station input dialog widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class METARInputDialog(ModalScreen[str | None]):
    """Modal dialog for entering an ICAO station ID."""

    DEFAULT_CSS = """
    METARInputDialog {
        align: center middle;
    }

    METARInputDialog > Vertical {
        width: 55;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    METARInputDialog .dialog-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    METARInputDialog .dialog-help {
        color: $text-muted;
        margin-bottom: 1;
    }

    METARInputDialog Input {
        margin-bottom: 1;
    }

    METARInputDialog .button-row {
        height: 3;
        align: center middle;
    }

    METARInputDialog Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("METAR Lookup", classes="dialog-title")
            yield Label(
                "Enter 4-letter ICAO station code (e.g., KORD, KDFW, KJFK):",
                classes="dialog-help",
            )
            yield Input(
                placeholder="Station ID",
                max_length=4,
                id="station-input",
            )
            with Horizontal(classes="button-row"):
                yield Button("Lookup", variant="primary", id="btn-submit")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#station-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-submit":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in input."""
        self._submit()

    def _submit(self) -> None:
        """Submit the station ID."""
        station_input = self.query_one("#station-input", Input)
        station_id = station_input.value.strip().upper()

        # ICAO codes are 4 letters (typically K + 3 letters for US stations)
        if len(station_id) == 4 and station_id.isalpha():
            self.dismiss(station_id)
        elif len(station_id) == 3 and station_id.isalpha():
            # Auto-prefix with K for US stations
            self.dismiss(f"K{station_id}")
        else:
            self.notify("Please enter a valid 3 or 4-letter station code", severity="error")

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)
