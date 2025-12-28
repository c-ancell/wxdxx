"""Models for NWS weather observations (METAR data)."""

from datetime import datetime

from pydantic import BaseModel


class Observation(BaseModel):
    """A weather observation (METAR) from an NWS station."""

    station_id: str  # ICAO identifier (e.g., "KORD")
    station_name: str | None = None
    timestamp: datetime | None = None

    # Temperature (in Celsius, from API)
    temperature_c: float | None = None
    dewpoint_c: float | None = None

    # Wind
    wind_direction_deg: int | None = None  # Degrees (0-360)
    wind_speed_kt: float | None = None  # Knots
    wind_gust_kt: float | None = None  # Knots

    # Pressure and visibility
    barometric_pressure_hpa: float | None = None
    visibility_m: float | None = None  # Meters

    # Other
    relative_humidity_pct: float | None = None
    wind_chill_c: float | None = None
    heat_index_c: float | None = None

    # Raw METAR
    raw_metar: str | None = None
    text_description: str | None = None

    @property
    def temperature_f(self) -> float | None:
        """Temperature in Fahrenheit."""
        if self.temperature_c is None:
            return None
        return (self.temperature_c * 9 / 5) + 32

    @property
    def dewpoint_f(self) -> float | None:
        """Dewpoint in Fahrenheit."""
        if self.dewpoint_c is None:
            return None
        return (self.dewpoint_c * 9 / 5) + 32

    @property
    def visibility_mi(self) -> float | None:
        """Visibility in statute miles."""
        if self.visibility_m is None:
            return None
        return self.visibility_m / 1609.344

    @property
    def wind_summary(self) -> str:
        """Human-readable wind summary."""
        if self.wind_speed_kt is None:
            return "Calm"
        if self.wind_speed_kt < 1:
            return "Calm"

        direction = self._wind_direction_str()
        speed = int(self.wind_speed_kt)

        if self.wind_gust_kt and self.wind_gust_kt > self.wind_speed_kt:
            gust = int(self.wind_gust_kt)
            return f"{direction} {speed}G{gust} kt"
        return f"{direction} {speed} kt"

    def _wind_direction_str(self) -> str:
        """Convert wind direction degrees to cardinal direction."""
        if self.wind_direction_deg is None:
            return "VRB"
        directions = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
        ]
        idx = round(self.wind_direction_deg / 22.5) % 16
        return directions[idx]

    def format_compact(self) -> str:
        """Format for inline display (alert integration)."""
        parts = [self.station_id]

        if self.temperature_f is not None:
            parts.append(f"{self.temperature_f:.0f}F")

        parts.append(self.wind_summary)

        if self.visibility_mi is not None and self.visibility_mi < 10:
            parts.append(f"Vis {self.visibility_mi:.1f}mi")

        return " | ".join(parts)
