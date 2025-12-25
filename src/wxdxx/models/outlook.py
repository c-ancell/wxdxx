"""Models for SPC Convective Outlooks."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class OutlookDay(str, Enum):
    """Outlook day designation."""

    DAY1 = "day1"
    DAY2 = "day2"
    DAY3 = "day3"


class OutlookType(str, Enum):
    """Type of convective outlook."""

    CATEGORICAL = "categorical"
    TORNADO = "tornado"
    WIND = "wind"
    HAIL = "hail"


class RiskLevel(str, Enum):
    """Categorical risk levels."""

    TSTM = "TSTM"  # General thunderstorms
    MRGL = "MRGL"  # Marginal
    SLGT = "SLGT"  # Slight
    ENH = "ENH"  # Enhanced
    MDT = "MDT"  # Moderate
    HIGH = "HIGH"  # High


class ConvectiveOutlook(BaseModel):
    """A convective outlook product from SPC."""

    day: OutlookDay
    outlook_type: OutlookType
    issued: datetime | None = None
    valid_start: datetime | None = None
    valid_end: datetime | None = None
    next_scheduled: datetime | None = None
    text: str
    max_risk: RiskLevel | None = None

    @property
    def title(self) -> str:
        """Human-readable title for the outlook."""
        day_map = {
            OutlookDay.DAY1: "Day 1",
            OutlookDay.DAY2: "Day 2",
            OutlookDay.DAY3: "Day 3",
        }
        return f"{day_map[self.day]} Convective Outlook"
