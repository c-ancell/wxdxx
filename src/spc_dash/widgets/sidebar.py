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
            SidebarItem("AFD", "wfo-afd", indent=1),
            SidebarItem("Warnings", "wfo-warnings", indent=1),
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
            # No active MDs
            item = SidebarItem("No active MDs", "mds-none", indent=1, id="mds-placeholder")
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
            # No active watches
            item = SidebarItem("No active watches", "watches-none", indent=1, id="watches-placeholder")
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

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection in the ListView."""
        item = event.item
        if isinstance(item, SidebarItem):
            self.post_message(self.ItemSelected(item.item_id))
