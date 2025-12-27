"""Smoke tests for the WxDXX application."""

import pytest
from textual.pilot import Pilot

from wxdxx.app import WxDXX


class TestAppSmoke:
    """Basic smoke tests to verify the app starts and renders."""

    @pytest.mark.asyncio
    async def test_app_starts(self) -> None:
        """Verify the app can be instantiated and started."""
        app = WxDXX()
        async with app.run_test() as pilot:
            # App should start without errors
            assert app.is_running

    @pytest.mark.asyncio
    async def test_app_has_expected_widgets(self) -> None:
        """Verify core widgets are present after startup."""
        app = WxDXX()
        async with app.run_test() as pilot:
            # Check for sidebar
            from wxdxx.widgets.sidebar import Sidebar
            sidebar = app.query_one(Sidebar)
            assert sidebar is not None

            # Check for product view
            from wxdxx.widgets.product_view import ProductView
            product_view = app.query_one(ProductView)
            assert product_view is not None

            # Check for news ticker
            from wxdxx.widgets.news_ticker import NewsTicker
            ticker = app.query_one(NewsTicker)
            assert ticker is not None

    @pytest.mark.asyncio
    async def test_app_quit_binding(self) -> None:
        """Verify the quit binding works."""
        app = WxDXX()
        async with app.run_test() as pilot:
            await pilot.press("q")
            # App should exit cleanly (no exception raised)

    @pytest.mark.asyncio
    async def test_help_screen_toggle(self) -> None:
        """Verify help screen can be opened and closed."""
        app = WxDXX()
        async with app.run_test() as pilot:
            # Open help
            await pilot.press("?")

            from wxdxx.widgets.help_screen import HelpScreen
            # Help screen should be visible
            assert len(app.screen_stack) > 1
            assert isinstance(app.screen_stack[-1], HelpScreen)

            # Close help
            await pilot.press("?")
            assert len(app.screen_stack) == 1
