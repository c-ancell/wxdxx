"""Models for NWS forecast zones."""

from pydantic import BaseModel


class ZoneGeometry(BaseModel):
    """Geometry data for a forecast zone."""

    zone_id: str  # Zone ID (e.g., "OKZ025", "TXZ001")
    name: str  # Zone name (e.g., "Oklahoma County")
    state: str  # State abbreviation (e.g., "OK")
    cwa: str  # County Warning Area / WFO ID (e.g., "OUN")
    polygons: list[list[tuple[float, float]]]  # List of polygon rings [(lon, lat), ...]

    @property
    def primary_polygon(self) -> list[tuple[float, float]]:
        """Return the first (usually main) polygon."""
        return self.polygons[0] if self.polygons else []
