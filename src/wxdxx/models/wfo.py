"""Models for WFO text products."""

from datetime import datetime

from pydantic import BaseModel


# NWS product type abbreviations and their meanings
PRODUCT_ABBREVIATIONS = {
    # Forecast products
    "AFD": "Area Forecast Discussion",
    "ZFP": "Zone Forecast Product",
    "NOW": "Short Term Forecast",
    # Hazard products
    "HWO": "Hazardous Weather Outlook",
    "SPS": "Special Weather Statement",
    # Watch/warning products
    "SVS": "Severe Weather Statement",
    "SVR": "Severe Thunderstorm Warning",
    "TOR": "Tornado Warning",
    "FFW": "Flash Flood Warning",
    "WSW": "Winter Storm Warning",
    # SPC products
    "MCD": "Mesoscale Discussion",
    "WWA": "Watch/Warning/Advisory",
    "PTS": "Probabilistic Outlook Points",
}

# Common product types to display in the sidebar
DEFAULT_PRODUCT_TYPES = ["AFD", "HWO", "SPS", "NOW", "ZFP"]


class WFOProduct(BaseModel):
    """A text product from a WFO."""

    id: str  # Unique product ID from NWS API
    wfo: str  # WFO identifier (e.g., "OUN")
    product_type: str  # Product type code (e.g., "AFD")
    issued: datetime | None = None
    text: str | None = None  # May be None until loaded
    name: str | None = None  # Product name from API

    @property
    def title(self) -> str:
        """Human-readable title."""
        base = self.name or f"{self.product_type} from {self.wfo}"
        if self.issued:
            return f"{base} ({self.issued.strftime('%H:%M UTC')})"
        return base

    @property
    def short_title(self) -> str:
        """Short title for sidebar display."""
        if self.issued:
            return f"{self.product_type} {self.issued.strftime('%H:%M')}"
        return self.product_type

    @property
    def sidebar_id(self) -> str:
        """Unique ID for sidebar item."""
        return f"wfo-{self.wfo}-{self.id}"
