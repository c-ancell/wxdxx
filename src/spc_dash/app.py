"""Main SPC Dash application."""

import re

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from .api.spc import SPCClient
from .models.md import MesoscaleDiscussion
from .models.outlook import OutlookDay
from .models.watch import Watch
from .widgets.product_view import ProductView
from .widgets.sidebar import Sidebar


class SPCDash(App):
    """TUI application for viewing SPC and WFO weather products."""

    TITLE = "SPC Dash"
    SUB_TITLE = "Storm Prediction Center Product Viewer"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
    }

    .home-container {
        align: center middle;
        padding: 4;
    }

    .home-container .title {
        text-style: bold;
        color: $primary;
        text-align: center;
        margin-bottom: 1;
    }

    .home-container .subtitle {
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("?", "help", "Help"),
        Binding("1", "view_day1", "Day 1", show=False),
        Binding("2", "view_day2", "Day 2", show=False),
        Binding("3", "view_day3", "Day 3", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.spc_client = SPCClient()
        self._cached_mds: dict[int, MesoscaleDiscussion] = {}
        self._cached_watches: dict[int, Watch] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Sidebar(),
            ProductView(),
            id="main-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the app by fetching active products."""
        self.run_worker(self._refresh_sidebar_data())

    async def _refresh_sidebar_data(self) -> None:
        """Fetch MDs and watches and update the sidebar."""
        sidebar = self.query_one(Sidebar)

        # Fetch MDs
        try:
            mds = await self.spc_client.get_active_mds()
            self._cached_mds = {md.number: md for md in mds}
            md_data = [(md.number, md.concerning) for md in mds]
            sidebar.update_mds(md_data)
        except Exception as e:
            sidebar.update_mds([])
            self.notify(f"Failed to fetch MDs: {e}", severity="error")

        # Fetch watches
        try:
            watches = await self.spc_client.get_active_watches()
            self._cached_watches = {w.number: w for w in watches}
            watch_data = [(w.number, w.watch_type.value, w.is_pds) for w in watches]
            sidebar.update_watches(watch_data)
        except Exception as e:
            sidebar.update_watches([])
            self.notify(f"Failed to fetch watches: {e}", severity="error")

    async def on_unmount(self) -> None:
        """Clean up when app closes."""
        await self.spc_client.close()

    async def on_sidebar_item_selected(self, event: Sidebar.ItemSelected) -> None:
        """Handle sidebar item selection."""
        product_view = self.query_one(ProductView)
        item_id = event.item_id

        if item_id == "outlook-day1":
            await self._load_outlook(OutlookDay.DAY1)
        elif item_id == "outlook-day2":
            await self._load_outlook(OutlookDay.DAY2)
        elif item_id == "outlook-day3":
            await self._load_outlook(OutlookDay.DAY3)
        elif item_id.startswith("md-"):
            # Individual MD selected
            md_match = re.match(r"md-(\d+)", item_id)
            if md_match:
                md_num = int(md_match.group(1))
                await self._load_md(md_num)
        elif item_id.startswith("watch-"):
            # Individual watch selected
            watch_match = re.match(r"watch-(\d+)", item_id)
            if watch_match:
                watch_num = int(watch_match.group(1))
                await self._load_watch(watch_num)
        elif item_id in ("mds-none", "mds-loading"):
            product_view.show_product(
                "Mesoscale Discussions",
                "No active Mesoscale Discussions at this time.",
            )
        elif item_id in ("watches-none", "watches-loading"):
            product_view.show_product(
                "Watches",
                "No active Watches at this time.",
            )
        elif item_id == "wfo-afd":
            product_view.show_product(
                "Area Forecast Discussion",
                "WFO product support coming soon.\n\nThis will allow you to view AFDs from local forecast offices.",
            )
        elif item_id == "wfo-warnings":
            product_view.show_product(
                "Warnings",
                "WFO warnings support coming soon.\n\nThis will display active warnings from local forecast offices.",
            )

    async def _load_outlook(self, day: OutlookDay) -> None:
        """Load and display a convective outlook."""
        product_view = self.query_one(ProductView)
        product_view.show_loading(f"Fetching {day.value} outlook...")

        try:
            outlook = await self.spc_client.get_outlook(day)
            risk_str = f"Max Risk: {outlook.max_risk.value}" if outlook.max_risk else ""
            product_view.show_product(outlook.title, outlook.text, risk_str)
        except Exception as e:
            product_view.show_error(str(e))

    async def _load_md(self, md_num: int) -> None:
        """Load and display a specific mesoscale discussion."""
        product_view = self.query_one(ProductView)

        # Check cache first
        if md_num in self._cached_mds:
            md = self._cached_mds[md_num]
            product_view.show_product(md.title, md.text)
            return

        # Fetch from API
        product_view.show_loading(f"Fetching MD {md_num}...")
        try:
            md = await self.spc_client.get_md(md_num)
            self._cached_mds[md_num] = md
            product_view.show_product(md.title, md.text)
        except Exception as e:
            product_view.show_error(f"Failed to fetch MD {md_num}: {e}")

    async def _load_watch(self, watch_num: int) -> None:
        """Load and display a specific watch."""
        product_view = self.query_one(ProductView)

        # Check cache first
        if watch_num in self._cached_watches:
            watch = self._cached_watches[watch_num]
            product_view.show_product(watch.title, watch.text)
            return

        # Fetch from API - need to determine watch type
        product_view.show_loading(f"Fetching Watch {watch_num}...")
        try:
            # Try fetching as severe thunderstorm first (more common)
            from .models.watch import WatchType
            watch = await self.spc_client.get_watch(watch_num, WatchType.SEVERE_THUNDERSTORM)
            self._cached_watches[watch_num] = watch
            product_view.show_product(watch.title, watch.text)
        except Exception as e:
            product_view.show_error(f"Failed to fetch Watch {watch_num}: {e}")

    def action_refresh(self) -> None:
        """Refresh the sidebar data."""
        self._cached_mds.clear()
        self._cached_watches.clear()
        self.notify("Refreshing...")
        self.run_worker(self._refresh_sidebar_data())

    def action_help(self) -> None:
        """Show help information."""
        self.notify("SPC Dash - Press Q to quit, R to refresh")

    async def action_view_day1(self) -> None:
        """Quick key to view Day 1 outlook."""
        await self._load_outlook(OutlookDay.DAY1)

    async def action_view_day2(self) -> None:
        """Quick key to view Day 2 outlook."""
        await self._load_outlook(OutlookDay.DAY2)

    async def action_view_day3(self) -> None:
        """Quick key to view Day 3 outlook."""
        await self._load_outlook(OutlookDay.DAY3)


def main() -> None:
    """Entry point for SPC Dash."""
    app = SPCDash()
    app.run()


if __name__ == "__main__":
    main()
