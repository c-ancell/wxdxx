"""Main WxDXX application."""

import asyncio
import re
import time
from datetime import datetime, timezone

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from .api.nws import NWSClient
from .api.spc import SPCClient
from .cache import ProductCache
from .config import TICKER_SPEED_INTERVALS, AppConfig
from .models.alert import WFOAlert
from .models.md import MesoscaleDiscussion
from .models.outlook import ConvectiveOutlook, OutlookDay
from .models.watch import Watch
from .models.wfo import DEFAULT_PRODUCT_TYPES, WFOProduct
from .widgets.help_screen import HelpScreen
from .widgets.news_ticker import NewsTicker, TickerHeadline
from .widgets.product_view import ProductView
from .widgets.settings_screen import SettingsResult, SettingsScreen
from .widgets.sidebar import Sidebar
from .widgets.wfo_input import WFODialogMode, WFOInputDialog
from .widgets.zone_map import ZoneMap


def format_timedelta(td_seconds: float) -> str:
    """Format seconds into a human-readable duration string (minutes resolution)."""
    abs_seconds = abs(int(td_seconds))
    hours, remainder = divmod(abs_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


class ClockWidget(Static):
    """Widget displaying UTC and local time, plus product timing info."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_display: str = ""

    def on_mount(self) -> None:
        """Start the clock update interval."""
        self.update_clock()
        self.set_interval(1, self.update_clock)

    def update_clock(self) -> None:
        """Update the clock display only if content has changed."""
        utc_now = datetime.now(timezone.utc)
        local_now = datetime.now()

        clock_str = f"UTC: {utc_now.strftime('%d %H:%M')} | Local: {local_now.strftime('%d %H:%M')}"

        # Check for product timing info from app
        app = self.app
        parts = []

        # Show refresh indicator
        if hasattr(app, "_is_refreshing") and app._is_refreshing:
            parts.append("[bold cyan]Refreshing...[/]")
        elif hasattr(app, "_last_refresh_time") and app._last_refresh_time:
            # Show time since last refresh (only when not actively refreshing)
            since_refresh = (utc_now - app._last_refresh_time).total_seconds()
            if since_refresh < 60:
                parts.append("Refreshed: <1m ago")
            else:
                parts.append(f"Refreshed: {format_timedelta(since_refresh)} ago")

        # Show WFO loading indicator
        if hasattr(app, "_loading_wfos") and app._loading_wfos:
            wfos = ", ".join(sorted(app._loading_wfos))
            parts.append(f"[bold cyan]Loading {wfos}...[/]")

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
            is_outlook = getattr(app, "_current_product_is_outlook", False)

            if is_outlook:
                # Show date range for outlooks: Valid: DDHHmmZ - DDHHmmZ
                valid_start = getattr(app, "_current_product_valid_start", None)
                if valid_start:
                    if valid_start.tzinfo is None:
                        valid_start = valid_start.replace(tzinfo=timezone.utc)
                    parts.append(
                        f"Valid: {valid_start.strftime('%d%H%MZ')} - {expires.strftime('%d%H%MZ')}"
                    )
                else:
                    parts.append(f"Valid Until: {expires.strftime('%d%H%MZ')}")
            else:
                # Show countdown for MDs/Watches
                if until > 0:
                    parts.append(f"Expires: in {format_timedelta(until)}")
                else:
                    parts.append(f"Expired: {format_timedelta(-until)} ago")

        if hasattr(app, "_current_product_next_scheduled") and app._current_product_next_scheduled:
            next_sched = app._current_product_next_scheduled
            if next_sched.tzinfo is None:
                next_sched = next_sched.replace(tzinfo=timezone.utc)
            until_next = (next_sched - utc_now).total_seconds()
            if until_next > 0:
                parts.append(f"Next: in {format_timedelta(until_next)}")

        parts.append(clock_str)
        new_display = " | ".join(parts)

        # Only trigger UI update if content actually changed
        if new_display != self._last_display:
            self._last_display = new_display
            self.update(new_display)


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

    #content-area {
        height: 1fr;
    }

    ZoneMap {
        height: auto;
        max-height: 30;
        border-top: solid $primary;
        padding: 1;
        background: $surface;
    }

    ZoneMap.hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("s", "settings", "Settings", show=False),
        Binding("w", "add_wfo", "Add WFO", show=False),
        Binding("W", "remove_wfo", "Remove WFO", show=False),
        Binding("?", "help", "Help"),  # Only show help hint; all shortcuts documented there
        Binding("tab", "toggle_focus", "Switch Panel", show=False),
        Binding("1", "view_day1", "Day 1", show=False),
        Binding("2", "view_day2", "Day 2", show=False),
        Binding("3", "view_day3", "Day 3", show=False),
        Binding("M", "mark_all_read", "Mark All Read", show=False),
        Binding("m", "toggle_map", "Toggle Map", show=False),
    ]

    AUTO_REFRESH_INTERVAL = 60  # seconds

    def __init__(self) -> None:
        super().__init__()
        # Load configuration
        self._config = AppConfig.load()
        self.spc_client = SPCClient()
        self.nws_client = NWSClient()
        # Unified product cache with targeted invalidation and state tracking
        self._cache = ProductCache()
        self._tracked_wfos: set[str] = set(self._config.tracked_wfos)
        # Current product timing for status bar display
        self._current_product_issued: datetime | None = None
        self._current_product_expires: datetime | None = None
        self._current_product_valid_start: datetime | None = None
        self._current_product_next_scheduled: datetime | None = None
        self._current_product_is_outlook: bool = False
        # Auto-refresh state
        self._is_refreshing: bool = False
        # WFOs currently loading
        self._loading_wfos: set[str] = set()
        # Last successful refresh time for status bar display
        self._last_refresh_time: datetime | None = None
        # Track which sidebar items have been read (viewed in content pane)
        self._read_items: set[str] = set()
        # Fast-poll tasks for empty MDs/watches (cache_key -> asyncio.Task)
        self._fast_poll_tasks: dict[str, asyncio.Task] = {}
        # Map visibility state
        self._map_visible: bool = False
        # Current alert's affected zones (for map display)
        self._current_alert_zones: list[str] = []

    def _set_product_timing(
        self,
        issued: datetime | None = None,
        expires: datetime | None = None,
        valid_start: datetime | None = None,
        next_scheduled: datetime | None = None,
        is_outlook: bool = False,
    ) -> None:
        """Set the current product timing for status bar display."""
        self._current_product_issued = issued
        self._current_product_expires = expires
        self._current_product_valid_start = valid_start
        self._current_product_next_scheduled = next_scheduled
        self._current_product_is_outlook = is_outlook

    def compose(self) -> ComposeResult:
        yield Header()
        ticker_interval = TICKER_SPEED_INTERVALS.get(self._config.ticker_speed, 0.12)
        yield NewsTicker(id="news-ticker", update_interval=ticker_interval)
        yield Horizontal(
            Sidebar(),
            Vertical(
                ProductView(),
                ZoneMap(id="zone-map", classes="hidden"),
                id="content-area",
            ),
            id="main-container",
        )
        yield Horizontal(Footer(), ClockWidget(), id="status-bar")

    async def on_mount(self) -> None:
        """Initialize the app by fetching active products and start auto-refresh."""
        # Restore saved WFOs to sidebar first (sync operation)
        sidebar = self.query_one(Sidebar)
        for wfo_id in self._tracked_wfos:
            sidebar.add_wfo(wfo_id)

        # Start initial refresh and auto-refresh loop
        # Using call_later to ensure they run after mount completes
        self.call_later(self._start_background_tasks)

    def _start_background_tasks(self) -> None:
        """Start background refresh tasks after mount."""
        self.run_worker(self._initial_refresh_and_loop())

    async def _initial_refresh_and_loop(self) -> None:
        """Run initial refresh, then start the auto-refresh loop."""
        await self._refresh_all_data_with_indicator()
        await self._auto_refresh_loop()

    async def _auto_refresh_loop(self) -> None:
        """Background worker that handles periodic auto-refresh."""
        while True:
            await asyncio.sleep(self._config.refresh_interval)
            if self._is_refreshing:
                self.log.debug("Auto-refresh skipped - already refreshing")
                continue
            self.log.debug("Auto-refresh triggered")
            await self._refresh_all_data_with_indicator()

    async def _refresh_all_data_with_indicator(self) -> None:
        """Refresh all data with status bar indicator."""
        # Prevent concurrent refreshes
        if self._is_refreshing:
            return

        min_display_time = 2.0  # Show "Refreshing..." for at least 2 seconds
        start_time = time.monotonic()

        self._is_refreshing = True
        self._update_clock_display()
        try:
            # Build list of all refresh tasks
            refresh_tasks = [
                self._refresh_sidebar_data(),
                self._refresh_ticker_data(),
            ]
            # Add WFO refresh tasks
            for wfo_id in self._tracked_wfos:
                refresh_tasks.append(self._refresh_wfo_products(wfo_id))

            # Run all refresh tasks in parallel
            await asyncio.gather(*refresh_tasks)

            # Ensure indicator shows for minimum time
            elapsed = time.monotonic() - start_time
            if elapsed < min_display_time:
                await asyncio.sleep(min_display_time - elapsed)

            # Record successful refresh time
            self._last_refresh_time = datetime.now(timezone.utc)
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
        """Fetch MDs, watches, and outlooks and update the sidebar."""
        sidebar = self.query_one(Sidebar)
        now = datetime.now(timezone.utc)

        # Fetch MDs, watches, and outlooks in parallel
        async def fetch_mds() -> list[MesoscaleDiscussion]:
            cached = self._cache.get_md_list()
            if cached is not None:
                return cached
            mds = await self.spc_client.get_active_mds()
            self._cache.set_md_list(mds)
            for md in mds:
                self._cache.set_md(md.number, md)
            return mds

        async def fetch_watches() -> list[Watch]:
            cached = self._cache.get_watch_list()
            if cached is not None:
                return cached
            watches = await self.spc_client.get_active_watches()
            self._cache.set_watch_list(watches)
            for watch in watches:
                self._cache.set_watch(watch.number, watch)
            return watches

        async def fetch_outlook(day: OutlookDay) -> ConvectiveOutlook | None:
            try:
                cached = self._cache.get_outlook(day.value)
                if cached is not None:
                    return cached
                outlook = await self.spc_client.get_outlook(day)
                self._cache.set_outlook(day.value, outlook)
                return outlook
            except Exception:
                return None

        # Run all fetches in parallel
        results = await asyncio.gather(
            fetch_mds(),
            fetch_watches(),
            fetch_outlook(OutlookDay.DAY1),
            fetch_outlook(OutlookDay.DAY2),
            fetch_outlook(OutlookDay.DAY3),
            return_exceptions=True,
        )

        mds_result, watches_result, outlook1, outlook2, outlook3 = results

        # Update MDs
        if isinstance(mds_result, Exception):
            sidebar.update_mds([], read_items=self._read_items)
            self.notify(f"Failed to fetch MDs: {mds_result}", severity="error")
        else:
            active_mds = [
                md for md in mds_result
                if md.expires is None or md.expires > now
            ]
            md_data = [
                (md.number, md.concerning, md.watch_probability, md.expires)
                for md in active_mds
            ]
            sidebar.update_mds(md_data, read_items=self._read_items)

        # Update watches
        if isinstance(watches_result, Exception):
            sidebar.update_watches([], read_items=self._read_items)
            self.notify(f"Failed to fetch watches: {watches_result}", severity="error")
        else:
            active_watches = [
                w for w in watches_result
                if w.expires is None or w.expires > now
            ]
            watch_data = [
                (w.number, w.watch_type.value, w.is_pds, w.expires)
                for w in active_watches
            ]
            sidebar.update_watches(watch_data, read_items=self._read_items)

        # Update outlook risk levels
        for day_num, outlook in [(1, outlook1), (2, outlook2), (3, outlook3)]:
            if outlook is not None and not isinstance(outlook, Exception):
                sidebar.update_outlook_risk(
                    day_num, outlook.max_risk.value if outlook.max_risk else None
                )

        # Start fast-polling for any empty MDs/watches
        self._start_fast_poll_for_empty_products()

    def _start_fast_poll_for_empty_products(self) -> None:
        """Start fast-polling tasks for any empty MDs/watches.

        Checks the cache for products with minimal content and starts
        background polling tasks to fetch content as soon as it's available.
        """
        empty_keys = self._cache.get_empty_products()

        for key in empty_keys:
            # Only fast-poll SPC MDs and watches
            if not key.startswith("spc:md:") and not key.startswith("spc:watch:"):
                continue

            # Don't start duplicate tasks
            if key in self._fast_poll_tasks:
                continue

            # Start fast-poll task
            task = asyncio.create_task(self._fast_poll_product(key))
            self._fast_poll_tasks[key] = task

    async def _fast_poll_product(self, cache_key: str) -> None:
        """Fast-poll an empty product until content appears or timeout.

        Args:
            cache_key: Cache key in format "spc:{md|watch}:{number}"
        """
        POLL_INTERVAL = 15  # seconds
        MAX_DURATION = 300  # 5 minutes

        start_time = time.time()
        parts = cache_key.split(":")
        if len(parts) != 3:
            return

        source, category, identifier = parts

        try:
            while time.time() - start_time < MAX_DURATION:
                await asyncio.sleep(POLL_INTERVAL)

                # Check if task was cancelled or key removed
                if cache_key not in self._fast_poll_tasks:
                    return

                # Fetch fresh content
                if category == "md":
                    md = await self.spc_client.get_md(int(identifier))
                    if md:
                        self._cache.set_md(int(identifier), md, content_text=md.text)
                        if not self._cache.is_empty(cache_key):
                            # Content appeared - trigger sidebar refresh
                            await self._refresh_sidebar_data()
                            return
                elif category == "watch":
                    watch = await self.spc_client.get_watch(int(identifier))
                    if watch:
                        self._cache.set_watch(
                            int(identifier), watch, content_text=watch.text
                        )
                        if not self._cache.is_empty(cache_key):
                            # Content appeared - trigger sidebar refresh
                            await self._refresh_sidebar_data()
                            return
        except asyncio.CancelledError:
            pass  # Task was cancelled, clean exit
        finally:
            # Cleanup task reference
            self._fast_poll_tasks.pop(cache_key, None)

    async def _refresh_ticker_data(self) -> None:
        """Refresh the news ticker with nationwide alerts and SPC watches."""
        try:
            ticker = self.query_one(NewsTicker)
        except Exception:
            return  # Ticker widget not mounted yet

        headlines: list[TickerHeadline] = []
        now = datetime.now(timezone.utc)

        # Fetch nationwide NWS alerts (use cache if available)
        try:
            cached_alerts = self._cache.get_ticker_alerts()
            if cached_alerts is None:
                cached_alerts = await self.nws_client.get_active_alerts_nationwide()
                self._cache.set_ticker_alerts(cached_alerts)

            for alert in cached_alerts:
                # Skip expired alerts
                if alert.expires and alert.expires < now:
                    continue

                # Format expiry time in UTC (convert from original timezone)
                expires_str = ""
                if alert.expires:
                    expires_utc = alert.expires.astimezone(timezone.utc)
                    expires_str = expires_utc.strftime("%d/%H%MZ")

                # Build headline text
                wfo = alert.wfo or "NWS"
                text = f"{wfo}: {alert.event} in effect until {expires_str}"

                headlines.append(
                    TickerHeadline(
                        id=f"nws-{alert.id}",
                        text=text,
                        event_type=alert.short_event,
                        source="nws",
                        wfo=alert.wfo,
                        expires=alert.expires,
                    )
                )
        except Exception as e:
            self.log.warning(f"Failed to fetch nationwide alerts: {e}")

        # Add SPC watches from cached data
        try:
            watches = self._cache.get_watch_list() or []
            for watch in watches:
                # Skip expired watches
                if watch.expires and watch.expires < now:
                    continue

                # Format expiry time in UTC (convert from original timezone)
                expires_str = ""
                if watch.expires:
                    expires_utc = watch.expires.astimezone(timezone.utc)
                    expires_str = expires_utc.strftime("%d/%H%MZ")

                # Determine event type for coloring
                event_type = "TOR" if watch.watch_type.value == "tornado" else "SVR"
                watch_type_str = "Tornado" if event_type == "TOR" else "Severe Thunderstorm"
                pds_str = " PDS" if watch.is_pds else ""

                text = f"SPC: {watch_type_str} Watch #{watch.number}{pds_str} until {expires_str}"

                headlines.append(
                    TickerHeadline(
                        id=f"spc-watch-{watch.number}",
                        text=text,
                        event_type=event_type,
                        source="spc",
                        expires=watch.expires,
                    )
                )
        except Exception as e:
            self.log.warning(f"Failed to add SPC watches to ticker: {e}")

        # Sort headlines by priority (TOR > SVR > FFW > others)
        priority_map = {
            "TOR": 0,
            "SVR": 1,
            "FFW": 2,
            "FLW": 3,
            "BZW": 4,
            "WSW": 5,
            "WWY": 6,
            "HWW": 7,
            "EHW": 8,
        }

        def get_priority(h: TickerHeadline) -> int:
            base_priority = priority_map.get(h.event_type, 10)
            # SPC watches slightly lower priority than NWS warnings
            if h.source == "spc":
                base_priority += 0.5
            return base_priority

        headlines.sort(key=get_priority)

        # Update ticker with headlines
        ticker.update_headlines(headlines)

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
        elif item_id.startswith("alert-"):
            # Alert selected - format: alert-{WFO}-{alert_id}
            parts = item_id.split("-", 2)
            if len(parts) == 3:
                wfo_id, alert_id = parts[1], parts[2]
                await self._load_alert(wfo_id, alert_id, item_id)
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
                    await self._load_wfo_product(product_id, item_id)

    async def _load_outlook(self, day: OutlookDay) -> None:
        """Load and display a convective outlook."""
        product_view = self.query_one(ProductView)
        sidebar = self.query_one(Sidebar)
        day_num = int(day.value.replace("day", ""))

        # Check cache first
        cached = self._cache.get_outlook(day.value)
        if cached:
            risk_str = f"Max Risk: {cached.max_risk.value}" if cached.max_risk else ""
            self._set_product_timing(
                issued=cached.issued,
                expires=cached.valid_end,
                valid_start=cached.valid_start,
                next_scheduled=cached.next_scheduled,
                is_outlook=True,
            )
            product_view.show_product(cached.title, cached.text, risk_str)
            # Update sidebar with risk level highlighting
            sidebar.update_outlook_risk(day_num, cached.max_risk.value if cached.max_risk else None)
            return

        # Fetch from API
        product_view.show_loading(f"Fetching {day.value} outlook...")
        try:
            outlook = await self.spc_client.get_outlook(day)
            self._cache.set_outlook(day.value, outlook)
            risk_str = f"Max Risk: {outlook.max_risk.value}" if outlook.max_risk else ""
            self._set_product_timing(
                issued=outlook.issued,
                expires=outlook.valid_end,
                valid_start=outlook.valid_start,
                next_scheduled=outlook.next_scheduled,
                is_outlook=True,
            )
            product_view.show_product(outlook.title, outlook.text, risk_str)
            # Update sidebar with risk level highlighting
            sidebar.update_outlook_risk(day_num, outlook.max_risk.value if outlook.max_risk else None)
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(str(e))

    async def _load_md(self, md_num: int) -> None:
        """Load and display a specific mesoscale discussion."""
        product_view = self.query_one(ProductView)
        sidebar = self.query_one(Sidebar)
        item_id = f"md-{md_num}"

        # Mark as read
        self._read_items.add(item_id)
        sidebar.mark_item_as_read(item_id)

        # Check cache first
        cached = self._cache.get_md(md_num)
        if cached:
            self._set_product_timing(issued=cached.issued, expires=cached.expires)
            product_view.show_product(cached.title, cached.text)
            return

        # Fetch from API
        product_view.show_loading(f"Fetching MD {md_num}...")
        try:
            md = await self.spc_client.get_md(md_num)
            self._cache.set_md(md_num, md)
            self._set_product_timing(issued=md.issued, expires=md.expires)
            product_view.show_product(md.title, md.text)
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(f"Failed to fetch MD {md_num}: {e}")

    async def _load_watch(self, watch_num: int) -> None:
        """Load and display a specific watch."""
        product_view = self.query_one(ProductView)
        sidebar = self.query_one(Sidebar)
        item_id = f"watch-{watch_num}"

        # Mark as read
        self._read_items.add(item_id)
        sidebar.mark_item_as_read(item_id)

        # Check cache first
        cached = self._cache.get_watch(watch_num)
        if cached:
            self._set_product_timing(issued=cached.issued, expires=cached.expires)
            product_view.show_product(cached.title, cached.text)
            return

        # Fetch from API - need to determine watch type
        product_view.show_loading(f"Fetching Watch {watch_num}...")
        try:
            # Try fetching as severe thunderstorm first (more common)
            from .models.watch import WatchType
            watch = await self.spc_client.get_watch(watch_num, WatchType.SEVERE_THUNDERSTORM)
            self._cache.set_watch(watch_num, watch)
            self._set_product_timing(issued=watch.issued, expires=watch.expires)
            product_view.show_product(watch.title, watch.text)
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(f"Failed to fetch Watch {watch_num}: {e}")

    def action_refresh(self) -> None:
        """Force refresh - clear all caches and fetch fresh data."""
        # Cancel any fast-poll tasks (they'll be restarted if needed after refresh)
        for task in self._fast_poll_tasks.values():
            task.cancel()
        self._fast_poll_tasks.clear()

        # Clear all SPC data
        self._cache.invalidate_by_source("spc")
        # Clear NWS data except zones (zones have 24hr TTL and rarely change)
        self._cache.invalidate_by_pattern(source="nws", category="list")
        self._cache.invalidate_by_pattern(source="nws", category="alert")
        self._cache.invalidate_by_pattern(source="nws", category="product")
        self._cache.invalidate_by_pattern(source="nws", category="ticker")
        self.run_worker(self._refresh_all_data_with_indicator())

    def action_help(self) -> None:
        """Toggle help screen."""
        # Check if help screen is already showing (top of stack)
        if self.screen_stack and isinstance(self.screen_stack[-1], HelpScreen):
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())

    def action_settings(self) -> None:
        """Open settings screen."""
        self.push_screen(
            SettingsScreen(
                current_refresh_interval=self._config.refresh_interval,
                tracked_wfos=list(self._tracked_wfos),
                current_ticker_speed=self._config.ticker_speed,
            ),
            callback=self._on_settings_result,
        )

    def _on_settings_result(self, result: SettingsResult | None) -> None:
        """Handle settings screen result."""
        if result is None:
            return

        changes = []

        # Handle refresh interval change
        if result.refresh_interval != self._config.refresh_interval:
            self._config.refresh_interval = result.refresh_interval
            changes.append(f"refresh interval to {result.refresh_interval}s")

        # Handle ticker speed change
        if result.ticker_speed != self._config.ticker_speed:
            self._config.ticker_speed = result.ticker_speed
            # Update the ticker widget with new interval
            new_interval = TICKER_SPEED_INTERVALS.get(result.ticker_speed, 0.12)
            ticker = self.query_one(NewsTicker)
            ticker.set_update_interval(new_interval)
            changes.append(f"ticker speed to {result.ticker_speed}")

        if changes:
            self._config.save()
            self.notify(f"Updated {' and '.join(changes)}")

    def action_toggle_focus(self) -> None:
        """Toggle focus between sidebar and content view."""
        from .widgets.sidebar import VimListView

        product_view = self.query_one(ProductView)
        sidebar_list = self.query_one("#sidebar-list", VimListView)

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

    def action_mark_all_read(self) -> None:
        """Mark all sidebar items as read."""
        sidebar = self.query_one(Sidebar)
        count = sidebar.mark_all_as_read(self._read_items)
        if count > 0:
            self.notify(f"Marked {count} item{'s' if count != 1 else ''} as read")

    def action_toggle_map(self) -> None:
        """Toggle the zone map visibility."""
        zone_map = self.query_one("#zone-map", ZoneMap)
        self._map_visible = not self._map_visible

        if self._map_visible:
            zone_map.remove_class("hidden")
            # If we have zones to display, render them
            if self._current_alert_zones:
                self.run_worker(self._render_zone_map())
            else:
                zone_map.clear()
                zone_map.set_title("No zones to display")
        else:
            zone_map.add_class("hidden")

    async def _render_zone_map(self) -> None:
        """Fetch zone geometry and render the map."""
        if not self._current_alert_zones:
            return

        zone_map = self.query_one("#zone-map", ZoneMap)
        zone_map.clear()
        zone_map.set_title("Loading zone geometry...")

        # Fetch geometry for all zones
        geometries = await self.nws_client.get_zones_geometry(self._current_alert_zones)

        if not geometries:
            zone_map.set_title("No geometry available")
            return

        # Color map for different alert types
        zone_map.clear()

        # Add each zone polygon
        for zone_id, zone_geo in geometries.items():
            for polygon in zone_geo.polygons:
                zone_map.add_polygon(polygon, color="bright_red")

        # Set title with zone count
        zone_count = len(geometries)
        zone_map.set_title(f"Affected Zones ({zone_count})")
        zone_map.render_map()

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

        self.push_screen(WFOInputDialog(WFODialogMode.REMOVE), callback=self._on_remove_wfo_result)

    def _on_remove_wfo_result(self, result: str | None) -> None:
        """Handle result from remove WFO dialog."""
        if result and result in self._tracked_wfos:
            self._tracked_wfos.remove(result)
            self.query_one(Sidebar).remove_wfo(result)

            # Clear cached product lists and alerts for this WFO
            self._cache.invalidate_by_pattern(source="nws", identifier_prefix=f"{result}:")

            # Auto-save config
            self._config.tracked_wfos = list(self._tracked_wfos)
            self._config.save()

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

        # Auto-save config
        self._config.tracked_wfos = list(self._tracked_wfos)
        self._config.save()

        self.notify(f"Added WFO {wfo_id}")

        # Fetch products
        self.run_worker(self._refresh_wfo_products(wfo_id))

    async def _refresh_wfo_products(self, wfo_id: str) -> None:
        """Refresh products and alerts for a specific WFO."""
        self._loading_wfos.add(wfo_id)
        self._update_clock_display()

        async def fetch_product_type(
            product_type: str,
        ) -> list[tuple[str, str, str, datetime | None]]:
            """Fetch products for a single type, returning tuples for sidebar."""
            # Check cache first
            cached = self._cache.get_wfo_product_list(wfo_id, product_type)
            if cached is not None:
                return cached

            # Fetch from API
            try:
                products = await self.nws_client.get_products_by_type(
                    wfo_id, product_type, limit=1
                )
                # Filter out expired products (SPS will have expires populated)
                now = datetime.now(timezone.utc)
                active_products = [
                    p for p in products if p.expires is None or p.expires > now
                ]
                result = [
                    (
                        p.id,
                        p.product_type,
                        p.issued.strftime("%H:%M") if p.issued else "",
                        p.expires,
                    )
                    for p in active_products
                ]
                self._cache.set_wfo_product_list(wfo_id, product_type, result)
                return result
            except Exception:
                return []

        async def fetch_alerts() -> list[WFOAlert]:
            """Fetch alerts for this WFO's zones."""
            # Check alert cache first
            cached_alerts = self._cache.get_wfo_alerts(wfo_id)
            if cached_alerts is not None:
                return cached_alerts

            # Get zones (cached long-term)
            zones = self._cache.get_wfo_zones(wfo_id)
            if zones is None:
                try:
                    zones = await self.nws_client.get_wfo_zones(wfo_id)
                    self._cache.set_wfo_zones(wfo_id, zones)
                except Exception:
                    zones = []

            if not zones:
                return []

            # Fetch alerts for zones
            try:
                alerts = await self.nws_client.get_active_alerts(zones)
                self._cache.set_wfo_alerts(wfo_id, alerts)
                return alerts
            except Exception:
                return []

        try:
            sidebar = self.query_one(Sidebar)
            # Fetch products and alerts in parallel
            results = await asyncio.gather(
                *[fetch_product_type(pt) for pt in DEFAULT_PRODUCT_TYPES],
                fetch_alerts(),
            )
            # Separate product results from alerts
            product_results = results[:-1]
            alerts = results[-1]
            # Flatten product results
            products_data = [item for sublist in product_results for item in sublist]
            sidebar.update_wfo_products(wfo_id, products_data, alerts, read_items=self._read_items)
        finally:
            self._loading_wfos.discard(wfo_id)
            self._update_clock_display()

    async def _load_wfo_product(self, product_id: str, item_id: str) -> None:
        """Load and display a WFO product."""
        product_view = self.query_one(ProductView)
        sidebar = self.query_one(Sidebar)

        # Mark as read
        self._read_items.add(item_id)
        sidebar.mark_item_as_read(item_id)

        # Check cache
        cached = self._cache.get_wfo_product(product_id)
        if cached and cached.text:
            self._set_product_timing(issued=cached.issued)
            product_view.show_product(cached.title, cached.text)
            return

        # Fetch from API
        product_view.show_loading("Fetching product...")
        try:
            product = await self.nws_client.get_product(product_id)
            self._cache.set_wfo_product(product_id, product)
            self._set_product_timing(issued=product.issued)
            product_view.show_product(product.title, product.text or "No content")
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(f"Failed to fetch product: {e}")

    async def _load_alert(self, wfo_id: str, alert_id: str, item_id: str) -> None:
        """Load and display an alert."""
        product_view = self.query_one(ProductView)
        sidebar = self.query_one(Sidebar)

        # Mark as read
        self._read_items.add(item_id)
        sidebar.mark_item_as_read(item_id)

        # Clear previous zones
        self._current_alert_zones = []

        # Try to find in cache
        cached_alerts = self._cache.get_wfo_alerts(wfo_id)
        if cached_alerts:
            for alert in cached_alerts:
                if alert.id == alert_id or alert.sidebar_id.endswith(alert_id):
                    self._set_product_timing(issued=alert.effective, expires=alert.expires)
                    product_view.show_product(alert.title, alert.text)

                    # Store affected zones for map display
                    self._current_alert_zones = alert.affected_zones

                    # If map is visible, render the zones
                    if self._map_visible and self._current_alert_zones:
                        self.run_worker(self._render_zone_map())
                    elif self._map_visible:
                        zone_map = self.query_one("#zone-map", ZoneMap)
                        zone_map.clear()
                        zone_map.set_title("No zones to display")
                    return

        # Not found in cache - show error (alerts should always be in cache)
        self._set_product_timing()
        self._current_alert_zones = []
        product_view.show_error("Alert no longer available. Try refreshing.")


def main() -> None:
    """Entry point for WxDXX."""
    app = WxDXX()
    app.run()


if __name__ == "__main__":
    main()
