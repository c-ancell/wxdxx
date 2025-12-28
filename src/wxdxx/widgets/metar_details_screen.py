"""METAR details screen modal widget."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ..models.observation import Observation


class METARDetailsScreen(ModalScreen[None]):
    """Modal screen showing METAR observation details."""

    DEFAULT_CSS = """
    METARDetailsScreen {
        align: center middle;
    }

    METARDetailsScreen > VerticalScroll {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    METARDetailsScreen .details-content {
        padding: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, station_id: str, observation: Observation) -> None:
        super().__init__()
        self.station_id = station_id.upper()
        self.observation = observation

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self._format_details(), classes="details-content")

    def _format_details(self) -> str:
        """Format observation details for display."""
        obs = self.observation
        lines = []

        # Header
        name = obs.text_description or obs.station_name or self.station_id
        lines.append(f"[bold cyan]Current Conditions: {self.station_id}[/bold cyan]")
        lines.append(f"[bold]{name}[/bold]")
        lines.append("")

        # Observation time
        if obs.timestamp:
            lines.append(f"[bold]Observed:[/bold] {obs.timestamp.strftime('%Y-%m-%d %H:%M UTC')}")
            lines.append("")

        # Temperature section
        if obs.temperature_f is not None:
            lines.append(f"[bold]Temperature:[/bold] {obs.temperature_f:.0f}F ({obs.temperature_c:.0f}C)")
        if obs.dewpoint_f is not None:
            lines.append(f"[bold]Dewpoint:[/bold] {obs.dewpoint_f:.0f}F ({obs.dewpoint_c:.0f}C)")
        if obs.relative_humidity_pct is not None:
            lines.append(f"[bold]Humidity:[/bold] {obs.relative_humidity_pct:.0f}%")

        # Feels like
        if obs.wind_chill_c is not None:
            wind_chill_f = (obs.wind_chill_c * 9 / 5) + 32
            lines.append(f"[bold]Wind Chill:[/bold] {wind_chill_f:.0f}F")
        elif obs.heat_index_c is not None:
            heat_index_f = (obs.heat_index_c * 9 / 5) + 32
            lines.append(f"[bold]Heat Index:[/bold] {heat_index_f:.0f}F")

        lines.append("")

        # Wind section
        lines.append(f"[bold]Wind:[/bold] {obs.wind_summary}")

        # Visibility
        if obs.visibility_mi is not None:
            if obs.visibility_mi >= 10:
                lines.append("[bold]Visibility:[/bold] 10+ mi")
            else:
                lines.append(f"[bold]Visibility:[/bold] {obs.visibility_mi:.1f} mi")

        # Pressure
        if obs.barometric_pressure_hpa is not None:
            # Convert hPa to inHg
            pressure_inhg = obs.barometric_pressure_hpa / 33.8639
            lines.append(f"[bold]Pressure:[/bold] {pressure_inhg:.2f} inHg")

        # Raw METAR
        if obs.raw_metar:
            lines.append("")
            lines.append("[bold]Raw METAR:[/bold]")
            lines.append(f"[dim]{obs.raw_metar}[/dim]")

        lines.append("")
        lines.append("[dim]Press Escape to close[/dim]")

        return "\n".join(lines)

    def action_close(self) -> None:
        """Close the details screen."""
        self.dismiss(None)
