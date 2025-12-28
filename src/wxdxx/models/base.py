"""Base model for all displayable weather products."""

from datetime import datetime

from pydantic import BaseModel


class BaseProduct(BaseModel):
    """Base class for all displayable weather products.

    All products have an issued time and a human-readable title.
    Subclasses must implement the `title` property.

    Attributes:
        issued: When the product was issued (UTC).
    """

    issued: datetime | None = None

    @property
    def title(self) -> str:
        """Human-readable title for the product.

        Subclasses must override this property.
        """
        raise NotImplementedError("Subclasses must implement title property")
