"""SPC API client for fetching weather products."""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from .base import BaseAPIClient
from ..utils.datetime import (
    US_TIMEZONE_OFFSETS,
    MONTH_NAMES,
    parse_local_timestamp,
    parse_valid_line,
    parse_zulu_time,
)

logger = logging.getLogger(__name__)

from ..models.md import MesoscaleDiscussion
from ..models.outlook import ConvectiveOutlook, OutlookDay, OutlookType, RiskLevel
from ..models.watch import Watch, WatchType


class SPCClient(BaseAPIClient):
    """Client for fetching products from the Storm Prediction Center."""

    BASE_URL = "https://www.spc.noaa.gov"
    MAX_CONCURRENT_REQUESTS = 3  # Limit concurrent requests to be a good citizen

    async def get_outlook(self, day: OutlookDay) -> ConvectiveOutlook:
        """Fetch a convective outlook for the specified day."""
        day_num = day.value.replace("day", "")
        url = f"/products/outlook/day{day_num}otlk.html"
        logger.debug("Fetching outlook for %s", day.value)

        response = await self._get(url)
        response.raise_for_status()

        text = self._extract_outlook_text(response.text)
        max_risk = self._parse_max_risk(text)

        # Extract timestamps
        issued = self._parse_outlook_issued(text)
        valid_start, valid_end = parse_valid_line(text)
        next_scheduled = self._parse_next_scheduled(text)

        logger.debug("Fetched %s outlook: risk=%s, issued=%s", day.value, max_risk, issued)
        return ConvectiveOutlook(
            day=day,
            outlook_type=OutlookType.CATEGORICAL,
            text=text,
            max_risk=max_risk,
            issued=issued,
            valid_start=valid_start,
            valid_end=valid_end,
            next_scheduled=next_scheduled,
        )

    async def get_active_mds(self) -> list[MesoscaleDiscussion]:
        """Fetch list of active mesoscale discussions."""
        url = "/products/md/"
        logger.debug("Fetching active MDs list")
        response = await self._get(url)
        response.raise_for_status()

        md_numbers = self._parse_md_list(response.text)[:10]  # Limit to most recent 10
        logger.debug("Found %d MDs to fetch: %s", len(md_numbers), md_numbers)

        if not md_numbers:
            return []

        async def fetch_md(num: int) -> MesoscaleDiscussion | None:
            try:
                return await self.get_md(num)
            except httpx.HTTPError as e:
                logger.warning("Failed to fetch MD %d: %s", num, e)
                return None

        results = await asyncio.gather(*[fetch_md(num) for num in md_numbers])
        valid_mds = [md for md in results if md is not None]
        logger.debug("Successfully fetched %d/%d MDs", len(valid_mds), len(md_numbers))
        return valid_mds

    async def get_md(self, number: int) -> MesoscaleDiscussion:
        """Fetch a specific mesoscale discussion by number."""
        url = f"/products/md/md{number:04d}.html"
        logger.debug("Fetching MD %d", number)
        response = await self._get(url)
        response.raise_for_status()

        text = self._extract_md_text(response.text)
        concerning = self._parse_md_concerning(text)
        watch_probability = self._parse_watch_probability(text)

        # Extract timestamps
        issued = parse_local_timestamp(text)
        _, expires = parse_valid_line(text)

        logger.debug("Fetched MD %d: concerning=%s, watch_prob=%s", number, concerning, watch_probability)
        return MesoscaleDiscussion(
            number=number,
            text=text,
            concerning=concerning,
            issued=issued,
            expires=expires,
            watch_probability=watch_probability,
        )

    async def get_active_watches(self) -> list[Watch]:
        """Fetch list of active watches."""
        url = "/products/watch/"
        logger.debug("Fetching active watches list")
        response = await self._get(url)
        response.raise_for_status()

        watch_info = self._parse_watch_list(response.text)[:10]  # Limit to most recent 10
        logger.debug("Found %d watches to fetch", len(watch_info))

        if not watch_info:
            return []

        async def fetch_watch(num: int, wtype: WatchType) -> Watch | None:
            try:
                return await self.get_watch(num, wtype)
            except httpx.HTTPError as e:
                logger.warning("Failed to fetch watch %d: %s", num, e)
                return None

        results = await asyncio.gather(
            *[fetch_watch(num, wtype) for num, wtype in watch_info]
        )
        valid_watches = [w for w in results if w is not None]
        logger.debug("Successfully fetched %d/%d watches", len(valid_watches), len(watch_info))
        return valid_watches

    async def get_watch(self, number: int, watch_type: WatchType) -> Watch:
        """Fetch a specific watch by number."""
        prefix = "ww" if watch_type == WatchType.TORNADO else "ww"
        url = f"/products/watch/{prefix}{number:04d}.html"
        logger.debug("Fetching watch %d", number)
        response = await self._get(url)
        response.raise_for_status()

        text = self._extract_watch_text(response.text)
        text_upper = text.upper()
        is_pds = "PARTICULARLY DANGEROUS SITUATION" in text_upper

        # Determine actual watch type from content
        # Look for "TORNADO WATCH" or "SEVERE THUNDERSTORM WATCH" in text
        if "TORNADO WATCH" in text_upper:
            actual_type = WatchType.TORNADO
        elif "SEVERE THUNDERSTORM WATCH" in text_upper:
            actual_type = WatchType.SEVERE_THUNDERSTORM
        else:
            # Fallback to passed-in type if detection fails
            actual_type = watch_type

        # Extract timestamps
        issued = parse_local_timestamp(text)
        expires = self._parse_watch_expires(text, issued)

        logger.debug("Fetched watch %d: type=%s, is_pds=%s", number, actual_type.value, is_pds)
        return Watch(
            number=number,
            watch_type=actual_type,
            text=text,
            is_pds=is_pds,
            issued=issued,
            expires=expires,
        )

    def _extract_outlook_text(self, html: str) -> str:
        """Extract outlook text from HTML page."""
        # Look for pre-formatted text block
        pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.DOTALL | re.IGNORECASE)
        if pre_match:
            return self._clean_html(pre_match.group(1))

        # Fallback: try to find the main content
        return self._clean_html(html)

    def _extract_md_text(self, html: str) -> str:
        """Extract MD text from HTML page."""
        pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.DOTALL | re.IGNORECASE)
        if pre_match:
            return self._clean_html(pre_match.group(1))
        return self._clean_html(html)

    def _extract_watch_text(self, html: str) -> str:
        """Extract watch text from HTML page."""
        pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.DOTALL | re.IGNORECASE)
        if pre_match:
            return self._clean_html(pre_match.group(1))
        return self._clean_html(html)

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean up text."""
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&nbsp;", " ")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&amp;", "&")
        return text.strip()

    def _parse_max_risk(self, text: str) -> RiskLevel | None:
        """Parse the maximum risk level from outlook text."""
        upper = text.upper()
        if "HIGH RISK" in upper or "...HIGH..." in upper:
            return RiskLevel.HIGH
        if "MODERATE RISK" in upper or "...MDT..." in upper:
            return RiskLevel.MDT
        if "ENHANCED RISK" in upper or "...ENH..." in upper:
            return RiskLevel.ENH
        if "SLIGHT RISK" in upper or "...SLGT..." in upper:
            return RiskLevel.SLGT
        if "MARGINAL RISK" in upper or "...MRGL..." in upper:
            return RiskLevel.MRGL
        if "THUNDERSTORM" in upper or "...TSTM..." in upper:
            return RiskLevel.TSTM
        return None

    def _parse_md_list(self, html: str) -> list[int]:
        """Parse MD numbers from the MD listing page."""
        matches = re.findall(r"md(\d{4})\.html", html, re.IGNORECASE)
        return sorted(set(int(m) for m in matches), reverse=True)

    def _parse_md_concerning(self, text: str) -> str | None:
        """Extract the 'concerning' line from MD text."""
        match = re.search(r"CONCERNING\.\.\.(.+?)(?:\n|$)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _parse_watch_probability(self, text: str) -> int | None:
        """Parse watch probability percentage from MD text.

        Handles patterns like:
        - "PROBABILITY OF WATCH ISSUANCE...40 PERCENT"
        - "WATCH PROBABILITY...80%"
        - "...PROBABILITY OF WATCH ISSUANCE IS 20 PERCENT..."

        Returns:
            Probability as integer (0-100), or None if not found
        """
        patterns = [
            r"PROBABILITY\s+OF\s+WATCH\s+ISSUANCE[.\s]*?(\d+)\s*(?:PERCENT|%)",
            r"WATCH\s+PROBABILITY[.\s]*?(\d+)\s*(?:PERCENT|%)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _parse_watch_list(self, html: str) -> list[tuple[int, WatchType]]:
        """Parse watch numbers and types from the watch listing page."""
        matches = re.findall(r"ww(\d{4})\.html", html, re.IGNORECASE)
        # Default to SEVERE_THUNDERSTORM, actual type determined when fetching
        return [(int(m), WatchType.SEVERE_THUNDERSTORM) for m in sorted(set(matches), reverse=True)]

    def _parse_outlook_issued(self, text: str) -> datetime | None:
        """Parse issued timestamp from outlook text.

        Handles format like "1630 UTC DAY MON DD YYYY" at top of outlook.
        """
        # First try the standard local timestamp pattern
        result = parse_local_timestamp(text)
        if result:
            return result

        # Try simpler UTC-only pattern: HHMM UTC DAY MON DD YYYY
        pattern = r"(\d{4})\s+UTC\s+\w{3}\s+(\w{3})\s+(\d{1,2})\s+(\d{4})"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None

        time_str, month_str, day_str, year_str = match.groups()

        try:
            hour = int(time_str[:2])
            minute = int(time_str[2:])
        except ValueError:
            return None

        month = MONTH_NAMES.get(month_str.upper())
        if month is None:
            return None

        try:
            day = int(day_str)
            year = int(year_str)
            return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        except ValueError:
            return None

    def _parse_next_scheduled(self, text: str) -> datetime | None:
        """Parse the next scheduled outlook time from outlook text.

        Handles patterns like:
        - "NOTE: THE NEXT DAY 1 OUTLOOK IS SCHEDULED BY 0100Z"
        - "THE NEXT DAY 2 OUTLOOK IS SCHEDULED BY 0600Z"

        Returns:
            UTC datetime for next scheduled outlook, or None if not found
        """
        pattern = r"THE\s+NEXT\s+DAY\s+\d\s+OUTLOOK\s+IS\s+SCHEDULED\s+BY\s+(\d{4})Z"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None

        time_str = match.group(1)
        try:
            hour = int(time_str[:2])
            minute = int(time_str[2:])
        except ValueError:
            return None

        # Determine the date for this scheduled time
        now = datetime.now(timezone.utc)
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If the scheduled time is in the past, it's for tomorrow
        if scheduled <= now:
            scheduled += timedelta(days=1)

        return scheduled

    def _parse_watch_expires(
        self, text: str, issued: datetime | None
    ) -> datetime | None:
        """Parse watch expiration time.

        Watches have patterns like:
        - "EFFECTIVE THIS THURSDAY NIGHT FROM 505 PM UNTIL 1100 PM CST"
        - "VALID 261200Z - 270300Z" (Zulu format)

        Args:
            text: Watch text content
            issued: Issued datetime for reference

        Returns:
            UTC datetime or None if parsing fails
        """
        # First try VALID line (Zulu format)
        _, expires = parse_valid_line(text, issued)
        if expires:
            return expires

        # Try "UNTIL HH:MM AM/PM TZ" pattern
        pattern = r"UNTIL\s+(\d{3,4})\s*(AM|PM)\s+(UTC|EST|EDT|CST|CDT|MST|MDT|PST|PDT|AKST|AKDT|HST)"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None

        time_str, ampm, tz_str = match.groups()
        tz_str = tz_str.upper()
        ampm = ampm.upper()

        # Parse time
        time_str = time_str.zfill(4)
        try:
            hour = int(time_str[:-2])
            minute = int(time_str[-2:])
        except ValueError:
            return None

        # Convert 12-hour to 24-hour
        if ampm == "PM" and hour != 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0

        # Get timezone offset
        tz_offset = US_TIMEZONE_OFFSETS.get(tz_str, 0)

        # Use issued date as reference, or current date
        if issued:
            ref_date = issued
        else:
            ref_date = datetime.now(timezone.utc)

        try:
            local_tz = timezone(timedelta(hours=tz_offset))
            # Start with same day as issued
            expires_dt = datetime(
                ref_date.year, ref_date.month, ref_date.day,
                hour, minute, tzinfo=local_tz
            )
            expires_utc = expires_dt.astimezone(timezone.utc)

            # If expires is before issued, it's the next day
            if issued and expires_utc < issued:
                expires_utc += timedelta(days=1)

            return expires_utc
        except ValueError:
            return None
