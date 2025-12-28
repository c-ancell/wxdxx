"""Sidebar navigation widget."""

from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static

from wxdxx.colors import (
    generate_sidebar_css,
    get_alert_css_class,
    get_md_css_class,
    get_wfo_css_class,
)


class VimListView(ListView):
    """ListView with vim-style keyboard navigation."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "first", "Top", show=False),
        Binding("G", "last", "Bottom", show=False),
        Binding("d", "page_down", "Page Down", show=False),
        Binding("u", "page_up", "Page Up", show=False),
    ]

    def action_page_down(self) -> None:
        """Move cursor down by approximately one page (10 items)."""
        for _ in range(10):
            self.action_cursor_down()

    def action_page_up(self) -> None:
        """Move cursor up by approximately one page (10 items)."""
        for _ in range(10):
            self.action_cursor_up()

    def action_first(self) -> None:
        """Move cursor to the first item."""
        self.index = 0

    def action_last(self) -> None:
        """Move cursor to the last item."""
        if self._nodes:
            self.index = len(self._nodes) - 1


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
        unread: bool = False,
    ) -> None:
        super().__init__(id=id)
        self.base_label = label  # Label without expiry time
        self.item_id = item_id
        self.indent = indent
        self.expires = expires
        self._unread = unread
        self._has_severity = severity_class is not None
        # Calculate initial label with expiry (before compose runs)
        self.label_text = self._compute_expiry_label()
        if severity_class:
            self.add_class(severity_class)
        if unread:
            self.add_class("unread")

    def _compute_expiry_label(self) -> str:
        """Compute the label text including expiry time if applicable."""
        if not self.expires:
            return self.base_label
        now = datetime.now(timezone.utc)
        remaining = (self.expires - now).total_seconds()
        if remaining > 0:
            return f"{self.base_label} ({format_time_remaining(remaining)})"
        return f"{self.base_label} (expired)"

    def _get_display_text(self) -> str:
        """Get the full display text including indent and unread indicator."""
        prefix = "  " * self.indent
        if self._unread:
            # Use different circle colors based on whether item has severity styling
            circle = "[#333333]●[/] " if self._has_severity else "[#aaaaaa]●[/] "
            return f"{prefix}{circle}{self.label_text}"
        return f"{prefix}{self.label_text}"

    def compose(self) -> ComposeResult:
        yield Label(self._get_display_text(), markup=True)

    def update_label(self, new_label: str) -> None:
        """Update the displayed label text."""
        self.label_text = new_label
        self.query_one(Label).update(self._get_display_text())

    def mark_as_read(self) -> None:
        """Mark this item as read (remove unread indicator)."""
        if self._unread:
            self._unread = False
            self.remove_class("unread")
            self.query_one(Label).update(self._get_display_text())

    def mark_as_unread(self) -> None:
        """Mark this item as unread (show indicator)."""
        if not self._unread:
            self._unread = True
            self.add_class("unread")
            self.query_one(Label).update(self._get_display_text())

    @property
    def is_unread(self) -> bool:
        """Check if this item is unread."""
        return self._unread

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

""" + generate_sidebar_css() + """
    """

    class ItemSelected(Message):
        """Message sent when a sidebar item is selected."""

        def __init__(self, item_id: str) -> None:
            super().__init__()
            self.item_id = item_id

    def compose(self) -> ComposeResult:
        yield VimListView(
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
        return get_md_css_class(watch_prob)

    def update_mds(
        self,
        mds: list[tuple[int, str | None, int | None, datetime | None]],
        read_items: set[str] | None = None,
    ) -> None:
        """Update the MDs section with active discussions.

        Args:
            mds: List of (md_number, concerning_text, watch_probability, expires) tuples
            read_items: Set of item_ids that have been read (won't show unread indicator)
        """
        read_items = read_items or set()
        listview = self.query_one("#sidebar-list", VimListView)

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
                item_id = f"md-{md_num}"
                severity_class = self._get_md_severity_class(watch_prob)
                item = SidebarItem(
                    base_label,
                    item_id,
                    indent=1,
                    severity_class=severity_class,
                    expires=expires,
                    unread=item_id not in read_items,
                )
                item.add_class("md-item")
                listview.mount(item, after=cat_mds)

    def update_watches(
        self,
        watches: list[tuple[int, str, bool, datetime | None]],
        read_items: set[str] | None = None,
    ) -> None:
        """Update the Watches section with active watches.

        Args:
            watches: List of (watch_number, watch_type, is_pds, expires) tuples
                    watch_type is "tornado" or "severe_thunderstorm"
            read_items: Set of item_ids that have been read (won't show unread indicator)
        """
        read_items = read_items or set()
        listview = self.query_one("#sidebar-list", VimListView)

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
                item_id = f"watch-{watch_num}"

                # Determine severity class (PDS takes priority)
                if is_pds:
                    severity_class = "watch-pds"
                elif watch_type == "tornado":
                    severity_class = "watch-tor"
                else:
                    severity_class = "watch-svr"

                item = SidebarItem(
                    base_label,
                    item_id,
                    indent=1,
                    severity_class=severity_class,
                    expires=expires,
                    unread=item_id not in read_items,
                )
                item.add_class("watch-item")
                listview.mount(item, after=cat_watches)

    def add_wfo(self, wfo_id: str) -> None:
        """Add a new WFO section to the sidebar."""
        listview = self.query_one("#sidebar-list", VimListView)

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
        listview = self.query_one("#sidebar-list", VimListView)

        # Move cursor to first item before removing to avoid IndexError
        # when the currently selected item is deleted
        listview.index = 0

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
        return get_wfo_css_class(product_type)

    def _get_alert_severity_class(self, event: str) -> str | None:
        """Get CSS class for alert based on event type."""
        return get_alert_css_class(event)

    def update_wfo_products(
        self,
        wfo_id: str,
        products: list[tuple[str, str, str, datetime | None]],  # (id, type, time, expires)
        alerts: list | None = None,  # list[WFOAlert]
        read_items: set[str] | None = None,
    ) -> None:
        """Update the products and alerts list for a specific WFO.

        Args:
            wfo_id: The WFO identifier
            products: List of (product_id, product_type, time_str, expires) tuples
            alerts: Optional list of WFOAlert objects
            read_items: Set of item_ids that have been read (won't show unread indicator)
        """
        read_items = read_items or set()
        listview = self.query_one("#sidebar-list", VimListView)

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

        # Track alert types to deduplicate products (prefer alert styling)
        alert_types: set[str] = set()

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
                # Use tracked wfo_id (not alert.wfo) to match cache key in _load_alert
                all_items.append({
                    "label": alert.short_event,
                    "item_id": f"alert-{wfo_id}-{alert.id}",
                    "severity_class": severity_class,
                    "expires": alert.expires,
                })
                alert_types.add(alert.short_event)

        # Add products (skip if already shown as alert)
        for product_id, product_type, time_str, expires in products:
            if product_type in alert_types:
                continue  # Dedupe: prefer alert version for styling
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
                item_id = item_data["item_id"]
                item = SidebarItem(
                    item_data["label"],
                    item_id,
                    indent=2,
                    severity_class=item_data["severity_class"],
                    expires=item_data.get("expires"),
                    unread=item_id not in read_items,
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

    def mark_item_as_read(self, item_id: str) -> None:
        """Mark a sidebar item as read (remove unread indicator).

        Args:
            item_id: The item_id of the sidebar item to mark as read
        """
        for item in self.query(SidebarItem):
            if item.item_id == item_id:
                item.mark_as_read()
                break

    def mark_all_as_read(self, read_items: set[str]) -> int:
        """Mark all sidebar items as read.

        Args:
            read_items: Set to update with all item_ids that were marked as read

        Returns:
            Number of items that were marked as read
        """
        count = 0
        for item in self.query(SidebarItem):
            if item.is_unread:
                item.mark_as_read()
                read_items.add(item.item_id)
                count += 1
        return count
