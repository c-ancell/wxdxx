"""Widget for displaying weather product text."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class ProductView(VerticalScroll):
    """Scrollable view for displaying weather product text."""

    DEFAULT_CSS = """
    ProductView {
        padding: 1 2;
        background: $surface;
    }

    ProductView .product-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    ProductView .product-content {
        color: $text;
    }

    ProductView .product-meta {
        color: $text-muted;
        margin-top: 1;
        text-style: italic;
    }

    ProductView .loading {
        color: $text-muted;
        text-align: center;
        margin-top: 4;
    }

    ProductView .error {
        color: $error;
        text-align: center;
        margin-top: 4;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._title = ""
        self._content = ""
        self._meta = ""

    def compose(self) -> ComposeResult:
        yield Static("Select a product from the sidebar", classes="loading", id="product-loading")
        yield Static("", classes="product-title", id="product-title")
        yield Static("", classes="product-content", id="product-content")
        yield Static("", classes="product-meta", id="product-meta")

    def show_loading(self, message: str = "Loading...") -> None:
        """Show a loading message."""
        self.query_one("#product-loading", Static).update(message)
        self.query_one("#product-loading").display = True
        self.query_one("#product-title").display = False
        self.query_one("#product-content").display = False
        self.query_one("#product-meta").display = False

    def show_error(self, message: str) -> None:
        """Show an error message."""
        loading = self.query_one("#product-loading", Static)
        loading.update(f"Error: {message}")
        loading.remove_class("loading")
        loading.add_class("error")
        loading.display = True
        self.query_one("#product-title").display = False
        self.query_one("#product-content").display = False
        self.query_one("#product-meta").display = False

    def show_product(self, title: str, content: str, meta: str = "") -> None:
        """Display a product with title, content, and optional metadata."""
        self.query_one("#product-loading").display = False

        title_widget = self.query_one("#product-title", Static)
        title_widget.update(title)
        title_widget.display = True

        content_widget = self.query_one("#product-content", Static)
        content_widget.update(content)
        content_widget.display = True

        meta_widget = self.query_one("#product-meta", Static)
        if meta:
            meta_widget.update(meta)
            meta_widget.display = True
        else:
            meta_widget.display = False

        self.scroll_home()
