"""SPC API client for fetching weather products."""

import re
from datetime import datetime

import httpx

from ..models.md import MesoscaleDiscussion
from ..models.outlook import ConvectiveOutlook, OutlookDay, OutlookType, RiskLevel
from ..models.watch import Watch, WatchType


class SPCClient:
    """Client for fetching products from the Storm Prediction Center."""

    BASE_URL = "https://www.spc.noaa.gov"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "SPC-Dash/0.1.0"},
        )

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

        response = await self._client.get(url)
        response.raise_for_status()

        text = self._extract_outlook_text(response.text)
        max_risk = self._parse_max_risk(text)

        return ConvectiveOutlook(
            day=day,
            outlook_type=OutlookType.CATEGORICAL,
            text=text,
            max_risk=max_risk,
        )

    async def get_active_mds(self) -> list[MesoscaleDiscussion]:
        """Fetch list of active mesoscale discussions."""
        url = "/products/md/"
        response = await self._client.get(url)
        response.raise_for_status()

        md_numbers = self._parse_md_list(response.text)
        mds = []

        for num in md_numbers[:10]:  # Limit to most recent 10
            try:
                md = await self.get_md(num)
                mds.append(md)
            except httpx.HTTPError:
                continue

        return mds

    async def get_md(self, number: int) -> MesoscaleDiscussion:
        """Fetch a specific mesoscale discussion by number."""
        url = f"/products/md/md{number:04d}.html"
        response = await self._client.get(url)
        response.raise_for_status()

        text = self._extract_md_text(response.text)
        concerning = self._parse_md_concerning(text)

        return MesoscaleDiscussion(
            number=number,
            text=text,
            concerning=concerning,
        )

    async def get_active_watches(self) -> list[Watch]:
        """Fetch list of active watches."""
        url = "/products/watch/"
        response = await self._client.get(url)
        response.raise_for_status()

        watch_info = self._parse_watch_list(response.text)
        watches = []

        for num, wtype in watch_info[:10]:  # Limit to most recent 10
            try:
                watch = await self.get_watch(num, wtype)
                watches.append(watch)
            except httpx.HTTPError:
                continue

        return watches

    async def get_watch(self, number: int, watch_type: WatchType) -> Watch:
        """Fetch a specific watch by number."""
        prefix = "ww" if watch_type == WatchType.TORNADO else "ww"
        url = f"/products/watch/{prefix}{number:04d}.html"
        response = await self._client.get(url)
        response.raise_for_status()

        text = self._extract_watch_text(response.text)
        is_pds = "PARTICULARLY DANGEROUS SITUATION" in text.upper()

        return Watch(
            number=number,
            watch_type=watch_type,
            text=text,
            is_pds=is_pds,
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
        return sorted([int(m) for m in matches], reverse=True)

    def _parse_md_concerning(self, text: str) -> str | None:
        """Extract the 'concerning' line from MD text."""
        match = re.search(r"CONCERNING\.\.\.(.+?)(?:\n|$)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _parse_watch_list(self, html: str) -> list[tuple[int, WatchType]]:
        """Parse watch numbers and types from the watch listing page."""
        matches = re.findall(r"ww(\d{4})\.html", html, re.IGNORECASE)
        # Default to SEVERE_THUNDERSTORM, actual type determined when fetching
        return [(int(m), WatchType.SEVERE_THUNDERSTORM) for m in sorted(set(matches), reverse=True)]
