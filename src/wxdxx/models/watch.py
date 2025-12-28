"""Models for SPC Watches."""

from datetime import datetime
from enum import Enum

from .base import BaseProduct


class WatchType(str, Enum):
    """Type of severe weather watch."""

    TORNADO = "tornado"
    SEVERE_THUNDERSTORM = "severe_thunderstorm"


class Watch(BaseProduct):
    """A severe weather watch from SPC."""

    number: int
    watch_type: WatchType
    expires: datetime | None = None
    text: str
    affected_states: list[str] = []
    is_pds: bool = False  # Particularly Dangerous Situation

    @property
    def title(self) -> str:
        """Human-readable title for the watch."""
        type_str = "Tornado" if self.watch_type == WatchType.TORNADO else "Severe Thunderstorm"
        pds = " (PDS)" if self.is_pds else ""
        return f"{type_str} Watch #{self.number}{pds}"

    @property
    def short_title(self) -> str:
        """Short title for sidebar display."""
        prefix = "TOR" if self.watch_type == WatchType.TORNADO else "SVR"
        pds = " PDS" if self.is_pds else ""
        return f"{prefix} {self.number}{pds}"
