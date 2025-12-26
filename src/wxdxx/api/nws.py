"""NWS API client for fetching WFO products."""

from datetime import datetime

import httpx

from ..models.alert import AlertSeverity, AlertUrgency, WFOAlert
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

    async def get_wfo_zones(self, wfo_id: str) -> list[str]:
        """Fetch responsible forecast zones for a WFO.

        Returns:
            List of zone IDs (e.g., ["OKZ025", "OKZ026", ...])
        """
        response = await self._client.get(f"/offices/{wfo_id.upper()}")
        response.raise_for_status()
        data = response.json()

        # Extract zone IDs from URIs
        # Format: "https://api.weather.gov/zones/forecast/OKZ025"
        zones = []
        for zone_uri in data.get("responsibleForecastZones", []):
            zone_id = zone_uri.split("/")[-1]
            if zone_id:
                zones.append(zone_id)
        return zones

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

    async def get_active_alerts(self, zones: list[str]) -> list[WFOAlert]:
        """Fetch active alerts for specified forecast zones.

        Args:
            zones: List of zone IDs to query (e.g., ["OKZ025", "OKZ026"])

        Returns:
            List of WFOAlert objects for active alerts in those zones.
        """
        if not zones:
            return []

        all_alerts: list[WFOAlert] = []
        seen_ids: set[str] = set()

        # NWS API accepts comma-separated zone list
        # Chunk into groups of 50 to avoid URL length limits
        for i in range(0, len(zones), 50):
            zone_chunk = zones[i : i + 50]
            zone_param = ",".join(zone_chunk)

            response = await self._client.get(
                "/alerts/active",
                params={"zone": zone_param, "message_type": "alert"},
            )
            response.raise_for_status()
            data = response.json()

            for feature in data.get("features", []):
                props = feature.get("properties", {})
                alert_id = props.get("id", "")

                # Deduplicate alerts that appear in multiple zones
                if alert_id in seen_ids:
                    continue
                seen_ids.add(alert_id)

                # Extract WFO from sender (format: "NWS Norman OK")
                sender = props.get("senderName", "")
                wfo = ""
                if "NWS " in sender:
                    # Try to extract WFO code from the response
                    # senderCode is more reliable if available
                    sender_code = props.get("senderCode", "")
                    if sender_code:
                        wfo = sender_code.upper()
                    else:
                        # Fallback: extract from sender name
                        parts = sender.replace("NWS ", "").split()
                        if parts:
                            wfo = parts[0][:3].upper()

                # Parse severity and urgency
                severity_str = props.get("severity", "Unknown")
                urgency_str = props.get("urgency", "Unknown")

                try:
                    severity = AlertSeverity(severity_str)
                except ValueError:
                    severity = AlertSeverity.UNKNOWN

                try:
                    urgency = AlertUrgency(urgency_str)
                except ValueError:
                    urgency = AlertUrgency.UNKNOWN

                all_alerts.append(
                    WFOAlert(
                        id=alert_id.split("/")[-1] if "/" in alert_id else alert_id,
                        wfo=wfo,
                        event=props.get("event", "Unknown"),
                        headline=props.get("headline"),
                        description=props.get("description"),
                        instruction=props.get("instruction"),
                        severity=severity,
                        urgency=urgency,
                        effective=self._parse_datetime(props.get("effective")),
                        expires=self._parse_datetime(props.get("expires")),
                        area_desc=props.get("areaDesc"),
                    )
                )

        return all_alerts

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None
