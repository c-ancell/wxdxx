"""Sidebar navigation widget."""

from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static


def format_time_remaining(seconds: float) -> str:
    """Format remaining time as 'Xh Ym' or 'Xm'."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, _ = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class SidebarItem(ListItem):
    """A clickable item in the sidebar."""

    def __init__(
        self,
        label: str,
        item_id: str,
        indent: int = 0,
        id: str | None = None,
        severity_class: str | None = None,
        expires: datetime | None = None,
    ) -> None:
        super().__init__(id=id)
        self.base_label = label  # Label without expiry time
        self.item_id = item_id
        self.indent = indent
        self.expires = expires
        # Calculate initial label with expiry (before compose runs)
        self.label_text = self._compute_expiry_label()
        if severity_class:
            self.add_class(severity_class)

    def _compute_expiry_label(self) -> str:
        """Compute the label text including expiry time if applicable."""
        if not self.expires:
            return self.base_label
        now = datetime.now(timezone.utc)
        remaining = (self.expires - now).total_seconds()
        if remaining > 0:
            return f"{self.base_label} ({format_time_remaining(remaining)})"
        return f"{self.base_label} (expired)"

    def compose(self) -> ComposeResult:
        prefix = "  " * self.indent
        yield Label(f"{prefix}{self.label_text}")

    def update_label(self, new_label: str) -> None:
        """Update the displayed label text."""
        self.label_text = new_label
        prefix = "  " * self.indent
        self.query_one(Label).update(f"{prefix}{new_label}")

    def refresh_expiry_label(self) -> None:
        """Recalculate and update the label based on current expiry time."""
        if not self.expires:
            return
        new_label = self._compute_expiry_label()
        if new_label != self.label_text:
            self.update_label(new_label)


class SidebarCategory(Static):
    """A category header in the sidebar."""

    def __init__(self, title: str, expanded: bool = True) -> None:
        super().__init__()
        self.title = title
        self.expanded = expanded

    def compose(self) -> ComposeResult:
        icon = "▾" if self.expanded else "▸"
        yield Label(f"{icon} {self.title}")


class Sidebar(Vertical):
    """Left navigation sidebar with collapsible categories."""

    DEFAULT_CSS = """
    Sidebar {
        width: 30;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
    }

    Sidebar ListView {
        background: transparent;
        padding: 0;
    }

    Sidebar ListItem {
        padding: 0 1;
    }

    Sidebar ListItem:hover {
        background: $primary-darken-2;
    }

    Sidebar ListItem.-active {
        background: $primary;
    }

    Sidebar .category-header {
        color: $text-muted;
        padding: 1 0 0 0;
        text-style: bold;
    }

    /* Watch severity colors (NWS standard) */
    Sidebar ListItem.watch-tor {
        background: #ff0000;
        color: #ffffff;
    }
    Sidebar ListItem.watch-tor:hover {
        background: #cc0000;
    }
    Sidebar ListItem.watch-svr {
        background: #ffff00;
        color: #000000;
    }
    Sidebar ListItem.watch-svr:hover {
        background: #cccc00;
    }
    Sidebar ListItem.watch-pds {
        background: #ff00ff;
        color: #ffffff;
    }
    Sidebar ListItem.watch-pds:hover {
        background: #cc00cc;
    }

    /* Outlook risk level colors (NWS/SPC standard) */
    Sidebar ListItem.risk-tstm {
        background: #90ee90;
        color: #000000;
    }
    Sidebar ListItem.risk-tstm:hover {
        background: #70ce70;
    }
    Sidebar ListItem.risk-mrgl {
        background: #008000;
        color: #ffffff;
    }
    Sidebar ListItem.risk-mrgl:hover {
        background: #006600;
    }
    Sidebar ListItem.risk-slgt {
        background: #ffff00;
        color: #000000;
    }
    Sidebar ListItem.risk-slgt:hover {
        background: #cccc00;
    }
    Sidebar ListItem.risk-enh {
        background: #ffa500;
        color: #000000;
    }
    Sidebar ListItem.risk-enh:hover {
        background: #cc8400;
    }
    Sidebar ListItem.risk-mdt {
        background: #ff0000;
        color: #ffffff;
    }
    Sidebar ListItem.risk-mdt:hover {
        background: #cc0000;
    }
    Sidebar ListItem.risk-high {
        background: #ff00ff;
        color: #ffffff;
    }
    Sidebar ListItem.risk-high:hover {
        background: #cc00cc;
    }

    /* MD watch probability colors */
    Sidebar ListItem.md-prob-med {
        background: #fffacd;
        color: #000000;
    }
    Sidebar ListItem.md-prob-med:hover {
        background: #e6e1b8;
    }
    Sidebar ListItem.md-prob-high {
        background: #ffd700;
        color: #000000;
    }
    Sidebar ListItem.md-prob-high:hover {
        background: #ccac00;
    }
    Sidebar ListItem.md-prob-likely {
        background: #ff6347;
        color: #ffffff;
    }
    Sidebar ListItem.md-prob-likely:hover {
        background: #cc4f39;
    }

    /* WFO product type colors */
    Sidebar ListItem.wfo-warn-tor {
        background: #ff0000;
        color: #ffffff;
    }
    Sidebar ListItem.wfo-warn-tor:hover {
        background: #cc0000;
    }
    Sidebar ListItem.wfo-warn-svr {
        background: #ffa500;
        color: #000000;
    }
    Sidebar ListItem.wfo-warn-svr:hover {
        background: #cc8400;
    }
    Sidebar ListItem.wfo-warn-ffw {
        background: #228b22;
        color: #ffffff;
    }
    Sidebar ListItem.wfo-warn-ffw:hover {
        background: #1b6f1b;
    }
    Sidebar ListItem.wfo-warn-wsw {
        background: #ffb6c1;
        color: #000000;
    }
    Sidebar ListItem.wfo-warn-wsw:hover {
        background: #cc919a;
    }
    Sidebar ListItem.wfo-stmt {
        background: #f0e68c;
        color: #000000;
    }
    Sidebar ListItem.wfo-stmt:hover {
        background: #c0b870;
    }

    /* Alert colors (NWS standard per-event colors) */
    /* Tornado */
    Sidebar ListItem.alert-tor {
        background: #ff0000;
        color: #ffffff;
    }
    Sidebar ListItem.alert-tor:hover {
        background: #cc0000;
    }
    /* Severe Thunderstorm */
    Sidebar ListItem.alert-svr {
        background: #ffa500;
        color: #000000;
    }
    Sidebar ListItem.alert-svr:hover {
        background: #cc8400;
    }
    /* Flash Flood */
    Sidebar ListItem.alert-ffw {
        background: #8b0000;
        color: #ffffff;
    }
    Sidebar ListItem.alert-ffw:hover {
        background: #6e0000;
    }
    /* Flood Warning */
    Sidebar ListItem.alert-flw {
        background: #00ff00;
        color: #000000;
    }
    Sidebar ListItem.alert-flw:hover {
        background: #00cc00;
    }
    /* Flood Watch/Advisory */
    Sidebar ListItem.alert-fla {
        background: #2e8b57;
        color: #ffffff;
    }
    Sidebar ListItem.alert-fla:hover {
        background: #256f46;
    }
    /* Winter Storm Warning */
    Sidebar ListItem.alert-wsw {
        background: #ff69b4;
        color: #000000;
    }
    Sidebar ListItem.alert-wsw:hover {
        background: #cc5490;
    }
    /* Winter Storm Watch */
    Sidebar ListItem.alert-wsa {
        background: #4169e1;
        color: #ffffff;
    }
    Sidebar ListItem.alert-wsa:hover {
        background: #3454b4;
    }
    /* Winter Weather Advisory */
    Sidebar ListItem.alert-wwa {
        background: #7b68ee;
        color: #ffffff;
    }
    Sidebar ListItem.alert-wwa:hover {
        background: #6253be;
    }
    /* Wind Advisory */
    Sidebar ListItem.alert-wind {
        background: #d2b48c;
        color: #000000;
    }
    Sidebar ListItem.alert-wind:hover {
        background: #a89070;
    }
    /* High Wind Warning */
    Sidebar ListItem.alert-hww {
        background: #daa520;
        color: #000000;
    }
    Sidebar ListItem.alert-hww:hover {
        background: #ae841a;
    }
    /* Heat Advisory */
    Sidebar ListItem.alert-heat {
        background: #ff7f50;
        color: #000000;
    }
    Sidebar ListItem.alert-heat:hover {
        background: #cc6640;
    }
    /* Excessive Heat Warning */
    Sidebar ListItem.alert-ehw {
        background: #c71585;
        color: #ffffff;
    }
    Sidebar ListItem.alert-ehw:hover {
        background: #9f116a;
    }
    /* Freeze Warning */
    Sidebar ListItem.alert-frz {
        background: #483d8b;
        color: #ffffff;
    }
    Sidebar ListItem.alert-frz:hover {
        background: #3a316f;
    }
    /* Frost Advisory */
    Sidebar ListItem.alert-fst {
        background: #6495ed;
        color: #000000;
    }
    Sidebar ListItem.alert-fst:hover {
        background: #5077be;
    }
    /* Dense Fog Advisory */
    Sidebar ListItem.alert-fog {
        background: #708090;
        color: #ffffff;
    }
    Sidebar ListItem.alert-fog:hover {
        background: #5a6673;
    }
    /* Special Weather Statement */
    Sidebar ListItem.alert-sps {
        background: #ffe4b5;
        color: #000000;
    }
    Sidebar ListItem.alert-sps:hover {
        background: #ccb691;
    }
    /* Generic fallbacks */
    Sidebar ListItem.alert-warning {
        background: #ff0000;
        color: #ffffff;
    }
    Sidebar ListItem.alert-warning:hover {
        background: #cc0000;
    }
    Sidebar ListItem.alert-watch {
        background: #ffa500;
        color: #000000;
    }
    Sidebar ListItem.alert-watch:hover {
        background: #cc8400;
    }
    Sidebar ListItem.alert-advisory {
        background: #ffff00;
        color: #000000;
    }
    Sidebar ListItem.alert-advisory:hover {
        background: #cccc00;
    }
    """

    class ItemSelected(Message):
        """Message sent when a sidebar item is selected."""

        def __init__(self, item_id: str) -> None:
            super().__init__()
            self.item_id = item_id

    def compose(self) -> ComposeResult:
        yield ListView(
            # Outlooks category
            ListItem(Label("▾ Outlooks", classes="category-header"), id="cat-outlooks"),
            SidebarItem("Day 1", "outlook-day1", indent=1),
            SidebarItem("Day 2", "outlook-day2", indent=1),
            SidebarItem("Day 3", "outlook-day3", indent=1),
            # MDs category
            ListItem(Label("▾ Mesoscale Discussions", classes="category-header"), id="cat-mds"),
            SidebarItem("Loading...", "mds-loading", indent=1, id="mds-placeholder"),
            # Watches category
            ListItem(Label("▾ Watches", classes="category-header"), id="cat-watches"),
            SidebarItem("Loading...", "watches-loading", indent=1, id="watches-placeholder"),
            # WFO category
            ListItem(Label("▾ WFO Products", classes="category-header"), id="cat-wfo"),
            SidebarItem("Press 'w' to add", "wfo-hint", indent=1, id="wfo-placeholder"),
            id="sidebar-list",
        )

    def on_mount(self) -> None:
        """Start timer to refresh expiry labels."""
        self.set_interval(30, self._refresh_expiry_labels)

    def _refresh_expiry_labels(self) -> None:
        """Refresh all sidebar items that have expiry times."""
        for item in self.query(SidebarItem):
            item.refresh_expiry_label()

    def _get_md_severity_class(self, watch_prob: int | None) -> str | None:
        """Get CSS class based on MD watch probability."""
        if watch_prob is None:
            return None
        if watch_prob >= 80:
            return "md-prob-likely"
        if watch_prob >= 60:
            return "md-prob-high"
        if watch_prob >= 20:
            return "md-prob-med"
        return None  # Low probability, no highlighting

    def update_mds(
        self, mds: list[tuple[int, str | None, int | None, datetime | None]]
    ) -> None:
        """Update the MDs section with active discussions.

        Args:
            mds: List of (md_number, concerning_text, watch_probability, expires) tuples
        """
        listview = self.query_one("#sidebar-list", ListView)

        # Remove existing MD items (placeholder or previous items)
        for item in list(listview.query(".md-item")):
            item.remove()

        # Find the placeholder and remove it if it exists
        try:
            placeholder = self.query_one("#mds-placeholder")
            placeholder.remove()
        except Exception:
            pass

        # Find the MDs category header to insert after
        cat_mds = self.query_one("#cat-mds")

        if not mds:
            # No current MDs - don't set an ID, use class for cleanup
            item = SidebarItem("None current", "mds-none", indent=1)
            item.add_class("md-item")
            listview.mount(item, after=cat_mds)
        else:
            # Add each MD as a sidebar item (in reverse so they appear in order)
            for md_num, concerning, watch_prob, expires in reversed(mds):
                base_label = f"MD {md_num}"
                severity_class = self._get_md_severity_class(watch_prob)
                item = SidebarItem(
                    base_label,
                    f"md-{md_num}",
                    indent=1,
                    severity_class=severity_class,
                    expires=expires,
                )
                item.add_class("md-item")
                listview.mount(item, after=cat_mds)

    def update_watches(
        self, watches: list[tuple[int, str, bool, datetime | None]]
    ) -> None:
        """Update the Watches section with active watches.

        Args:
            watches: List of (watch_number, watch_type, is_pds, expires) tuples
                    watch_type is "tornado" or "severe_thunderstorm"
        """
        listview = self.query_one("#sidebar-list", ListView)

        # Remove existing watch items
        for item in list(listview.query(".watch-item")):
            item.remove()

        # Find the placeholder and remove it if it exists
        try:
            placeholder = self.query_one("#watches-placeholder")
            placeholder.remove()
        except Exception:
            pass

        # Find the Watches category header to insert after
        cat_watches = self.query_one("#cat-watches")

        if not watches:
            # No current watches - don't set an ID, use class for cleanup
            item = SidebarItem("None current", "watches-none", indent=1)
            item.add_class("watch-item")
            listview.mount(item, after=cat_watches)
        else:
            # Add each watch as a sidebar item (in reverse so they appear in order)
            for watch_num, watch_type, is_pds, expires in reversed(watches):
                prefix = "TOR" if watch_type == "tornado" else "SVR"
                pds = " PDS" if is_pds else ""
                base_label = f"{prefix} {watch_num}{pds}"

                # Determine severity class (PDS takes priority)
                if is_pds:
                    severity_class = "watch-pds"
                elif watch_type == "tornado":
                    severity_class = "watch-tor"
                else:
                    severity_class = "watch-svr"

                item = SidebarItem(
                    base_label,
                    f"watch-{watch_num}",
                    indent=1,
                    severity_class=severity_class,
                    expires=expires,
                )
                item.add_class("watch-item")
                listview.mount(item, after=cat_watches)

    def add_wfo(self, wfo_id: str) -> None:
        """Add a new WFO section to the sidebar."""
        listview = self.query_one("#sidebar-list", ListView)

        # Remove the placeholder hint if it exists
        try:
            placeholder = self.query_one("#wfo-placeholder")
            placeholder.remove()
        except Exception:
            pass

        # Find the WFO category header
        cat_wfo = self.query_one("#cat-wfo")

        # Find where to insert (after existing WFO sections, alphabetically)
        insert_after = cat_wfo
        for item in listview.query(".wfo-header"):
            if item.id and item.id < f"wfo-{wfo_id}-header":
                insert_after = item
                # Also skip past all items for this WFO
                for sub in listview.query(f".wfo-{item.id.split('-')[1]}-item"):
                    insert_after = sub

        # Create WFO header
        wfo_header = SidebarItem(wfo_id, f"wfo-{wfo_id}-header", indent=1, id=f"wfo-{wfo_id}-header")
        wfo_header.add_class("wfo-header")
        listview.mount(wfo_header, after=insert_after)

        # Add loading placeholder
        loading = SidebarItem("Loading...", f"wfo-{wfo_id}-loading", indent=2)
        loading.add_class(f"wfo-{wfo_id}-item")
        listview.mount(loading, after=wfo_header)

    def remove_wfo(self, wfo_id: str) -> None:
        """Remove a WFO and its products from the sidebar."""
        listview = self.query_one("#sidebar-list", ListView)

        # Remove the header
        try:
            header = self.query_one(f"#wfo-{wfo_id}-header")
            header.remove()
        except Exception:
            pass

        # Remove all items for this WFO
        for item in list(listview.query(f".wfo-{wfo_id}-item")):
            item.remove()

        # If no WFOs left, restore the placeholder
        remaining_wfos = list(listview.query(".wfo-header"))
        if len(remaining_wfos) == 0:
            cat_wfo = self.query_one("#cat-wfo")
            placeholder = SidebarItem("Press 'w' to add", "wfo-hint", indent=1, id="wfo-placeholder")
            listview.mount(placeholder, after=cat_wfo)

    def _get_wfo_severity_class(self, product_type: str) -> str | None:
        """Get CSS class for WFO product type."""
        product_type = product_type.upper()

        if product_type == "TOR":
            return "wfo-warn-tor"
        elif product_type == "SVR":
            return "wfo-warn-svr"
        elif product_type == "FFW":
            return "wfo-warn-ffw"
        elif product_type == "WSW":
            return "wfo-warn-wsw"
        elif product_type == "SPS":
            return "wfo-stmt"
        else:
            return None  # AFD, HWO, ZFP, NOW - no special coloring

    def _get_alert_severity_class(self, event: str) -> str | None:
        """Get CSS class for alert based on event type.

        Uses NWS-standard colors for each specific alert type.
        Falls back to generic warning/watch/advisory colors for unknown types.
        """
        event_lower = event.lower()

        # Specific event types with NWS colors
        if "tornado" in event_lower:
            if "warning" in event_lower:
                return "alert-tor"
            return "alert-watch"  # Tornado Watch uses generic watch orange
        elif "severe thunderstorm" in event_lower:
            return "alert-svr"
        elif "flash flood" in event_lower:
            return "alert-ffw"
        elif "flood" in event_lower:
            if "warning" in event_lower:
                return "alert-flw"
            return "alert-fla"  # Watch or advisory
        elif "winter storm" in event_lower:
            if "warning" in event_lower:
                return "alert-wsw"
            return "alert-wsa"  # Watch
        elif "winter weather" in event_lower:
            return "alert-wwa"
        elif "high wind" in event_lower:
            return "alert-hww"
        elif "wind" in event_lower and "advisory" in event_lower:
            return "alert-wind"
        elif "excessive heat" in event_lower:
            return "alert-ehw"
        elif "heat" in event_lower:
            return "alert-heat"
        elif "freeze" in event_lower:
            return "alert-frz"
        elif "frost" in event_lower:
            return "alert-fst"
        elif "fog" in event_lower:
            return "alert-fog"
        elif "special weather statement" in event_lower:
            return "alert-sps"
        # Generic fallbacks
        elif "warning" in event_lower:
            return "alert-warning"
        elif "watch" in event_lower:
            return "alert-watch"
        elif "advisory" in event_lower:
            return "alert-advisory"
        else:
            return None

    def update_wfo_products(
        self,
        wfo_id: str,
        products: list[tuple[str, str, str, datetime | None]],  # (id, type, time, expires)
        alerts: list | None = None,  # list[WFOAlert]
    ) -> None:
        """Update the products and alerts list for a specific WFO.

        Args:
            wfo_id: The WFO identifier
            products: List of (product_id, product_type, time_str, expires) tuples
            alerts: Optional list of WFOAlert objects
        """
        listview = self.query_one("#sidebar-list", ListView)

        # Remove existing items for this WFO
        for item in list(listview.query(f".wfo-{wfo_id}-item")):
            item.remove()

        # Find the WFO header
        try:
            wfo_header = self.query_one(f"#wfo-{wfo_id}-header")
        except Exception:
            return  # WFO not added yet

        # Build combined list: alerts first (more urgent), then products
        all_items: list[dict] = []

        # Add alerts (filtered and sorted by severity)
        if alerts:
            now = datetime.now(timezone.utc)
            active_alerts = [a for a in alerts if a.expires is None or a.expires > now]

            # Sort: warnings > watches > advisories > statements
            def alert_priority(a) -> int:
                event_lower = a.event.lower()
                if "warning" in event_lower:
                    return 0
                elif "watch" in event_lower:
                    return 1
                elif "advisory" in event_lower:
                    return 2
                return 3

            active_alerts.sort(key=alert_priority)

            for alert in active_alerts:
                severity_class = self._get_alert_severity_class(alert.event)
                all_items.append({
                    "label": alert.short_event,
                    "item_id": alert.sidebar_id,
                    "severity_class": severity_class,
                    "expires": alert.expires,
                })

        # Add products
        for product_id, product_type, time_str, expires in products:
            label = f"{product_type} {time_str}" if time_str else product_type
            severity_class = self._get_wfo_severity_class(product_type)
            all_items.append({
                "label": label,
                "item_id": f"wfo-{wfo_id}-{product_id}",
                "severity_class": severity_class,
                "expires": expires,
            })

        if not all_items:
            item = SidebarItem("No products", f"wfo-{wfo_id}-none", indent=2)
            item.add_class(f"wfo-{wfo_id}-item")
            listview.mount(item, after=wfo_header)
        else:
            # Add in reverse order (so they appear in order)
            for item_data in reversed(all_items):
                item = SidebarItem(
                    item_data["label"],
                    item_data["item_id"],
                    indent=2,
                    severity_class=item_data["severity_class"],
                    expires=item_data.get("expires"),
                )
                item.add_class(f"wfo-{wfo_id}-item")
                listview.mount(item, after=wfo_header)

    def update_outlook_risk(self, day: int, risk_level: str | None) -> None:
        """Update the risk level styling for an outlook item.

        Args:
            day: Outlook day (1, 2, or 3)
            risk_level: Risk level string (TSTM, MRGL, SLGT, ENH, MDT, HIGH) or None
        """
        item_id = f"outlook-day{day}"

        # Find the outlook item
        for item in self.query(SidebarItem):
            if item.item_id == item_id:
                # Remove any existing risk classes
                for cls in ["risk-tstm", "risk-mrgl", "risk-slgt", "risk-enh", "risk-mdt", "risk-high"]:
                    item.remove_class(cls)

                # Add new risk class
                if risk_level:
                    risk_class = f"risk-{risk_level.lower()}"
                    item.add_class(risk_class)
                break

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection in the ListView."""
        item = event.item
        if isinstance(item, SidebarItem):
            self.post_message(self.ItemSelected(item.item_id))
