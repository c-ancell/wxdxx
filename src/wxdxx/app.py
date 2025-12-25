"""Main WxDXX application."""

import asyncio
import re
import time
from datetime import datetime, timezone

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from .api.nws import NWSClient
from .api.spc import SPCClient
from .models.md import MesoscaleDiscussion
from .models.outlook import OutlookDay
from .models.watch import Watch
from .models.wfo import DEFAULT_PRODUCT_TYPES, WFOProduct
from .widgets.help_screen import HelpScreen
from .widgets.product_view import ProductView
from .widgets.sidebar import Sidebar
from .widgets.wfo_input import WFOInputDialog


def format_timedelta(td_seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    abs_seconds = abs(int(td_seconds))
    hours, remainder = divmod(abs_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


class ClockWidget(Static):
    """Widget displaying UTC and local time, plus product timing info."""

    def on_mount(self) -> None:
        """Start the clock update interval."""
        self.update_clock()
        self.set_interval(1, self.update_clock)

    def update_clock(self) -> None:
        """Update the clock display."""
        utc_now = datetime.now(timezone.utc)
        local_now = datetime.now()

        clock_str = f"UTC: {utc_now.strftime('%H:%M:%S')} | Local: {local_now.strftime('%H:%M:%S')}"

        # Check for product timing info from app
        app = self.app
        parts = []

        # Show refresh indicator
        if hasattr(app, "_is_refreshing") and app._is_refreshing:
            parts.append("[bold cyan]Refreshing...[/]")

        if hasattr(app, "_current_product_issued") and app._current_product_issued:
            issued = app._current_product_issued
            if issued.tzinfo is None:
                issued = issued.replace(tzinfo=timezone.utc)
            since = (utc_now - issued).total_seconds()
            parts.append(f"Issued: {format_timedelta(since)} ago")

        if hasattr(app, "_current_product_expires") and app._current_product_expires:
            expires = app._current_product_expires
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            until = (expires - utc_now).total_seconds()
            if until > 0:
                parts.append(f"Expires: in {format_timedelta(until)}")
            else:
                parts.append(f"Expired: {format_timedelta(-until)} ago")

        parts.append(clock_str)
        self.update(" | ".join(parts))


class WxDXX(App):
    """TUI application for viewing NWS text products."""

    TITLE = "WxDXX"
    SUB_TITLE = "NWS Text Product Viewer"

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

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
    }

    ClockWidget {
        dock: right;
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("w", "add_wfo", "Add WFO"),
        Binding("W", "remove_wfo", "Remove WFO", show=False),
        Binding("?", "help", "Help"),
        Binding("tab", "toggle_focus", "Switch Panel", show=False),
        Binding("1", "view_day1", "Day 1", show=False),
        Binding("2", "view_day2", "Day 2", show=False),
        Binding("3", "view_day3", "Day 3", show=False),
    ]

    AUTO_REFRESH_INTERVAL = 60  # seconds

    def __init__(self) -> None:
        super().__init__()
        self.spc_client = SPCClient()
        self.nws_client = NWSClient()
        self._cached_mds: dict[int, MesoscaleDiscussion] = {}
        self._cached_watches: dict[int, Watch] = {}
        self._tracked_wfos: set[str] = set()
        self._cached_wfo_products: dict[str, WFOProduct] = {}
        # Current product timing for status bar display
        self._current_product_issued: datetime | None = None
        self._current_product_expires: datetime | None = None
        # Auto-refresh state
        self._is_refreshing: bool = False

    def _set_product_timing(
        self,
        issued: datetime | None = None,
        expires: datetime | None = None,
    ) -> None:
        """Set the current product timing for status bar display."""
        self._current_product_issued = issued
        self._current_product_expires = expires

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Sidebar(),
            ProductView(),
            id="main-container",
        )
        yield Horizontal(Footer(), ClockWidget(), id="status-bar")

    async def on_mount(self) -> None:
        """Initialize the app by fetching active products and start auto-refresh."""
        self.run_worker(self._refresh_all_data_with_indicator())
        self.set_interval(self.AUTO_REFRESH_INTERVAL, self._auto_refresh)

    def _auto_refresh(self) -> None:
        """Trigger auto-refresh of all data."""
        self.run_worker(self._refresh_all_data_with_indicator())

    async def _refresh_all_data_with_indicator(self) -> None:
        """Refresh all data with status bar indicator."""
        min_display_time = 2.0  # Show "Refreshing..." for at least 2 seconds
        start_time = time.monotonic()

        self._is_refreshing = True
        self._update_clock_display()
        try:
            await self._refresh_sidebar_data()
            for wfo_id in self._tracked_wfos:
                await self._refresh_wfo_products(wfo_id)

            # Ensure indicator shows for minimum time
            elapsed = time.monotonic() - start_time
            if elapsed < min_display_time:
                await asyncio.sleep(min_display_time - elapsed)
        finally:
            self._is_refreshing = False
            self._update_clock_display()

    def _update_clock_display(self) -> None:
        """Force immediate update of the clock widget."""
        try:
            clock = self.query_one(ClockWidget)
            clock.update_clock()
        except Exception:
            pass  # Widget may not be mounted yet

    async def _refresh_sidebar_data(self) -> None:
        """Fetch MDs and watches and update the sidebar."""
        sidebar = self.query_one(Sidebar)
        now = datetime.now(timezone.utc)

        # Fetch MDs
        try:
            mds = await self.spc_client.get_active_mds()
            self._cached_mds = {md.number: md for md in mds}
            # Filter out expired MDs
            active_mds = [
                md for md in mds
                if md.expires is None or md.expires > now
            ]
            md_data = [(md.number, md.concerning) for md in active_mds]
            sidebar.update_mds(md_data)
        except Exception as e:
            sidebar.update_mds([])
            self.notify(f"Failed to fetch MDs: {e}", severity="error")

        # Fetch watches
        try:
            watches = await self.spc_client.get_active_watches()
            self._cached_watches = {w.number: w for w in watches}
            # Filter out expired watches
            active_watches = [
                w for w in watches
                if w.expires is None or w.expires > now
            ]
            watch_data = [(w.number, w.watch_type.value, w.is_pds) for w in active_watches]
            sidebar.update_watches(watch_data)
        except Exception as e:
            sidebar.update_watches([])
            self.notify(f"Failed to fetch watches: {e}", severity="error")

    async def on_unmount(self) -> None:
        """Clean up when app closes."""
        await self.spc_client.close()
        await self.nws_client.close()

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
            self._set_product_timing()
            product_view.show_product(
                "Mesoscale Discussions",
                "No current Mesoscale Discussions.",
            )
        elif item_id in ("watches-none", "watches-loading"):
            self._set_product_timing()
            product_view.show_product(
                "Watches",
                "No current Watches.",
            )
        elif item_id == "wfo-hint":
            self._set_product_timing()
            product_view.show_product(
                "WFO Products",
                "Press 'w' to add a Weather Forecast Office.\n\n"
                "Enter a 3-letter WFO ID (e.g., OUN, FWD, ICT) to track products from that office.",
            )
        elif item_id.startswith("wfo-") and "-header" in item_id:
            # WFO header clicked - show info about this WFO
            self._set_product_timing()
            wfo_id = item_id.split("-")[1]
            product_view.show_product(
                f"WFO {wfo_id}",
                f"Products from Weather Forecast Office {wfo_id}.\n\n"
                f"Press 'W' to remove this WFO.",
            )
        elif item_id.startswith("wfo-"):
            # WFO product selected - format: wfo-{WFO}-{product_id}
            parts = item_id.split("-", 2)
            if len(parts) == 3:
                wfo_id, product_id = parts[1], parts[2]
                if product_id not in ("loading", "none"):
                    await self._load_wfo_product(product_id)

    async def _load_outlook(self, day: OutlookDay) -> None:
        """Load and display a convective outlook."""
        product_view = self.query_one(ProductView)
        product_view.show_loading(f"Fetching {day.value} outlook...")

        try:
            outlook = await self.spc_client.get_outlook(day)
            risk_str = f"Max Risk: {outlook.max_risk.value}" if outlook.max_risk else ""
            self._set_product_timing(issued=outlook.issued, expires=outlook.valid_end)
            product_view.show_product(outlook.title, outlook.text, risk_str)
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(str(e))

    async def _load_md(self, md_num: int) -> None:
        """Load and display a specific mesoscale discussion."""
        product_view = self.query_one(ProductView)

        # Check cache first
        if md_num in self._cached_mds:
            md = self._cached_mds[md_num]
            self._set_product_timing(issued=md.issued, expires=md.expires)
            product_view.show_product(md.title, md.text)
            return

        # Fetch from API
        product_view.show_loading(f"Fetching MD {md_num}...")
        try:
            md = await self.spc_client.get_md(md_num)
            self._cached_mds[md_num] = md
            self._set_product_timing(issued=md.issued, expires=md.expires)
            product_view.show_product(md.title, md.text)
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(f"Failed to fetch MD {md_num}: {e}")

    async def _load_watch(self, watch_num: int) -> None:
        """Load and display a specific watch."""
        product_view = self.query_one(ProductView)

        # Check cache first
        if watch_num in self._cached_watches:
            watch = self._cached_watches[watch_num]
            self._set_product_timing(issued=watch.issued, expires=watch.expires)
            product_view.show_product(watch.title, watch.text)
            return

        # Fetch from API - need to determine watch type
        product_view.show_loading(f"Fetching Watch {watch_num}...")
        try:
            # Try fetching as severe thunderstorm first (more common)
            from .models.watch import WatchType
            watch = await self.spc_client.get_watch(watch_num, WatchType.SEVERE_THUNDERSTORM)
            self._cached_watches[watch_num] = watch
            self._set_product_timing(issued=watch.issued, expires=watch.expires)
            product_view.show_product(watch.title, watch.text)
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(f"Failed to fetch Watch {watch_num}: {e}")

    def action_refresh(self) -> None:
        """Refresh the sidebar data."""
        self._cached_mds.clear()
        self._cached_watches.clear()
        self._cached_wfo_products.clear()
        self.run_worker(self._refresh_all_data_with_indicator())

    def action_help(self) -> None:
        """Toggle help screen."""
        # Check if help screen is already showing (top of stack)
        if self.screen_stack and isinstance(self.screen_stack[-1], HelpScreen):
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())

    def action_toggle_focus(self) -> None:
        """Toggle focus between sidebar and content view."""
        from textual.widgets import ListView

        product_view = self.query_one(ProductView)
        sidebar_list = self.query_one("#sidebar-list", ListView)

        if product_view.has_focus:
            sidebar_list.focus()
        else:
            product_view.focus()

    async def action_view_day1(self) -> None:
        """Quick key to view Day 1 outlook."""
        await self._load_outlook(OutlookDay.DAY1)

    async def action_view_day2(self) -> None:
        """Quick key to view Day 2 outlook."""
        await self._load_outlook(OutlookDay.DAY2)

    async def action_view_day3(self) -> None:
        """Quick key to view Day 3 outlook."""
        await self._load_outlook(OutlookDay.DAY3)

    def action_add_wfo(self) -> None:
        """Show dialog to add a WFO."""
        self.push_screen(WFOInputDialog(), callback=self._on_add_wfo_result)

    def _on_add_wfo_result(self, result: str | None) -> None:
        """Handle result from add WFO dialog."""
        if result:
            self.run_worker(self._add_wfo(result))

    def action_remove_wfo(self) -> None:
        """Show dialog to remove a WFO."""
        if not self._tracked_wfos:
            self.notify("No WFOs are being tracked")
            return

        self.push_screen(WFOInputDialog(), callback=self._on_remove_wfo_result)

    def _on_remove_wfo_result(self, result: str | None) -> None:
        """Handle result from remove WFO dialog."""
        if result and result in self._tracked_wfos:
            self._tracked_wfos.remove(result)
            self.query_one(Sidebar).remove_wfo(result)
            # Clear cached products for this WFO
            to_remove = [k for k in self._cached_wfo_products if self._cached_wfo_products[k].wfo == result]
            for k in to_remove:
                del self._cached_wfo_products[k]
            self.notify(f"Removed WFO {result}")
        elif result:
            self.notify(f"WFO {result} is not being tracked", severity="warning")

    async def _add_wfo(self, wfo_id: str) -> None:
        """Add a WFO and fetch its products."""
        if wfo_id in self._tracked_wfos:
            self.notify(f"WFO {wfo_id} is already being tracked")
            return

        # Validate WFO exists
        self.notify(f"Validating WFO {wfo_id}...")
        is_valid = await self.nws_client.validate_wfo(wfo_id)
        if not is_valid:
            self.notify(f"Invalid WFO ID: {wfo_id}", severity="error")
            return

        self._tracked_wfos.add(wfo_id)
        self.query_one(Sidebar).add_wfo(wfo_id)
        self.notify(f"Added WFO {wfo_id}")

        # Fetch products
        self.run_worker(self._refresh_wfo_products(wfo_id))

    async def _refresh_wfo_products(self, wfo_id: str) -> None:
        """Refresh products for a specific WFO."""
        sidebar = self.query_one(Sidebar)
        products_data = []

        for product_type in DEFAULT_PRODUCT_TYPES:
            try:
                products = await self.nws_client.get_products_by_type(
                    wfo_id, product_type, limit=1
                )
                for product in products:
                    time_str = product.issued.strftime("%H:%M") if product.issued else ""
                    products_data.append((product.id, product.product_type, time_str))
            except Exception:
                continue

        sidebar.update_wfo_products(wfo_id, products_data)

    async def _load_wfo_product(self, product_id: str) -> None:
        """Load and display a WFO product."""
        product_view = self.query_one(ProductView)

        # Check cache
        if product_id in self._cached_wfo_products:
            product = self._cached_wfo_products[product_id]
            if product.text:
                self._set_product_timing(issued=product.issued)
                product_view.show_product(product.title, product.text)
                return

        # Fetch from API
        product_view.show_loading("Fetching product...")
        try:
            product = await self.nws_client.get_product(product_id)
            self._cached_wfo_products[product_id] = product
            self._set_product_timing(issued=product.issued)
            product_view.show_product(product.title, product.text or "No content")
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(f"Failed to fetch product: {e}")


def main() -> None:
    """Entry point for WxDXX."""
    app = WxDXX()
    app.run()


if __name__ == "__main__":
    main()
