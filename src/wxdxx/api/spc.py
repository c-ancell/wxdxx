"""SPC API client for fetching weather products."""

import asyncio
import re
from datetime import datetime, timedelta, timezone

import httpx

# US timezone offsets (hours from UTC)
# Standard time offsets
US_TIMEZONE_OFFSETS: dict[str, int] = {
    "EST": -5,
    "CST": -6,
    "MST": -7,
    "PST": -8,
    "AKST": -9,
    "HST": -10,
    # Daylight saving time offsets
    "EDT": -4,
    "CDT": -5,
    "MDT": -6,
    "PDT": -7,
    "AKDT": -8,
    # UTC
    "UTC": 0,
    "Z": 0,
}

from ..models.md import MesoscaleDiscussion
from ..models.outlook import ConvectiveOutlook, OutlookDay, OutlookType, RiskLevel
from ..models.watch import Watch, WatchType


class SPCClient:
    """Client for fetching products from the Storm Prediction Center."""

    BASE_URL = "https://www.spc.noaa.gov"
    MAX_CONCURRENT_REQUESTS = 3  # Limit concurrent requests to be a good citizen
    MAX_RETRIES = 3  # Max retry attempts (total attempts = MAX_RETRIES + 1)
    RETRY_BACKOFF = (1.0, 2.0, 4.0)  # Exponential backoff delays in seconds

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={
                "User-Agent": "WxDXX/0.1.2 (https://github.com/c-ancell/wxdxx, wxdxxapp@gmail.com)"
            },
        )
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

    async def _get(self, url: str) -> httpx.Response:
        """Make a rate-limited GET request with retry on transient failures."""
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    response = await self._client.get(url)
                    # Retry on server errors (5xx)
                    if response.status_code >= 500 and attempt < self.MAX_RETRIES:
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

    async def __aenter__(self) -> "SPCClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def get_outlook(self, day: OutlookDay) -> ConvectiveOutlook:
        """Fetch a convective outlook for the specified day."""
        day_num = day.value.replace("day", "")
        url = f"/products/outlook/day{day_num}otlk.html"

        response = await self._get(url)
        response.raise_for_status()

        text = self._extract_outlook_text(response.text)
        max_risk = self._parse_max_risk(text)

        # Extract timestamps
        issued = self._parse_outlook_issued(text)
        valid_start, valid_end = self._parse_valid_line(text)
        next_scheduled = self._parse_next_scheduled(text)

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
        response = await self._get(url)
        response.raise_for_status()

        md_numbers = self._parse_md_list(response.text)[:10]  # Limit to most recent 10

        if not md_numbers:
            return []

        async def fetch_md(num: int) -> MesoscaleDiscussion | None:
            try:
                return await self.get_md(num)
            except httpx.HTTPError:
                return None

        results = await asyncio.gather(*[fetch_md(num) for num in md_numbers])
        return [md for md in results if md is not None]

    async def get_md(self, number: int) -> MesoscaleDiscussion:
        """Fetch a specific mesoscale discussion by number."""
        url = f"/products/md/md{number:04d}.html"
        response = await self._get(url)
        response.raise_for_status()

        text = self._extract_md_text(response.text)
        concerning = self._parse_md_concerning(text)
        watch_probability = self._parse_watch_probability(text)

        # Extract timestamps
        issued = self._parse_local_timestamp(text)
        _, expires = self._parse_valid_line(text)

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
        response = await self._get(url)
        response.raise_for_status()

        watch_info = self._parse_watch_list(response.text)[:10]  # Limit to most recent 10

        if not watch_info:
            return []

        async def fetch_watch(num: int, wtype: WatchType) -> Watch | None:
            try:
                return await self.get_watch(num, wtype)
            except httpx.HTTPError:
                return None

        results = await asyncio.gather(
            *[fetch_watch(num, wtype) for num, wtype in watch_info]
        )
        return [w for w in results if w is not None]

    async def get_watch(self, number: int, watch_type: WatchType) -> Watch:
        """Fetch a specific watch by number."""
        prefix = "ww" if watch_type == WatchType.TORNADO else "ww"
        url = f"/products/watch/{prefix}{number:04d}.html"
        response = await self._get(url)
        response.raise_for_status()

        text = self._extract_watch_text(response.text)
        is_pds = "PARTICULARLY DANGEROUS SITUATION" in text.upper()

        # Extract timestamps
        issued = self._parse_local_timestamp(text)
        expires = self._parse_watch_expires(text, issued)

        return Watch(
            number=number,
            watch_type=watch_type,
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

    def _parse_valid_line(
        self, text: str, reference_date: datetime | None = None
    ) -> tuple[datetime | None, datetime | None]:
        """Parse VALID DDHHMMZ - DDHHMMZ line to extract start and end times.

        Args:
            text: Product text containing VALID line
            reference_date: Reference date for determining year/month (defaults to now)

        Returns:
            Tuple of (valid_start, valid_end) as UTC datetimes, or (None, None) if not found
        """
        match = re.search(r"VALID\s+(\d{6})Z\s*-\s*(\d{6})Z", text, re.IGNORECASE)
        if not match:
            return None, None

        if reference_date is None:
            reference_date = datetime.now(timezone.utc)

        start_str, end_str = match.group(1), match.group(2)
        start_dt = self._parse_zulu_time(start_str, reference_date)
        end_dt = self._parse_zulu_time(end_str, reference_date)

        # Handle case where end day is before start day (crosses month boundary)
        if start_dt and end_dt and end_dt < start_dt:
            # End is in the next month
            if end_dt.month == 12:
                end_dt = end_dt.replace(year=end_dt.year + 1, month=1)
            else:
                end_dt = end_dt.replace(month=end_dt.month + 1)

        return start_dt, end_dt

    def _parse_zulu_time(
        self, zulu_str: str, reference_date: datetime
    ) -> datetime | None:
        """Parse DDHHMMZ format to datetime.

        Args:
            zulu_str: String in DDHHMMZ format (e.g., "261200" for day 26, 12:00Z)
            reference_date: Reference date for year/month context

        Returns:
            UTC datetime or None if parsing fails
        """
        if len(zulu_str) != 6:
            return None

        try:
            day = int(zulu_str[0:2])
            hour = int(zulu_str[2:4])
            minute = int(zulu_str[4:6])
        except ValueError:
            return None

        # Use reference date's year and month
        year = reference_date.year
        month = reference_date.month

        # Handle day rollover (e.g., reference is Dec 31, product valid Jan 1)
        ref_day = reference_date.day
        if day < ref_day - 15:
            # Day is likely next month
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
        elif day > ref_day + 15:
            # Day is likely previous month
            if month == 1:
                month = 12
                year -= 1
            else:
                month -= 1

        try:
            return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        except ValueError:
            return None

    def _parse_local_timestamp(self, text: str) -> datetime | None:
        """Parse local timestamp from SPC product header.

        Handles formats like:
        - "0412 AM CST THU DEC 25 2025"
        - "505 PM CST THU DEC 18 2025"
        - "1630 UTC THU DEC 25 2025"

        Returns:
            UTC datetime or None if parsing fails
        """
        # Pattern: HHMM AM/PM TZ DAY MON DD YYYY (with optional AM/PM for UTC)
        pattern = r"(\d{3,4})\s*(AM|PM)?\s*(UTC|EST|EDT|CST|CDT|MST|MDT|PST|PDT|AKST|AKDT|HST)\s+\w{3}\s+(\w{3})\s+(\d{1,2})\s+(\d{4})"
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None

        time_str, ampm, tz_str, month_str, day_str, year_str = match.groups()
        tz_str = tz_str.upper()

        # Parse time
        time_str = time_str.zfill(4)  # Pad to 4 digits (e.g., "505" -> "0505")
        try:
            hour = int(time_str[:-2])
            minute = int(time_str[-2:])
        except ValueError:
            return None

        # Convert 12-hour to 24-hour if AM/PM present
        if ampm:
            ampm = ampm.upper()
            if ampm == "PM" and hour != 12:
                hour += 12
            elif ampm == "AM" and hour == 12:
                hour = 0

        # Parse month
        months = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        month = months.get(month_str.upper())
        if month is None:
            return None

        try:
            day = int(day_str)
            year = int(year_str)
        except ValueError:
            return None

        # Get timezone offset
        tz_offset = US_TIMEZONE_OFFSETS.get(tz_str, 0)

        try:
            local_tz = timezone(timedelta(hours=tz_offset))
            local_dt = datetime(year, month, day, hour, minute, tzinfo=local_tz)
            return local_dt.astimezone(timezone.utc)
        except ValueError:
            return None

    def _parse_outlook_issued(self, text: str) -> datetime | None:
        """Parse issued timestamp from outlook text.

        Handles format like "1630 UTC DAY MON DD YYYY" at top of outlook.
        """
        # First try the standard local timestamp pattern
        result = self._parse_local_timestamp(text)
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

        months = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        month = months.get(month_str.upper())
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
        _, expires = self._parse_valid_line(text, issued)
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
