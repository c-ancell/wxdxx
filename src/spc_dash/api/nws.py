"""NWS API client for fetching WFO products."""

from datetime import datetime

import httpx

from ..models.wfo import WFOProduct


class NWSClient:
    """Client for fetching products from the NWS API."""

    BASE_URL = "https://api.weather.gov"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={
                "User-Agent": "SPC-Dash/0.1.0",
                "Accept": "application/geo+json",
            },
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "NWSClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def validate_wfo(self, wfo_id: str) -> bool:
        """Check if a WFO ID is valid."""
        try:
            response = await self._client.get(f"/offices/{wfo_id.upper()}")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_products_by_type(
        self, wfo_id: str, product_type: str, limit: int = 5
    ) -> list[WFOProduct]:
        """Fetch products of a specific type from a WFO."""
        response = await self._client.get(
            "/products",
            params={
                "type": product_type.upper(),
                "location": wfo_id.upper(),
                "limit": limit,
            },
        )
        response.raise_for_status()
        data = response.json()

        products = []
        for item in data.get("@graph", []):
            product_id = item.get("id", "").split("/")[-1]
            if not product_id:
                continue

            products.append(
                WFOProduct(
                    id=product_id,
                    wfo=wfo_id.upper(),
                    product_type=product_type.upper(),
                    issued=self._parse_datetime(item.get("issuanceTime")),
                    text=None,  # Lazy-loaded
                    name=item.get("productName"),
                )
            )
        return products

    async def get_product(self, product_id: str) -> WFOProduct:
        """Fetch a specific product by ID."""
        response = await self._client.get(f"/products/{product_id}")
        response.raise_for_status()
        data = response.json()

        return WFOProduct(
            id=product_id,
            wfo=data.get("issuingOffice", "").split("/")[-1],
            product_type=data.get("productCode", ""),
            issued=self._parse_datetime(data.get("issuanceTime")),
            text=data.get("productText", ""),
            name=data.get("productName"),
        )

    async def get_active_alerts(self, wfo_id: str) -> list[WFOProduct]:
        """Fetch active alerts for a WFO."""
        response = await self._client.get(
            "/alerts/active",
            params={"message_type": "alert"},
        )
        response.raise_for_status()
        data = response.json()

        alerts = []
        wfo_upper = wfo_id.upper()
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            sender = props.get("senderName", "")
            # Check if this alert is from the specified WFO
            if wfo_upper not in sender.upper():
                continue

            alert_id = props.get("id", "").split("/")[-1]
            description = props.get("description", "")
            instruction = props.get("instruction", "")
            text = description
            if instruction:
                text += "\n\n" + instruction

            alerts.append(
                WFOProduct(
                    id=alert_id,
                    wfo=wfo_upper,
                    product_type=props.get("event", "ALERT"),
                    issued=self._parse_datetime(props.get("effective")),
                    text=text,
                    name=props.get("headline"),
                )
            )
        return alerts

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None
