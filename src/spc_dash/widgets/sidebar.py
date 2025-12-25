"""Sidebar navigation widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static


class SidebarItem(ListItem):
    """A clickable item in the sidebar."""

    def __init__(self, label: str, item_id: str, indent: int = 0, id: str | None = None) -> None:
        super().__init__(id=id)
        self.label_text = label
        self.item_id = item_id
        self.indent = indent

    def compose(self) -> ComposeResult:
        prefix = "  " * self.indent
        yield Label(f"{prefix}{self.label_text}")

    def update_label(self, new_label: str) -> None:
        """Update the displayed label text."""
        self.label_text = new_label
        prefix = "  " * self.indent
        self.query_one(Label).update(f"{prefix}{new_label}")


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

    def update_mds(self, mds: list[tuple[int, str | None]]) -> None:
        """Update the MDs section with active discussions.

        Args:
            mds: List of (md_number, concerning_text) tuples
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
        cat_index = listview._nodes.index(cat_mds)

        if not mds:
            # No current MDs - don't set an ID, use class for cleanup
            item = SidebarItem("None current", "mds-none", indent=1)
            item.add_class("md-item")
            listview.mount(item, after=cat_mds)
        else:
            # Add each MD as a sidebar item (in reverse so they appear in order)
            for md_num, concerning in reversed(mds):
                label = f"MD {md_num}"
                if concerning:
                    # Truncate long concerning text
                    short = concerning[:15] + "..." if len(concerning) > 18 else concerning
                    label = f"MD {md_num}"
                item = SidebarItem(label, f"md-{md_num}", indent=1)
                item.add_class("md-item")
                listview.mount(item, after=cat_mds)

    def update_watches(self, watches: list[tuple[int, str, bool]]) -> None:
        """Update the Watches section with active watches.

        Args:
            watches: List of (watch_number, watch_type, is_pds) tuples
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
            for watch_num, watch_type, is_pds in reversed(watches):
                prefix = "TOR" if watch_type == "tornado" else "SVR"
                pds = " PDS" if is_pds else ""
                label = f"{prefix} {watch_num}{pds}"
                item = SidebarItem(label, f"watch-{watch_num}", indent=1)
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
        if not listview.query(".wfo-header"):
            cat_wfo = self.query_one("#cat-wfo")
            placeholder = SidebarItem("Press 'w' to add", "wfo-hint", indent=1, id="wfo-placeholder")
            listview.mount(placeholder, after=cat_wfo)

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
                item = SidebarItem(label, f"wfo-{wfo_id}-{product_id}", indent=2)
                item.add_class(f"wfo-{wfo_id}-item")
                listview.mount(item, after=wfo_header)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection in the ListView."""
        item = event.item
        if isinstance(item, SidebarItem):
            self.post_message(self.ItemSelected(item.item_id))
