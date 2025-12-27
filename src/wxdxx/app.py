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
from .cache import TTLCache
from .config import AppConfig
from .models.alert import WFOAlert
from .models.md import MesoscaleDiscussion
from .models.outlook import ConvectiveOutlook, OutlookDay
from .models.watch import Watch
from .models.wfo import DEFAULT_PRODUCT_TYPES, WFOProduct
from .widgets.help_screen import HelpScreen
from .widgets.news_ticker import NewsTicker, TickerHeadline
from .widgets.product_view import ProductView
from .widgets.settings_screen import SettingsScreen
from .widgets.sidebar import Sidebar
from .widgets.wfo_input import WFODialogMode, WFOInputDialog


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
    ]

    AUTO_REFRESH_INTERVAL = 60  # seconds

    # Cache TTL values (in seconds)
    OUTLOOK_CACHE_TTL = 300  # 5 minutes
    MD_LIST_CACHE_TTL = 120  # 2 minutes
    WATCH_LIST_CACHE_TTL = 120  # 2 minutes
    MD_CACHE_TTL = 600  # 10 minutes
    WATCH_CACHE_TTL = 600  # 10 minutes
    WFO_LIST_CACHE_TTL = 120  # 2 minutes
    WFO_PRODUCT_CACHE_TTL = 1800  # 30 minutes
    WFO_ZONES_CACHE_TTL = 86400  # 24 hours (zones rarely change)
    WFO_ALERTS_CACHE_TTL = 120  # 2 minutes (alerts change frequently)
    TICKER_CACHE_TTL = 60  # 1 minute (nationwide alerts for ticker)

    def __init__(self) -> None:
        super().__init__()
        # Load configuration
        self._config = AppConfig.load()
        self.spc_client = SPCClient()
        self.nws_client = NWSClient()
        # TTL-based caches
        self._outlook_cache: TTLCache[str, ConvectiveOutlook] = TTLCache(
            default_ttl=self.OUTLOOK_CACHE_TTL, max_size=10
        )
        self._md_list_cache: TTLCache[str, list[MesoscaleDiscussion]] = TTLCache(
            default_ttl=self.MD_LIST_CACHE_TTL, max_size=1
        )
        self._watch_list_cache: TTLCache[str, list[Watch]] = TTLCache(
            default_ttl=self.WATCH_LIST_CACHE_TTL, max_size=1
        )
        self._cached_mds: TTLCache[int, MesoscaleDiscussion] = TTLCache(
            default_ttl=self.MD_CACHE_TTL, max_size=50
        )
        self._cached_watches: TTLCache[int, Watch] = TTLCache(
            default_ttl=self.WATCH_CACHE_TTL, max_size=50
        )
        self._wfo_list_cache: TTLCache[str, list[tuple[str, str, str]]] = TTLCache(
            default_ttl=self.WFO_LIST_CACHE_TTL, max_size=50
        )
        self._cached_wfo_products: TTLCache[str, WFOProduct] = TTLCache(
            default_ttl=self.WFO_PRODUCT_CACHE_TTL, max_size=100
        )
        self._wfo_zones_cache: TTLCache[str, list[str]] = TTLCache(
            default_ttl=self.WFO_ZONES_CACHE_TTL, max_size=50
        )
        self._wfo_alerts_cache: TTLCache[str, list[WFOAlert]] = TTLCache(
            default_ttl=self.WFO_ALERTS_CACHE_TTL, max_size=50
        )
        self._ticker_cache: TTLCache[str, list[WFOAlert]] = TTLCache(
            default_ttl=self.TICKER_CACHE_TTL, max_size=1
        )
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
        yield NewsTicker(id="news-ticker")
        yield Horizontal(
            Sidebar(),
            ProductView(),
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
            await self._refresh_sidebar_data()
            # Refresh ticker data (nationwide alerts + SPC watches)
            await self._refresh_ticker_data()
            # Refresh all WFOs in parallel
            if self._tracked_wfos:
                await asyncio.gather(
                    *[self._refresh_wfo_products(wfo_id) for wfo_id in self._tracked_wfos]
                )

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
        """Fetch MDs and watches and update the sidebar."""
        sidebar = self.query_one(Sidebar)
        now = datetime.now(timezone.utc)

        # Fetch MDs (use cache if available)
        try:
            mds = self._md_list_cache.get("active")
            if mds is None:
                mds = await self.spc_client.get_active_mds()
                self._md_list_cache.set("active", mds)
                # Also cache individual MDs
                for md in mds:
                    self._cached_mds.set(md.number, md)

            # Filter out expired MDs
            active_mds = [
                md for md in mds
                if md.expires is None or md.expires > now
            ]
            md_data = [
                (md.number, md.concerning, md.watch_probability, md.expires)
                for md in active_mds
            ]
            sidebar.update_mds(md_data, read_items=self._read_items)
        except Exception as e:
            sidebar.update_mds([], read_items=self._read_items)
            self.notify(f"Failed to fetch MDs: {e}", severity="error")

        # Fetch watches (use cache if available)
        try:
            watches = self._watch_list_cache.get("active")
            if watches is None:
                watches = await self.spc_client.get_active_watches()
                self._watch_list_cache.set("active", watches)
                # Also cache individual watches
                for watch in watches:
                    self._cached_watches.set(watch.number, watch)

            # Filter out expired watches
            active_watches = [
                w for w in watches
                if w.expires is None or w.expires > now
            ]
            watch_data = [
                (w.number, w.watch_type.value, w.is_pds, w.expires)
                for w in active_watches
            ]
            sidebar.update_watches(watch_data, read_items=self._read_items)
        except Exception as e:
            sidebar.update_watches([], read_items=self._read_items)
            self.notify(f"Failed to fetch watches: {e}", severity="error")

        # Fetch outlook risk levels for sidebar coloring (use cache if available)
        for day in [OutlookDay.DAY1, OutlookDay.DAY2, OutlookDay.DAY3]:
            try:
                cache_key = day.value
                outlook = self._outlook_cache.get(cache_key)
                if outlook is None:
                    outlook = await self.spc_client.get_outlook(day)
                    self._outlook_cache.set(cache_key, outlook)

                day_num = int(day.value.replace("day", ""))
                sidebar.update_outlook_risk(
                    day_num, outlook.max_risk.value if outlook.max_risk else None
                )
            except Exception:
                pass  # Silently fail - risk will show when user clicks

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
            cached_alerts = self._ticker_cache.get("nationwide")
            if cached_alerts is None:
                cached_alerts = await self.nws_client.get_active_alerts_nationwide()
                self._ticker_cache.set("nationwide", cached_alerts)

            for alert in cached_alerts:
                # Skip expired alerts
                if alert.expires and alert.expires < now:
                    continue

                # Format expiry time in UTC
                expires_str = ""
                if alert.expires:
                    expires_str = alert.expires.strftime("%d/%H%MZ")

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
            watches = self._watch_list_cache.get("active") or []
            for watch in watches:
                # Skip expired watches
                if watch.expires and watch.expires < now:
                    continue

                # Format expiry time in UTC
                expires_str = ""
                if watch.expires:
                    expires_str = watch.expires.strftime("%d/%H%MZ")

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
        cache_key = day.value  # "day1", "day2", "day3"
        day_num = int(day.value.replace("day", ""))

        # Check cache first
        cached = self._outlook_cache.get(cache_key)
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
            self._outlook_cache.set(cache_key, outlook)
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
        cached = self._cached_mds.get(md_num)
        if cached:
            self._set_product_timing(issued=cached.issued, expires=cached.expires)
            product_view.show_product(cached.title, cached.text)
            return

        # Fetch from API
        product_view.show_loading(f"Fetching MD {md_num}...")
        try:
            md = await self.spc_client.get_md(md_num)
            self._cached_mds.set(md_num, md)
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
        cached = self._cached_watches.get(watch_num)
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
            self._cached_watches.set(watch_num, watch)
            self._set_product_timing(issued=watch.issued, expires=watch.expires)
            product_view.show_product(watch.title, watch.text)
        except Exception as e:
            self._set_product_timing()
            product_view.show_error(f"Failed to fetch Watch {watch_num}: {e}")

    def action_refresh(self) -> None:
        """Force refresh - clear all caches and fetch fresh data."""
        self._outlook_cache.clear()
        self._md_list_cache.clear()
        self._watch_list_cache.clear()
        self._cached_mds.clear()
        self._cached_watches.clear()
        self._wfo_list_cache.clear()
        self._cached_wfo_products.clear()
        self._wfo_alerts_cache.clear()
        self._ticker_cache.clear()
        # Note: _wfo_zones_cache is NOT cleared (zones rarely change)
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
            ),
            callback=self._on_settings_result,
        )

    def _on_settings_result(self, new_interval: int | None) -> None:
        """Handle settings screen result."""
        if new_interval is not None and new_interval != self._config.refresh_interval:
            self._config.refresh_interval = new_interval
            self._config.save()
            # The auto-refresh loop will pick up the new interval on its next cycle
            self.notify(f"Refresh interval set to {new_interval}s")

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

        self.push_screen(WFOInputDialog(WFODialogMode.REMOVE), callback=self._on_remove_wfo_result)

    def _on_remove_wfo_result(self, result: str | None) -> None:
        """Handle result from remove WFO dialog."""
        if result and result in self._tracked_wfos:
            self._tracked_wfos.remove(result)
            self.query_one(Sidebar).remove_wfo(result)

            # Clear cached product lists for this WFO
            for product_type in DEFAULT_PRODUCT_TYPES:
                self._wfo_list_cache.invalidate(f"{result}:{product_type}")

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
            cache_key = f"{wfo_id}:{product_type}"

            # Check cache first
            cached = self._wfo_list_cache.get(cache_key)
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
                self._wfo_list_cache.set(cache_key, result)
                return result
            except Exception:
                return []

        async def fetch_alerts() -> list[WFOAlert]:
            """Fetch alerts for this WFO's zones."""
            # Check alert cache first
            cached_alerts = self._wfo_alerts_cache.get(wfo_id)
            if cached_alerts is not None:
                return cached_alerts

            # Get zones (cached long-term)
            zones = self._wfo_zones_cache.get(wfo_id)
            if zones is None:
                try:
                    zones = await self.nws_client.get_wfo_zones(wfo_id)
                    self._wfo_zones_cache.set(wfo_id, zones)
                except Exception:
                    zones = []

            if not zones:
                return []

            # Fetch alerts for zones
            try:
                alerts = await self.nws_client.get_active_alerts(zones)
                self._wfo_alerts_cache.set(wfo_id, alerts)
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
        cached = self._cached_wfo_products.get(product_id)
        if cached and cached.text:
            self._set_product_timing(issued=cached.issued)
            product_view.show_product(cached.title, cached.text)
            return

        # Fetch from API
        product_view.show_loading("Fetching product...")
        try:
            product = await self.nws_client.get_product(product_id)
            self._cached_wfo_products.set(product_id, product)
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

        # Try to find in cache
        cached_alerts = self._wfo_alerts_cache.get(wfo_id)
        if cached_alerts:
            for alert in cached_alerts:
                if alert.id == alert_id or alert.sidebar_id.endswith(alert_id):
                    self._set_product_timing(issued=alert.effective, expires=alert.expires)
                    product_view.show_product(alert.title, alert.text)
                    return

        # Not found in cache - show error (alerts should always be in cache)
        self._set_product_timing()
        product_view.show_error("Alert no longer available. Try refreshing.")


def main() -> None:
    """Entry point for WxDXX."""
    app = WxDXX()
    app.run()


if __name__ == "__main__":
    main()
