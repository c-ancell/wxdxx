"""Help screen modal widget."""

from importlib.metadata import version

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

try:
    __version__ = version("wxdxx")
except Exception:
    __version__ = "dev"


HELP_TEXT = f"""\
[bold cyan]WxDXX v{__version__}[/bold cyan]

[bold]General[/bold]
  q          Quit application
  r          Manual refresh (data auto-refreshes every 60s)
  s          Open settings
  ?          Toggle this help screen
  Tab        Switch focus between sidebar and content
  M          Mark all sidebar items as read

[bold]Navigation[/bold]
  1          View Day 1 Outlook
  2          View Day 2 Outlook
  3          View Day 3 Outlook
  m          Toggle zone map (when viewing alerts)

[bold]WFO Products[/bold]
  w          Add a WFO to track
  W          Remove a tracked WFO
  L          Lookup WFO details

[bold]Scrolling (Sidebar & Content)[/bold]
  j / ↓      Move down one item/line
  k / ↑      Move up one item/line
  d          Page down
  u          Page up
  g          Jump to top
  G          Jump to bottom

[bold]Product Abbreviations[/bold]
  AFD        Area Forecast Discussion
  ZFP        Zone Forecast Product
  NOW        Short Term Forecast
  HWO        Hazardous Weather Outlook
  SPS        Special Weather Statement

[dim]Press ? or Escape to close[/dim]
"""


class HelpScreen(ModalScreen[None]):
    """Modal screen showing keyboard shortcuts and help."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > VerticalScroll {
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
        with VerticalScroll():
            yield Static(HELP_TEXT, classes="help-content")

    def action_close(self) -> None:
        """Close the help screen."""
        self.dismiss(None)
