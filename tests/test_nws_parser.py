"""Tests for NWS API client parsing functions."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from wxdxx.utils.datetime import parse_ugc_expiry


class TestUGCExpiryParsing:
    """Tests for parse_ugc_expiry() function."""

    def test_parse_single_line_ugc(self):
        """Test parsing standard single-line UGC header."""
        text = """CAZ103-104-106-261800-
/O.NEW.KLOX.FA.Y.0001.250126T1200Z-250126T1800Z/

AREA FORECAST DISCUSSION
"""
        # Mock current time to Dec 26, 2025
        with patch("wxdxx.utils.datetime.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 26, 12, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = parse_ugc_expiry(text)

        assert result is not None
        assert result.day == 26
        assert result.hour == 18
        assert result.minute == 0
        assert result.tzinfo == timezone.utc

    def test_parse_multi_zone_ugc(self):
        """Test parsing UGC with multiple zone codes."""
        text = """TXZ001-002-003-004-005-006-261500-

SPECIAL WEATHER STATEMENT
"""
        with patch("wxdxx.utils.datetime.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 26, 10, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = parse_ugc_expiry(text)

        assert result is not None
        assert result.day == 26
        assert result.hour == 15
        assert result.minute == 0

    def test_parse_multi_line_ugc(self):
        """Test parsing UGC that spans multiple lines."""
        text = """OKZ001-002-003-004-005-006-007-008-009-010-011-012-
261200-

SPECIAL WEATHER STATEMENT
"""
        with patch("wxdxx.utils.datetime.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 26, 8, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = parse_ugc_expiry(text)

        assert result is not None
        assert result.day == 26
        assert result.hour == 12
        assert result.minute == 0

    def test_parse_expired_product_same_month(self):
        """Test parsing expired product from earlier in the month."""
        text = """CAZ103-231800-

SPECIAL WEATHER STATEMENT
"""
        # Current date is Dec 26, expiry was Dec 23 at 18:00 (already expired)
        with patch("wxdxx.utils.datetime.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 26, 20, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = parse_ugc_expiry(text)

        # Should return Dec 23 (expired), NOT Jan 23
        assert result is not None
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 23
        assert result.hour == 18
        assert result.minute == 0

    def test_parse_previous_month_rollback(self):
        """Test parsing when we're early in month and expiry is from end of last month."""
        text = """NYZ001-311800-

SPECIAL WEATHER STATEMENT
"""
        # Current date is Jan 2, expiry day 31 = Dec 31 of previous month
        with patch("wxdxx.utils.datetime.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = parse_ugc_expiry(text)

        assert result is not None
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 31

    def test_parse_empty_text(self):
        """Test parsing empty text returns None."""
        assert parse_ugc_expiry("") is None

    def test_parse_no_ugc_header(self):
        """Test parsing text without UGC header returns None."""
        text = """AREA FORECAST DISCUSSION
NATIONAL WEATHER SERVICE NORMAN OK
1200 PM CST THU DEC 26 2025

.SHORT TERM...
"""
        result = parse_ugc_expiry(text)
        assert result is None

    def test_parse_malformed_ugc(self):
        """Test parsing malformed UGC returns None."""
        # Missing trailing dash
        text = """CAZ103-261800

SPECIAL WEATHER STATEMENT
"""
        result = parse_ugc_expiry(text)
        assert result is None

    def test_parse_invalid_time(self):
        """Test parsing invalid time values returns None."""
        # Invalid hour (25)
        text = """CAZ103-262500-

SPECIAL WEATHER STATEMENT
"""
        with patch("wxdxx.utils.datetime.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 26, 12, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = parse_ugc_expiry(text)

        # Should return None due to ValueError when creating datetime
        assert result is None

    def test_parse_real_sps_format(self):
        """Test parsing a realistic SPS product format."""
        text = """WWUS85 KEWX 261445
SPSEWX

SPECIAL WEATHER STATEMENT
NATIONAL WEATHER SERVICE AUSTIN/SAN ANTONIO TX
845 AM CST THU DEC 26 2024

TXZ187-188-189-261600-
/O.NEW.KEWX.SQ.W.0001.241226T1445Z-241226T1600Z/

...STRONG WINDS EXPECTED THROUGH MID-MORNING...

A strong cold front is moving through South Central Texas.
"""
        with patch("wxdxx.utils.datetime.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 12, 26, 14, 50, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = parse_ugc_expiry(text)

        assert result is not None
        assert result.day == 26
        assert result.hour == 16
        assert result.minute == 0
