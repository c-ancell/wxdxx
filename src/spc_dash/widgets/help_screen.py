"""Help screen modal widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


HELP_TEXT = """\
[bold cyan]SPC Dash - Keyboard Shortcuts[/bold cyan]

[bold]General[/bold]
  q          Quit application
  r          Manual refresh (data auto-refreshes every 60s)
  ?          Toggle this help screen
  Tab        Switch focus between sidebar and content

[bold]Navigation[/bold]
  1          View Day 1 Outlook
  2          View Day 2 Outlook
  3          View Day 3 Outlook

[bold]WFO Products[/bold]
  w          Add a WFO to track
  W          Remove a tracked WFO

[bold]Content Scrolling[/bold]
  j / ↓      Scroll down one line
  k / ↑      Scroll up one line
  d          Page down
  u          Page up
  g          Jump to top
  G          Jump to bottom

[dim]Press ? or Escape to close[/dim]
"""


class HelpScreen(ModalScreen[None]):
    """Modal screen showing keyboard shortcuts and help."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Vertical {
        width: 50;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    HelpScreen .help-content {
        padding: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("question_mark", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(HELP_TEXT, classes="help-content")

    def action_close(self) -> None:
        """Close the help screen."""
        self.dismiss(None)
