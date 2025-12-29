"""WFO details screen modal widget."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from wxdxx.models.wfo import WFO_CITIES


class WFODetailsScreen(ModalScreen[None]):
    """Modal screen showing WFO details."""

    DEFAULT_CSS = """
    WFODetailsScreen {
        align: center middle;
    }

    WFODetailsScreen > VerticalScroll {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    WFODetailsScreen .details-content {
        padding: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, wfo_id: str, wfo_info: dict) -> None:
        super().__init__()
        self.wfo_id = wfo_id.upper()
        self.wfo_info = wfo_info

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self._format_details(), classes="details-content")

    def _format_details(self) -> str:
        """Format WFO details for display."""
        info = self.wfo_info

        # Extract fields from NWS API response
        name = info.get("name", "Unknown")
        address = info.get("address", {})
        street = address.get("streetAddress", "")
        city = address.get("addressLocality", "")
        state = address.get("addressRegion", "")
        zip_code = address.get("postalCode", "")
        telephone = info.get("telephone", "")

        # Count zones and counties
        forecast_zones = info.get("responsibleForecastZones", [])
        counties = info.get("responsibleCounties", [])
        fire_zones = info.get("responsibleFireZones", [])

        # Build display text
        lines = [
            f"[bold cyan]WFO {self.wfo_id}[/bold cyan]",
            f"[bold]{name}[/bold]",
            "",
        ]

        # Address section
        if street or city:
            lines.append("[bold]Address[/bold]")
            if street:
                lines.append(f"  {street}")
            if city and state:
                addr_line = f"  {city}, {state}"
                if zip_code:
                    addr_line += f" {zip_code}"
                lines.append(addr_line)
            lines.append("")

        # Contact section
        if telephone:
            lines.append("[bold]Contact[/bold]")
            lines.append(f"  Phone: {telephone}")
            lines.append("")

        # Coverage section
        lines.append("[bold]Coverage Area[/bold]")
        lines.append(f"  Forecast Zones: {len(forecast_zones)}")
        lines.append(f"  Counties: {len(counties)}")
        if fire_zones:
            lines.append(f"  Fire Weather Zones: {len(fire_zones)}")

        # Major cities section
        cities = WFO_CITIES.get(self.wfo_id, [])
        if cities:
            lines.append("")
            lines.append("[bold]Major Cities[/bold]")
            for city in cities:
                lines.append(f"  {city}")

        lines.append("")
        lines.append("[dim]Press Escape to close[/dim]")

        return "\n".join(lines)

    def action_close(self) -> None:
        """Close the details screen."""
        self.dismiss(None)
