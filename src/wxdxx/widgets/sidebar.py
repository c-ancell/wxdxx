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
        self.label_text = label
        self.item_id = item_id
        self.indent = indent
        self.expires = expires
        if severity_class:
            self.add_class(severity_class)

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
        now = datetime.now(timezone.utc)
        remaining = (self.expires - now).total_seconds()
        if remaining > 0:
            new_label = f"{self.base_label} ({format_time_remaining(remaining)})"
        else:
            new_label = f"{self.base_label} (expired)"
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
                # Calculate initial label with expiry
                item.refresh_expiry_label()
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
                # Calculate initial label with expiry
                item.refresh_expiry_label()
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

    def update_wfo_products(
        self,
        wfo_id: str,
        products: list[tuple[str, str, str]],  # (product_id, product_type, time_str)
    ) -> None:
        """Update the products list for a specific WFO.

        Args:
            wfo_id: The WFO identifier
            products: List of (product_id, product_type, time_str) tuples
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

        if not products:
            item = SidebarItem("No products", f"wfo-{wfo_id}-none", indent=2)
            item.add_class(f"wfo-{wfo_id}-item")
            listview.mount(item, after=wfo_header)
        else:
            # Add products in reverse order (so they appear in order)
            for product_id, product_type, time_str in reversed(products):
                label = f"{product_type} {time_str}" if time_str else product_type
                severity_class = self._get_wfo_severity_class(product_type)
                item = SidebarItem(
                    label, f"wfo-{wfo_id}-{product_id}", indent=2, severity_class=severity_class
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
