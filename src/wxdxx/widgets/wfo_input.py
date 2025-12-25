"""WFO input dialog widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class WFOInputDialog(ModalScreen[str | None]):
    """Modal dialog for entering a WFO ID."""

    DEFAULT_CSS = """
    WFOInputDialog {
        align: center middle;
    }

    WFOInputDialog > Vertical {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    WFOInputDialog .dialog-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    WFOInputDialog .dialog-help {
        color: $text-muted;
        margin-bottom: 1;
    }

    WFOInputDialog Input {
        margin-bottom: 1;
    }

    WFOInputDialog .button-row {
        height: 3;
        align: center middle;
    }

    WFOInputDialog Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Add WFO", classes="dialog-title")
            yield Label(
                "Enter 3-letter WFO ID (e.g., OUN, FWD, ICT):",
                classes="dialog-help",
            )
            yield Input(
                placeholder="WFO ID",
                max_length=3,
                id="wfo-input",
            )
            with Horizontal(classes="button-row"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#wfo-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-add":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in input."""
        self._submit()

    def _submit(self) -> None:
        """Submit the WFO ID."""
        wfo_input = self.query_one("#wfo-input", Input)
        wfo_id = wfo_input.value.strip().upper()
        if len(wfo_id) == 3 and wfo_id.isalpha():
            self.dismiss(wfo_id)
        else:
            self.notify("Please enter a valid 3-letter WFO ID", severity="error")

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)
