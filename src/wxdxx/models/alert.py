"""Models for NWS hazard alerts."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AlertSeverity(str, Enum):
    """NWS alert severity levels."""

    EXTREME = "Extreme"
    SEVERE = "Severe"
    MODERATE = "Moderate"
    MINOR = "Minor"
    UNKNOWN = "Unknown"


class AlertUrgency(str, Enum):
    """NWS alert urgency levels."""

    IMMEDIATE = "Immediate"
    EXPECTED = "Expected"
    FUTURE = "Future"
    PAST = "Past"
    UNKNOWN = "Unknown"


class WFOAlert(BaseModel):
    """An active weather alert from NWS."""

    id: str  # Alert ID from NWS API
    wfo: str  # Originating WFO
    event: str  # Event type (e.g., "Tornado Warning", "Flood Watch")
    headline: str | None = None
    description: str | None = None
    instruction: str | None = None
    severity: AlertSeverity = AlertSeverity.UNKNOWN
    urgency: AlertUrgency = AlertUrgency.UNKNOWN
    effective: datetime | None = None
    expires: datetime | None = None
    area_desc: str | None = None  # Human-readable affected area
    affected_zones: list[str] = []  # Zone IDs (e.g., ["OKZ025", "OKZ026"])
    message_type: str = "Alert"  # "Alert", "Update", or "Cancel"

    @property
    def title(self) -> str:
        """Human-readable title."""
        return self.headline or self.event

    @property
    def short_event(self) -> str:
        """Abbreviated event type for sidebar display."""
        abbrev_map = {
            "Tornado Warning": "TOR",
            "Tornado Watch": "TOA",
            "Severe Thunderstorm Warning": "SVR",
            "Severe Thunderstorm Watch": "SVA",
            "Flash Flood Warning": "FFW",
            "Flash Flood Watch": "FFA",
            "Flood Warning": "FLW",
            "Flood Watch": "FLA",
            "Flood Advisory": "FLY",
            "Winter Storm Warning": "WSW",
            "Winter Storm Watch": "WSA",
            "Winter Weather Advisory": "WWY",
            "Wind Advisory": "WND",
            "High Wind Warning": "HWW",
            "Heat Advisory": "HT",
            "Excessive Heat Warning": "EHW",
            "Dense Fog Advisory": "FOG",
            "Special Weather Statement": "SPS",
            "Freeze Warning": "FRW",
            "Frost Advisory": "FRA",
            "Red Flag Warning": "RFW",
            "Fire Weather Watch": "FWA",
        }
        return abbrev_map.get(self.event, self.event[:6].upper())

    @property
    def text(self) -> str:
        """Full text content for display."""
        parts = []
        if self.headline:
            parts.append(self.headline)
            parts.append("")
        if self.area_desc:
            parts.append(f"AREAS AFFECTED: {self.area_desc}")
            parts.append("")
        if self.description:
            parts.append(self.description)
        if self.instruction:
            parts.append("")
            parts.append("PRECAUTIONARY/PREPAREDNESS ACTIONS...")
            parts.append(self.instruction)
        return "\n".join(parts)

    @property
    def sidebar_id(self) -> str:
        """Unique ID for sidebar item."""
        return f"alert-{self.wfo}-{self.id}"
