"""Tests for SPC HTML parsing functions."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from wxdxx.api.spc import SPCClient
from wxdxx.models.outlook import RiskLevel


class TestSPCParser:
    """Tests for SPC content parsing."""

    @pytest.fixture
    def client(self) -> SPCClient:
        """Create an SPC client for testing parsing methods."""
        return SPCClient()

    def test_extract_md_text(self, client: SPCClient, spc_md_html: str) -> None:
        """Test MD text extraction from HTML."""
        text = client._extract_md_text(spc_md_html)

        assert "Mesoscale Discussion 2847" in text
        assert "Areas affected...Central Oklahoma" in text
        assert "Concerning...Severe potential" in text
        # HTML tags should be stripped
        assert "<pre>" not in text
        assert "</pre>" not in text

    def test_extract_outlook_text(self, client: SPCClient, spc_outlook_html: str) -> None:
        """Test outlook text extraction from HTML."""
        text = client._extract_outlook_text(spc_outlook_html)

        assert "Day 1 Convective Outlook" in text
        assert "SLIGHT RISK" in text
        assert "Southern Plains" in text
        # HTML tags should be stripped
        assert "<pre>" not in text

    def test_parse_md_concerning(self, client: SPCClient, spc_md_html: str) -> None:
        """Test extraction of MD 'concerning' line."""
        text = client._extract_md_text(spc_md_html)
        concerning = client._parse_md_concerning(text)

        assert concerning == "Severe potential...Watch possible"

    def test_parse_max_risk_slight(self, client: SPCClient, spc_outlook_html: str) -> None:
        """Test parsing SLIGHT risk level from outlook."""
        text = client._extract_outlook_text(spc_outlook_html)
        risk = client._parse_max_risk(text)

        assert risk == RiskLevel.SLGT

    def test_parse_max_risk_levels(self, client: SPCClient) -> None:
        """Test all risk level parsing variations."""
        test_cases = [
            ("HIGH RISK OF SEVERE", RiskLevel.HIGH),
            ("...HIGH...", RiskLevel.HIGH),
            ("MODERATE RISK", RiskLevel.MDT),
            ("...MDT...", RiskLevel.MDT),
            ("ENHANCED RISK", RiskLevel.ENH),
            ("...ENH...", RiskLevel.ENH),
            ("SLIGHT RISK", RiskLevel.SLGT),
            ("...SLGT...", RiskLevel.SLGT),
            ("MARGINAL RISK", RiskLevel.MRGL),
            ("...MRGL...", RiskLevel.MRGL),
            ("THUNDERSTORM", RiskLevel.TSTM),
            ("...TSTM...", RiskLevel.TSTM),
            ("NO SEVERE WEATHER EXPECTED", None),
        ]

        for text, expected_risk in test_cases:
            result = client._parse_max_risk(text)
            assert result == expected_risk, f"Failed for: {text}"

    def test_parse_md_list(self, client: SPCClient, fixtures_dir: Path) -> None:
        """Test parsing MD numbers from listing page."""
        html = (fixtures_dir / "md_list_sample.html").read_text()
        md_numbers = client._parse_md_list(html)

        assert md_numbers == [2847, 2846, 2845]

    def test_parse_valid_line(self, client: SPCClient) -> None:
        """Test parsing VALID timestamp line."""
        text = "VALID 251630Z - 251830Z"
        ref_date = datetime(2024, 12, 25, 12, 0, tzinfo=timezone.utc)

        start, end = client._parse_valid_line(text, ref_date)

        assert start is not None
        assert end is not None
        assert start.day == 25
        assert start.hour == 16
        assert start.minute == 30
        assert end.day == 25
        assert end.hour == 18
        assert end.minute == 30

    def test_parse_local_timestamp(self, client: SPCClient) -> None:
        """Test parsing local timestamp from product header."""
        text = "1030 AM CST Wed Dec 25 2024"
        result = client._parse_local_timestamp(text)

        assert result is not None
        # CST is UTC-6, so 10:30 AM CST = 16:30 UTC
        assert result.hour == 16
        assert result.minute == 30
        assert result.day == 25
        assert result.month == 12
        assert result.year == 2024

    def test_parse_local_timestamp_pm(self, client: SPCClient) -> None:
        """Test parsing PM timestamp."""
        text = "505 PM CST Thu Dec 18 2025"
        result = client._parse_local_timestamp(text)

        assert result is not None
        # 5:05 PM CST = 23:05 UTC
        assert result.hour == 23
        assert result.minute == 5

    def test_parse_zulu_time(self, client: SPCClient) -> None:
        """Test parsing DDHHMMZ format."""
        ref_date = datetime(2024, 12, 25, 12, 0, tzinfo=timezone.utc)

        result = client._parse_zulu_time("261200", ref_date)

        assert result is not None
        assert result.day == 26
        assert result.hour == 12
        assert result.minute == 0
        assert result.tzinfo == timezone.utc

    def test_clean_html(self, client: SPCClient) -> None:
        """Test HTML cleaning function."""
        html = "<b>Bold</b> &amp; <i>italic</i> &lt;test&gt;"
        result = client._clean_html(html)

        assert result == "Bold & italic <test>"

    def test_parse_next_scheduled(self, client: SPCClient) -> None:
        """Test parsing next scheduled outlook time."""
        text = "NOTE: THE NEXT DAY 1 OUTLOOK IS SCHEDULED BY 2000Z"
        result = client._parse_next_scheduled(text)

        assert result is not None
        assert result.hour == 20
        assert result.minute == 0
        assert result.tzinfo == timezone.utc

    def test_parse_next_scheduled_day2(self, client: SPCClient) -> None:
        """Test parsing next scheduled outlook for Day 2."""
        text = "THE NEXT DAY 2 OUTLOOK IS SCHEDULED BY 0600Z"
        result = client._parse_next_scheduled(text)

        assert result is not None
        assert result.hour == 6
        assert result.minute == 0

    def test_parse_next_scheduled_not_found(self, client: SPCClient) -> None:
        """Test that missing next scheduled returns None."""
        text = "Some outlook text without next scheduled info"
        result = client._parse_next_scheduled(text)

        assert result is None

    def test_parse_next_scheduled_from_fixture(
        self, client: SPCClient, spc_outlook_html: str
    ) -> None:
        """Test parsing next scheduled from full outlook fixture."""
        text = client._extract_outlook_text(spc_outlook_html)
        result = client._parse_next_scheduled(text)

        assert result is not None
        assert result.hour == 20
        assert result.minute == 0
