"""Tests for news ticker headline interleaving and styling."""

from datetime import datetime, timedelta, timezone

import pytest

from wxdxx.app import WxDXX
from wxdxx.widgets.news_ticker import NewsTicker, TickerHeadline


def make_headline(id: str, event_type: str, source: str = "nws") -> TickerHeadline:
    """Helper to create a TickerHeadline for testing."""
    return TickerHeadline(
        id=id,
        text=f"Test {event_type} headline",
        event_type=event_type,
        source=source,
    )


class TestInterleaveHighPriorityHeadlines:
    """Tests for _interleave_high_priority_headlines method."""

    def setup_method(self) -> None:
        """Create app instance for testing."""
        self.app = WxDXX()

    def test_empty_list_returns_empty(self) -> None:
        """Empty input returns empty output."""
        result = self.app._interleave_high_priority_headlines([])
        assert result == []

    def test_no_high_priority_returns_unchanged(self) -> None:
        """List without TOR/SVR returns unchanged."""
        headlines = [
            make_headline("1", "FFW"),
            make_headline("2", "BZW"),
            make_headline("3", "WSW"),
        ]
        result = self.app._interleave_high_priority_headlines(headlines)
        assert result == headlines

    def test_short_list_returns_unchanged(self) -> None:
        """List shorter than interleave interval returns unchanged."""
        headlines = [
            make_headline("1", "TOR"),
            make_headline("2", "SVR"),
        ]
        result = self.app._interleave_high_priority_headlines(headlines)
        assert result == headlines

    def test_tor_headlines_interleaved(self) -> None:
        """TOR headlines are inserted periodically throughout the list."""
        headlines = [
            make_headline("tor1", "TOR"),
            make_headline("2", "FFW"),
            make_headline("3", "BZW"),
            make_headline("4", "WSW"),
            make_headline("5", "HWW"),
            make_headline("6", "WWY"),
        ]
        result = self.app._interleave_high_priority_headlines(headlines)

        # Original list had 6 items, with 1 TOR
        # Should insert at least one duplicate
        assert len(result) > len(headlines)

        # Count TOR occurrences
        tor_count = sum(1 for h in result if h.event_type == "TOR")
        assert tor_count >= 2  # Original + at least one duplicate

    def test_svr_headlines_interleaved(self) -> None:
        """SVR headlines are inserted periodically throughout the list."""
        headlines = [
            make_headline("svr1", "SVR"),
            make_headline("2", "FFW"),
            make_headline("3", "BZW"),
            make_headline("4", "WSW"),
            make_headline("5", "HWW"),
            make_headline("6", "WWY"),
        ]
        result = self.app._interleave_high_priority_headlines(headlines)

        # Count SVR occurrences
        svr_count = sum(1 for h in result if h.event_type == "SVR")
        assert svr_count >= 2  # Original + at least one duplicate

    def test_duplicates_have_unique_ids(self) -> None:
        """Duplicate headlines have unique IDs to allow proper tracking."""
        headlines = [
            make_headline("tor1", "TOR"),
            make_headline("2", "FFW"),
            make_headline("3", "BZW"),
            make_headline("4", "WSW"),
            make_headline("5", "HWW"),
            make_headline("6", "WWY"),
        ]
        result = self.app._interleave_high_priority_headlines(headlines)

        # All IDs should be unique
        ids = [h.id for h in result]
        assert len(ids) == len(set(ids))

    def test_tor_and_svr_both_interleaved(self) -> None:
        """Both TOR and SVR headlines are interleaved when present."""
        headlines = [
            make_headline("tor1", "TOR"),
            make_headline("svr1", "SVR"),
            make_headline("3", "FFW"),
            make_headline("4", "BZW"),
            make_headline("5", "WSW"),
            make_headline("6", "HWW"),
            make_headline("7", "WWY"),
            make_headline("8", "EHW"),
        ]
        result = self.app._interleave_high_priority_headlines(headlines)

        # Both TOR and SVR should appear more than once
        tor_count = sum(1 for h in result if h.event_type == "TOR")
        svr_count = sum(1 for h in result if h.event_type == "SVR")
        assert tor_count >= 2
        assert svr_count >= 2

    def test_spc_watches_also_interleaved(self) -> None:
        """SPC watches with TOR/SVR event types are also interleaved."""
        headlines = [
            make_headline("spc-tor", "TOR", source="spc"),
            make_headline("2", "FFW"),
            make_headline("3", "BZW"),
            make_headline("4", "WSW"),
            make_headline("5", "HWW"),
            make_headline("6", "WWY"),
        ]
        result = self.app._interleave_high_priority_headlines(headlines)

        # SPC TOR watch should also be duplicated
        tor_count = sum(1 for h in result if h.event_type == "TOR")
        assert tor_count >= 2


class TestExpiringHeadlineStyle:
    """Tests for expiring-soon headline styling."""

    def test_headline_not_expiring_soon(self) -> None:
        """Headlines with >5 minutes remaining are not marked as expiring."""
        ticker = NewsTicker()
        now = datetime.now(timezone.utc)
        headline = TickerHeadline(
            id="test",
            text="Test warning",
            event_type="TOR",
            source="nws",
            expires=now + timedelta(minutes=10),
        )
        assert not ticker._is_expiring_soon(headline)

    def test_headline_expiring_within_5_minutes(self) -> None:
        """Headlines within 5 minutes of expiry are marked as expiring."""
        ticker = NewsTicker()
        now = datetime.now(timezone.utc)
        headline = TickerHeadline(
            id="test",
            text="Test warning",
            event_type="TOR",
            source="nws",
            expires=now + timedelta(minutes=3),
        )
        assert ticker._is_expiring_soon(headline)

    def test_headline_expiring_at_threshold(self) -> None:
        """Headlines exactly at the 5-minute threshold are marked as expiring."""
        ticker = NewsTicker()
        now = datetime.now(timezone.utc)
        headline = TickerHeadline(
            id="test",
            text="Test warning",
            event_type="TOR",
            source="nws",
            expires=now + timedelta(minutes=5),
        )
        assert ticker._is_expiring_soon(headline)

    def test_headline_no_expiry_not_marked(self) -> None:
        """Headlines without expiry time are not marked as expiring."""
        ticker = NewsTicker()
        headline = TickerHeadline(
            id="test",
            text="Test warning",
            event_type="TOR",
            source="nws",
            expires=None,
        )
        assert not ticker._is_expiring_soon(headline)

    def test_expiring_headline_gets_dim_strike_style(self) -> None:
        """Expiring headlines get dim strikethrough style."""
        ticker = NewsTicker()
        now = datetime.now(timezone.utc)
        headline = TickerHeadline(
            id="test",
            text="Test warning",
            event_type="TOR",
            source="nws",
            expires=now + timedelta(minutes=2),
            appearance_count=5,  # Would normally get regular style
        )
        style = ticker._get_headline_style(headline)
        assert style == "dim strike"
