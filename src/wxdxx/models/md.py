"""Models for SPC Mesoscale Discussions."""

from datetime import datetime

from pydantic import BaseModel


class MesoscaleDiscussion(BaseModel):
    """A Mesoscale Discussion from SPC."""

    number: int
    issued: datetime | None = None
    expires: datetime | None = None
    text: str
    concerning: str | None = None  # Brief description of what the MD is about
    affected_areas: list[str] = []
    watch_probability: int | None = None  # Percentage chance of watch issuance

    @property
    def title(self) -> str:
        """Human-readable title for the MD."""
        return f"Mesoscale Discussion #{self.number}"

    @property
    def short_title(self) -> str:
        """Short title for sidebar display."""
        return f"MD {self.number}"
