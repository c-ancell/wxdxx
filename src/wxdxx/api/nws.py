"""NWS API client for fetching WFO products."""

import asyncio
import re
from datetime import datetime, timezone

import httpx

from ..models.alert import AlertSeverity, AlertUrgency, WFOAlert
from ..models.wfo import WFOProduct
from ..models.zone import ZoneGeometry


class NWSClient:
    """Client for fetching products from the NWS API."""

    BASE_URL = "https://api.weather.gov"
    MAX_CONCURRENT_REQUESTS = 8  # NWS API is generous but we still limit
    MAX_RETRIES = 3  # Max retry attempts (total attempts = MAX_RETRIES + 1)
    RETRY_BACKOFF = (1.0, 2.0, 4.0)  # Exponential backoff delays in seconds

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={
                "User-Agent": "WxDXX/0.1.2 (https://github.com/c-ancell/wxdxx, wxdxxapp@gmail.com)",
                "Accept": "application/geo+json",
            },
        )
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        # Cache zone ID -> WFO ID mappings (zones rarely change)
        self._zone_wfo_cache: dict[str, str] = {}
        # Cache zone ID -> geometry (zones rarely change, 24hr effective TTL)
        self._zone_geometry_cache: dict[str, ZoneGeometry] = {}

    async def _get(self, url: str, **kwargs) -> httpx.Response:
        """Make a rate-limited GET request with retry on transient failures."""
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    response = await self._client.get(url, **kwargs)
                    # Retry on server errors (5xx) or rate limit (429)
                    if (response.status_code >= 500 or response.status_code == 429) and attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.RETRY_BACKOFF[attempt])
                        continue
                    return response
                except (httpx.TransportError, httpx.TimeoutException) as e:
                    last_error = e
                    if attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.RETRY_BACKOFF[attempt])
                    else:
                        raise
            # Should not reach here, but satisfy type checker
            if last_error:
                raise last_error
            raise RuntimeError("Unexpected retry loop exit")

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
            response = await self._get(f"/offices/{wfo_id.upper()}")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_zone_wfo(self, zone_id: str) -> str:
        """Get the WFO ID responsible for a forecast zone.

        Args:
            zone_id: Zone ID (e.g., "NVZ019", "OKZ025")

        Returns:
            WFO ID (e.g., "VEF", "OUN") or empty string if not found.
        """
        # Check cache first
        if zone_id in self._zone_wfo_cache:
            return self._zone_wfo_cache[zone_id]

        try:
            response = await self._get(f"/zones/forecast/{zone_id}")
            if response.status_code != 200:
                return ""
            data = response.json()
            props = data.get("properties", {})
            cwa = props.get("cwa", [])
            if cwa and isinstance(cwa, list):
                wfo = cwa[0].upper()
                self._zone_wfo_cache[zone_id] = wfo
                return wfo
        except Exception:
            pass

        return ""

    async def get_zone_geometry(self, zone_id: str) -> ZoneGeometry | None:
        """Get the geometry for a forecast zone.

        Args:
            zone_id: Zone ID (e.g., "OKZ025", "TXZ001")

        Returns:
            ZoneGeometry with polygon coordinates, or None if not found.
        """
        # Check cache first
        if zone_id in self._zone_geometry_cache:
            return self._zone_geometry_cache[zone_id]

        try:
            response = await self._get(f"/zones/forecast/{zone_id}")
            if response.status_code != 200:
                return None
            data = response.json()

            # Extract geometry
            geometry = data.get("geometry", {})
            geo_type = geometry.get("type", "")
            coords = geometry.get("coordinates", [])

            polygons: list[list[tuple[float, float]]] = []

            if geo_type == "Polygon":
                # Polygon coordinates: [[[lon, lat], ...]]
                # First ring is exterior, rest are holes (we just take exterior)
                if coords and len(coords) > 0:
                    exterior_ring = coords[0]
                    polygons.append([(c[0], c[1]) for c in exterior_ring])

            elif geo_type == "MultiPolygon":
                # MultiPolygon coordinates: [[[[lon, lat], ...]], ...]
                for polygon in coords:
                    if polygon and len(polygon) > 0:
                        exterior_ring = polygon[0]
                        polygons.append([(c[0], c[1]) for c in exterior_ring])

            if not polygons:
                return None

            # Extract properties
            props = data.get("properties", {})
            cwa_list = props.get("cwa", [])
            cwa = cwa_list[0].upper() if cwa_list else ""

            zone_geo = ZoneGeometry(
                zone_id=zone_id,
                name=props.get("name", ""),
                state=props.get("state", ""),
                cwa=cwa,
                polygons=polygons,
            )

            # Cache the result
            self._zone_geometry_cache[zone_id] = zone_geo
            # Also update the WFO cache while we have the data
            if cwa:
                self._zone_wfo_cache[zone_id] = cwa

            return zone_geo

        except Exception:
            return None

    async def get_zones_geometry(
        self, zone_ids: list[str]
    ) -> dict[str, ZoneGeometry]:
        """Get geometry for multiple forecast zones in parallel.

        Args:
            zone_ids: List of zone IDs (e.g., ["OKZ025", "TXZ001"])

        Returns:
            Dict mapping zone_id to ZoneGeometry (missing zones omitted).
        """
        if not zone_ids:
            return {}

        # Separate cached vs uncached
        results: dict[str, ZoneGeometry] = {}
        to_fetch: list[str] = []

        for zone_id in zone_ids:
            if zone_id in self._zone_geometry_cache:
                results[zone_id] = self._zone_geometry_cache[zone_id]
            else:
                to_fetch.append(zone_id)

        if not to_fetch:
            return results

        # Fetch uncached zones in parallel
        fetched = await asyncio.gather(
            *[self.get_zone_geometry(zone_id) for zone_id in to_fetch]
        )

        for zone_id, zone_geo in zip(to_fetch, fetched):
            if zone_geo is not None:
                results[zone_id] = zone_geo

        return results

    async def get_wfo_zones(self, wfo_id: str) -> list[str]:
        """Fetch responsible forecast zones for a WFO.

        Returns:
            List of zone IDs (e.g., ["OKZ025", "OKZ026", ...])
        """
        response = await self._get(f"/offices/{wfo_id.upper()}")
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
        response = await self._get(
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

        # For SPS products, fetch full text to parse UGC expiry
        # (NWS API doesn't populate expirationTime for text products)
        if product_type.upper() == "SPS" and products:
            async def fetch_sps_text(product: WFOProduct) -> None:
                try:
                    full_product = await self.get_product(product.id)
                    product.text = full_product.text
                    product.expires = self._parse_ugc_expiry(full_product.text or "")
                except Exception:
                    # If fetch fails, leave expires as None (product will show without countdown)
                    pass

            await asyncio.gather(*[fetch_sps_text(p) for p in products])

        return products

    async def get_product(self, product_id: str) -> WFOProduct:
        """Fetch a specific product by ID."""
        response = await self._get(f"/products/{product_id}")
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

    async def get_active_alerts_nationwide(
        self,
        limit: int = 100,
    ) -> list[WFOAlert]:
        """Fetch active alerts nationwide (no zone filter).

        This method fetches severe weather alerts from across the country
        for display in the news ticker.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of WFOAlert objects for active alerts nationwide.
        """
        # Filter to high-priority weather events for the ticker
        # Includes warnings and significant advisories
        ticker_events = {
            # Severe/Tornado
            "Tornado Warning",
            "Severe Thunderstorm Warning",
            # Flood
            "Flash Flood Warning",
            "Flood Warning",
            # Winter
            "Blizzard Warning",
            "Ice Storm Warning",
            "Winter Storm Warning",
            "Winter Weather Advisory",
            # Wind
            "High Wind Warning",
            # Heat
            "Excessive Heat Warning",
            # Tropical
            "Hurricane Warning",
            "Tropical Storm Warning",
        }

        seen_ids: set[str] = set()
        now = datetime.now(timezone.utc)

        # NWS API /alerts/active doesn't accept limit/status/message_type params
        # Fetch all and filter in Python
        response = await self._get("/alerts/active")
        response.raise_for_status()
        data = response.json()

        # First pass: collect candidate alerts and their zone IDs (no WFO lookups yet)
        candidates: list[tuple[dict, str]] = []  # (props, zone_id)
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            alert_id = props.get("id", "")
            event = props.get("event", "")

            # Filter to ticker-worthy events only
            if event not in ticker_events:
                continue

            # Skip expired alerts early (before deduplication)
            expires = self._parse_datetime(props.get("expires"))
            if expires and expires < now:
                continue

            # Deduplicate by alert ID
            if alert_id in seen_ids:
                continue
            seen_ids.add(alert_id)

            # Extract zone ID from the first affected zone
            affected_zones = props.get("affectedZones", [])
            zone_id = ""
            if affected_zones:
                # Zone URL format: https://api.weather.gov/zones/forecast/NVZ019
                first_zone_url = affected_zones[0]
                zone_id = first_zone_url.split("/")[-1] if "/" in first_zone_url else ""

            candidates.append((props, zone_id))

        # Batch lookup all WFOs in parallel
        unique_zones = list({zone_id for _, zone_id in candidates if zone_id})
        if unique_zones:
            wfo_results = await asyncio.gather(
                *[self.get_zone_wfo(zone_id) for zone_id in unique_zones]
            )
            zone_to_wfo = dict(zip(unique_zones, wfo_results))
        else:
            zone_to_wfo = {}

        # Second pass: build alerts with WFO info, dedupe by WFO+event
        all_alerts: list[WFOAlert] = []
        seen_wfo_events: set[str] = set()

        for props, zone_id in candidates:
            wfo = zone_to_wfo.get(zone_id, "") if zone_id else ""
            event = props.get("event", "")

            # Create WFO+event key for deduplication
            wfo_key = f"{wfo}:{event}"

            # Skip if we already have this WFO+event combo
            if wfo_key in seen_wfo_events:
                continue
            seen_wfo_events.add(wfo_key)

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

            alert_id = props.get("id", "")
            all_alerts.append(
                WFOAlert(
                    id=alert_id.split("/")[-1] if "/" in alert_id else alert_id,
                    wfo=wfo,
                    event=event,
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

            # Apply limit
            if len(all_alerts) >= limit:
                break

        return all_alerts

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

            # Don't filter by message_type - "update" messages are valid active alerts
            response = await self._get(
                "/alerts/active",
                params={"zone": zone_param},
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

    def _parse_ugc_expiry(self, text: str) -> datetime | None:
        """Extract expiry datetime from UGC header in product text.

        UGC (Universal Geographic Code) headers contain zone codes and an expiry
        time in DDHHMM format (day of month, hour, minute in UTC).

        Examples:
            CAZ103-104-106-261800-     -> Day 26, 18:00 UTC
            TXZ001-002-003-
            261800-                    -> Day 26, 18:00 UTC (multi-line)

        Args:
            text: Full product text containing UGC header

        Returns:
            Expiry datetime in UTC, or None if parsing fails
        """
        if not text:
            return None

        # UGC expiry is a 6-digit number followed by a dash at end of line
        # It appears in the first few lines of the product
        # Pattern: look for DDHHMM- where DD is day, HH is hour, MM is minute
        match = re.search(r"(\d{6})-\s*$", text[:500], re.MULTILINE)
        if not match:
            return None

        try:
            ddhhmm = match.group(1)
            day = int(ddhhmm[:2])
            hour = int(ddhhmm[2:4])
            minute = int(ddhhmm[4:6])

            # Build datetime using current year/month
            # Don't try to roll over months - if the expiry is in the past,
            # that's correct (the product is expired). The filtering logic
            # in app.py will handle removing expired products.
            now = datetime.now(timezone.utc)

            # Handle edge case: if we're on day 1-2 and expiry is day 30-31,
            # it's likely from the previous month (product issued end of last month)
            if now.day <= 2 and day >= 28:
                # Roll back to previous month
                if now.month == 1:
                    expiry = datetime(now.year - 1, 12, day, hour, minute, 0, tzinfo=timezone.utc)
                else:
                    # Need to handle months with different day counts
                    try:
                        expiry = datetime(now.year, now.month - 1, day, hour, minute, 0, tzinfo=timezone.utc)
                    except ValueError:
                        return None  # Day doesn't exist in previous month
            else:
                expiry = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)

            return expiry
        except (ValueError, IndexError):
            return None
