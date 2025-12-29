"""NWS API client for fetching WFO products."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .base import BaseAPIClient
from ..utils.datetime import parse_iso_datetime, parse_ugc_expiry

logger = logging.getLogger(__name__)
from ..models.alert import AlertSeverity, AlertUrgency, WFOAlert
from ..models.observation import Observation
from ..models.wfo import WFOProduct
from ..models.zone import ZoneGeometry

# Major US airports (Class B airspace) - prioritized in station listings
# These are busier airports with more reliable/frequent observations
MAJOR_AIRPORTS: set[str] = {
    # Top 30 busiest US airports by passenger traffic
    "KATL", "KLAX", "KORD", "KDFW", "KDEN",
    "KJFK", "KSFO", "KSEA", "KLAS", "KMCO",
    "KEWR", "KPHX", "KMIA", "KIAH", "KBOS",
    "KMSP", "KFLL", "KDTW", "KPHL", "KLGA",
    "KBWI", "KSLC", "KDCA", "KSAN", "KTPA",
    "KAUS", "KBNA", "KMDW", "KHOU", "KSTL",
    # Additional major metros
    "KCLT", "KRDU", "KPIT", "KCLE", "KCVG",
    "KIND", "KMCI", "KMKE", "KOAK", "KPDX",
    "KSMF", "KSJC", "KSNA", "KONT", "KSAT",
    "KELP", "KABQ", "KTUS", "KOKC", "KTUL",
    "KICT", "KOMA", "KDSM", "KMEM", "KLIT",
    "KJAN", "KMSY", "KBTR", "KJAX", "KPBI",
    "KRNO", "KCOS", "KBOI",
}


class NWSClient(BaseAPIClient):
    """Client for fetching products from the NWS API."""

    BASE_URL = "https://api.weather.gov"
    MAX_CONCURRENT_REQUESTS = 16  # NWS API is generous, increased for better parallelism
    RETRY_STATUS_CODES = {429}  # Retry on rate limit in addition to 5xx
    DEFAULT_HEADERS = {"Accept": "application/geo+json"}

    def __init__(self) -> None:
        super().__init__()
        # Cache zone ID -> WFO ID mappings (zones rarely change)
        self._zone_wfo_cache: dict[str, str] = {}
        # Cache zone ID -> geometry (zones rarely change, 24hr effective TTL)
        self._zone_geometry_cache: dict[str, ZoneGeometry] = {}

    async def validate_wfo(self, wfo_id: str) -> bool:
        """Check if a WFO ID is valid."""
        logger.debug("Validating WFO ID: %s", wfo_id)
        try:
            response = await self._get(f"/offices/{wfo_id.upper()}")
            valid = response.status_code == 200
            logger.debug("WFO %s validation: %s", wfo_id, valid)
            return valid
        except httpx.HTTPError as e:
            logger.warning("Failed to validate WFO %s: %s", wfo_id, e)
            return False

    async def get_wfo_info(self, wfo_id: str) -> dict | None:
        """Get detailed information about a WFO.

        Args:
            wfo_id: WFO ID (e.g., "OUN", "FWD")

        Returns:
            Dict with WFO details, or None if not found:
            - id: WFO ID
            - name: Full WFO name (e.g., "Norman, OK")
            - address: Street address
            - city: City
            - state: State
            - zipCode: ZIP code
            - telephone: Phone number
            - responsibleCounties: List of county URLs
            - responsibleForecastZones: List of zone URLs
            - responsibleFireZones: List of fire zone URLs
        """
        try:
            response = await self._get(f"/offices/{wfo_id.upper()}")
            if response.status_code != 200:
                return None
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPError:
            return None

    async def get_zone_wfo(self, zone_id: str) -> str:
        """Get the WFO ID responsible for a zone.

        Tries multiple zone types (forecast, county, fire) since alerts
        can reference different zone types.

        Args:
            zone_id: Zone ID (e.g., "NVZ019", "OKZ025", "OKC025")

        Returns:
            WFO ID (e.g., "VEF", "OUN") or empty string if not found.
        """
        # Check cache first
        if zone_id in self._zone_wfo_cache:
            return self._zone_wfo_cache[zone_id]

        # Try different zone type endpoints
        zone_types = ["forecast", "county", "fire"]
        for zone_type in zone_types:
            try:
                response = await self._get(f"/zones/{zone_type}/{zone_id}")
                if response.status_code != 200:
                    continue
                data = response.json()
                props = data.get("properties", {})
                cwa = props.get("cwa", [])
                if cwa and isinstance(cwa, list):
                    wfo: str = str(cwa[0]).upper()
                    self._zone_wfo_cache[zone_id] = wfo
                    return wfo
            except Exception:
                continue

        return ""

    def _extract_zone_ids(self, zone_urls: list[str]) -> list[str]:
        """Extract zone IDs from NWS zone URLs.

        Args:
            zone_urls: List of zone URLs (e.g., ["https://api.weather.gov/zones/forecast/OKZ025"])

        Returns:
            List of zone IDs (e.g., ["OKZ025"])
        """
        zone_ids = []
        for url in zone_urls:
            if "/" in url:
                zone_id = url.split("/")[-1]
                if zone_id:
                    zone_ids.append(zone_id)
        return zone_ids

    async def get_zone_geometry(self, zone_id: str) -> ZoneGeometry | None:
        """Get the geometry for a zone.

        Tries multiple zone type endpoints (forecast, county, fire) since
        alerts can reference different zone types.

        Args:
            zone_id: Zone ID (e.g., "OKZ025", "TXZ001", "INC001")

        Returns:
            ZoneGeometry with polygon coordinates, or None if not found.
        """
        # Check cache first
        if zone_id in self._zone_geometry_cache:
            return self._zone_geometry_cache[zone_id]

        # Try different zone type endpoints
        data = None
        zone_types = ["forecast", "county", "fire"]
        for zone_type in zone_types:
            try:
                response = await self._get(f"/zones/{zone_type}/{zone_id}")
                if response.status_code == 200:
                    data = response.json()
                    break
            except Exception:
                continue

        if data is None:
            return None

        try:

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

    async def get_wfo_zones_geometry(self, wfo_id: str) -> dict[str, ZoneGeometry]:
        """Get geometry for all forecast zones in a WFO's area.

        This method is optimized for performance:
        - Zone IDs are fetched once and cached
        - Zone geometries use the shared geometry cache
        - Subsequent calls for the same WFO are instant

        Args:
            wfo_id: WFO ID (e.g., "OUN", "FWD")

        Returns:
            Dict mapping zone_id to ZoneGeometry for all WFO zones.
        """
        # Get zone IDs for the WFO (uses office endpoint)
        zone_ids = await self.get_wfo_zones(wfo_id)
        if not zone_ids:
            return {}

        # Batch fetch all zone geometries (uses cache)
        return await self.get_zones_geometry(zone_ids)

    async def get_wfo_zones(self, wfo_id: str) -> list[str]:
        """Fetch responsible zones for a WFO (forecast + county).

        Includes both forecast zones and county zones since severe weather
        warnings are typically issued for county zones.

        Returns:
            List of zone IDs (e.g., ["OKZ025", "OKC025", ...])
        """
        response = await self._get(f"/offices/{wfo_id.upper()}")
        response.raise_for_status()
        data = response.json()

        # Extract zone IDs from URIs for both forecast and county zones
        # Format: "https://api.weather.gov/zones/forecast/OKZ025"
        #         "https://api.weather.gov/zones/county/OKC025"
        zones = []
        for zone_uri in data.get("responsibleForecastZones", []):
            zone_id = zone_uri.split("/")[-1]
            if zone_id:
                zones.append(zone_id)
        for zone_uri in data.get("responsibleCounties", []):
            zone_id = zone_uri.split("/")[-1]
            if zone_id:
                zones.append(zone_id)
        return zones

    async def get_products_by_type(
        self, wfo_id: str, product_type: str, limit: int = 5
    ) -> list[WFOProduct]:
        """Fetch products of a specific type from a WFO."""
        logger.debug("Fetching %s products for WFO %s (limit=%d)", product_type, wfo_id, limit)
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
                    issued=parse_iso_datetime(item.get("issuanceTime")),
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
                    product.expires = parse_ugc_expiry(full_product.text or "")
                except Exception as e:
                    logger.warning("Failed to fetch SPS text for %s: %s", product.id, e)

            await asyncio.gather(*[fetch_sps_text(p) for p in products])

        logger.debug("Fetched %d %s products for WFO %s", len(products), product_type, wfo_id)
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
            issued=parse_iso_datetime(data.get("issuanceTime")),
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
            "Snow Squall Warning",
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
        logger.debug("Fetching nationwide active alerts")
        response = await self._get("/alerts/active")
        response.raise_for_status()
        data = response.json()
        logger.debug("Received %d raw alerts from NWS API", len(data.get("features", [])))

        # First pass: collect candidate alerts with zone IDs and senderCode
        # (props, first_zone_id, all_zone_ids, sender_code)
        candidates: list[tuple[dict, str, list[str], str]] = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            alert_id = props.get("id", "")
            event = props.get("event", "")

            # Filter to ticker-worthy events only
            if event not in ticker_events:
                continue

            # Skip expired alerts early (before deduplication)
            expires = parse_iso_datetime(props.get("expires"))
            if expires and expires < now:
                continue

            # Deduplicate by alert ID
            if alert_id in seen_ids:
                continue
            seen_ids.add(alert_id)

            # Extract all zone IDs from affected zones
            affected_zone_urls = props.get("affectedZones", [])
            zone_ids = self._extract_zone_ids(affected_zone_urls)
            first_zone_id = zone_ids[0] if zone_ids else ""

            # Extract senderCode for reliable WFO attribution (like sidebar method)
            sender_code = props.get("senderCode", "").upper()
            sender_name = props.get("senderName", "")

            candidates.append((props, first_zone_id, zone_ids, sender_code, sender_name))

        # Batch lookup WFOs for ALL zones where senderCode is missing
        # This allows fallback to other zones if first zone lookup fails
        zones_needing_lookup: list[str] = []
        for _, _, zone_ids, sender_code, _ in candidates:
            if not sender_code:
                zones_needing_lookup.extend(zone_ids)
        unique_zones = list(set(zones_needing_lookup))
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

        for props, first_zone_id, zone_ids, sender_code, sender_name in candidates:
            # Use senderCode as primary WFO source (most reliable)
            wfo = sender_code
            # Fall back to zone lookup - try each zone until we find a WFO
            if not wfo:
                for zone_id in zone_ids:
                    wfo = zone_to_wfo.get(zone_id, "")
                    if wfo:
                        break
            event = props.get("event", "")

            # Only deduplicate by WFO+event if we have a valid WFO
            # (avoids incorrectly deduping alerts with failed WFO lookups)
            if wfo:
                wfo_key = f"{wfo}:{event}"
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
                    effective=parse_iso_datetime(props.get("effective")),
                    expires=parse_iso_datetime(props.get("expires")),
                    area_desc=props.get("areaDesc"),
                    affected_zones=zone_ids,
                    message_type=props.get("messageType", "Alert"),
                )
            )

            # Apply limit
            if len(all_alerts) >= limit:
                break

        logger.debug("Returning %d nationwide alerts after filtering", len(all_alerts))
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

        logger.debug("Fetching active alerts for %d zones", len(zones))
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
            logger.debug("Chunk %d: received %d alerts", i // 50 + 1, len(data.get("features", [])))

            for feature in data.get("features", []):
                props = feature.get("properties", {})
                alert_id = props.get("id", "")

                # Deduplicate alerts that appear in multiple zones
                if alert_id in seen_ids:
                    continue
                seen_ids.add(alert_id)

                # Extract WFO from senderCode (most reliable source)
                sender_code = props.get("senderCode", "")
                wfo = sender_code.upper() if sender_code else ""

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

                # Extract all zone IDs from affected zones
                affected_zone_urls = props.get("affectedZones", [])
                zone_ids = self._extract_zone_ids(affected_zone_urls)

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
                        effective=parse_iso_datetime(props.get("effective")),
                        expires=parse_iso_datetime(props.get("expires")),
                        area_desc=props.get("areaDesc"),
                        affected_zones=zone_ids,
                    )
                )

        logger.debug("Returning %d alerts for zone query", len(all_alerts))
        return all_alerts

    # ---------- Observation/METAR methods ----------

    async def validate_station(self, station_id: str) -> bool:
        """Check if a station ID is valid.

        Args:
            station_id: ICAO station identifier (e.g., "KORD")

        Returns:
            True if station exists, False otherwise.
        """
        try:
            response = await self._get(f"/stations/{station_id.upper()}")
            return response.status_code == 200
        except Exception:
            return False

    async def get_latest_observation(self, station_id: str) -> Observation | None:
        """Get the latest observation for a station.

        Args:
            station_id: ICAO station identifier (e.g., "KORD")

        Returns:
            Observation with current conditions, or None if unavailable.
        """
        try:
            response = await self._get(
                f"/stations/{station_id.upper()}/observations/latest"
            )
            if response.status_code != 200:
                return None
            data = response.json()

            props = data.get("properties", {})

            # Helper to extract quantitative values (NWS returns {"value": X, "unitCode": "..."})
            def get_value(field: str) -> float | None:
                val = props.get(field)
                if val is None or not isinstance(val, dict):
                    return None
                raw = val.get("value")
                return float(raw) if raw is not None else None

            def get_wind_kt(field: str) -> float | None:
                """Extract wind speed and convert to knots based on unitCode."""
                val = props.get(field)
                if val is None or not isinstance(val, dict):
                    return None
                raw = val.get("value")
                if raw is None:
                    return None
                value = float(raw)
                unit_code = val.get("unitCode", "")
                # NWS API can return wind in m/s or knots
                # unit:m_s-1 = meters per second, wmoUnit:km_h-1 = km/h
                if "m_s-1" in unit_code:
                    return value * 1.94384  # m/s to knots
                elif "km_h-1" in unit_code:
                    return value * 0.539957  # km/h to knots
                else:
                    # Assume already in knots (wmoUnit:kt) or unknown
                    return value

            wind_direction = get_value("windDirection")

            return Observation(
                station_id=station_id.upper(),
                station_name=props.get("textDescription"),
                timestamp=parse_iso_datetime(props.get("timestamp")),
                temperature_c=get_value("temperature"),
                dewpoint_c=get_value("dewpoint"),
                wind_direction_deg=(
                    int(wind_direction) if wind_direction is not None else None
                ),
                wind_speed_kt=get_wind_kt("windSpeed"),
                wind_gust_kt=get_wind_kt("windGust"),
                barometric_pressure_hpa=get_value("barometricPressure"),
                visibility_m=get_value("visibility"),
                relative_humidity_pct=get_value("relativeHumidity"),
                wind_chill_c=get_value("windChill"),
                heat_index_c=get_value("heatIndex"),
                raw_metar=props.get("rawMessage"),
                text_description=props.get("textDescription"),
            )
        except Exception:
            return None

    async def get_zone_stations(self, zone_id: str) -> list[str]:
        """Get station IDs for stations in a forecast zone.

        Args:
            zone_id: Zone ID (e.g., "OKZ025")

        Returns:
            List of station ICAO identifiers.
        """
        try:
            response = await self._get(f"/zones/forecast/{zone_id}/stations")
            if response.status_code != 200:
                return []
            data = response.json()

            stations = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                station_id = props.get("stationIdentifier")
                if station_id:
                    stations.append(station_id)

            return stations
        except Exception:
            return []

    async def get_observations_for_zones(
        self, zone_ids: list[str], limit: int = 10
    ) -> list[Observation]:
        """Get latest observations for stations in specified zones.

        Fetches stations for a subset of zones, deduplicates, then fetches
        observations for up to `limit` unique stations. Prioritizes major
        airports over regional stations for more reliable observations.

        Args:
            zone_ids: List of zone IDs
            limit: Maximum number of observations to return

        Returns:
            List of Observation objects (major airports first).
        """
        if not zone_ids:
            return []

        # Limit zones to query to avoid excessive API calls
        # (large watches can have 50+ zones, but we only need ~10 stations)
        max_zones = min(len(zone_ids), 15)
        zones_to_query = zone_ids[:max_zones]

        # Fetch stations for zones in parallel
        station_lists = await asyncio.gather(
            *[self.get_zone_stations(zone_id) for zone_id in zones_to_query]
        )

        # Deduplicate
        all_stations: set[str] = set()
        for station_list in station_lists:
            all_stations.update(station_list)

        # Sort by importance: major airports first, then alphabetically
        def station_priority(station_id: str) -> tuple[int, str]:
            # Priority 0 for major airports, 1 for others
            is_major = 0 if station_id in MAJOR_AIRPORTS else 1
            return (is_major, station_id)

        stations_to_fetch = sorted(all_stations, key=station_priority)[:limit]

        if not stations_to_fetch:
            return []

        # Fetch observations in parallel
        observations = await asyncio.gather(
            *[self.get_latest_observation(station_id) for station_id in stations_to_fetch]
        )

        # Filter out None results
        return [obs for obs in observations if obs is not None]
