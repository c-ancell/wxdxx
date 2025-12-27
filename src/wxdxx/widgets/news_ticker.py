"""Scrolling news ticker widget for nationwide weather alerts."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from rich.console import RenderableType
from rich.text import Text
from textual.widget import Widget


@dataclass
class TickerHeadline:
    """A headline for the news ticker."""

    id: str
    text: str
    event_type: str  # TOR, SVR, FFW, etc.
    source: str  # "nws" or "spc"
    wfo: str | None = None
    is_new: bool = True
    appearance_count: int = 0
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires: datetime | None = None


# NWS standard colors for weather events
# Background colors for NEW headlines (tuple: bg_color, text_color)
EVENT_BG_COLORS: dict[str, tuple[str, str]] = {
    "TOR": ("red", "white"),
    "SVR": ("yellow", "black"),
    "FFW": ("dark_green", "white"),
    "FLW": ("green", "black"),
    "TOA": ("yellow", "black"),  # Tornado watch
    "SVA": ("dark_goldenrod", "black"),  # Severe thunderstorm watch
    "WSW": ("deep_pink4", "white"),  # Winter storm warning - darker pink
    "WWY": ("purple4", "white"),  # Winter weather advisory - darker purple
    "BZW": ("red1", "white"),  # Blizzard warning
    "ISW": ("dark_magenta", "white"),  # Ice storm warning
    "HWW": ("dark_goldenrod", "black"),  # High wind warning
    "EHW": ("magenta", "white"),  # Excessive heat warning
    "SPC_TOR": ("red", "white"),  # SPC Tornado watch
    "SPC_SVR": ("yellow", "black"),  # SPC Severe watch
}

# Foreground (text) colors for regular headlines
EVENT_FG_COLORS: dict[str, str] = {
    "TOR": "red",
    "SVR": "orange1",
    "FFW": "green",
    "FLW": "dark_green",
    "TOA": "yellow",
    "SVA": "dark_goldenrod",
    "WSW": "deep_pink3",  # Winter storm warning
    "WWY": "medium_purple1",  # Winter weather advisory
    "BZW": "red1",
    "ISW": "magenta",  # Ice storm warning
    "HWW": "dark_goldenrod",
    "EHW": "magenta",
    "SPC_TOR": "red",
    "SPC_SVR": "yellow",
}

# Default colors for unrecognized event types
DEFAULT_BG_COLOR = "blue"
DEFAULT_FG_COLOR = "cyan"


class NewsTicker(Widget):
    """Scrolling news ticker displaying nationwide weather alerts."""

    DEFAULT_CSS = """
    NewsTicker {
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        overflow: hidden;
    }
    """

    # Configuration
    SCROLL_SPEED = 1  # Characters per update interval
    UPDATE_INTERVAL = 0.12  # Seconds between scroll updates (~8 chars/sec)
    EXPIRY_CHECK_INTERVAL = 30.0  # Seconds between expiry checks
    SEPARATOR = " *** "
    NEW_THRESHOLD_APPEARANCES = 2  # Show "NEW" styling for this many full scrolls

    def __init__(
        self,
        *args,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._headlines: list[TickerHeadline] = []
        self._plain_text: str = ""
        self._scroll_offset: int = 0
        self._known_ids: set[str] = set()
        self._paused: bool = False

    def on_mount(self) -> None:
        """Start the scroll animation timer and expiry check timer."""
        self.set_interval(self.UPDATE_INTERVAL, self._scroll_tick)
        self.set_interval(self.EXPIRY_CHECK_INTERVAL, self._expiry_check_tick)

    def _scroll_tick(self) -> None:
        """Advance the scroll position and update display."""
        if self._paused or not self._plain_text:
            return

        self._scroll_offset += self.SCROLL_SPEED

        # Check if we completed a full cycle
        if self._scroll_offset >= len(self._plain_text):
            self._scroll_offset = self._scroll_offset % len(self._plain_text)
            self._increment_appearance_counts()
            # Adjust scroll offset if text got shorter (from is_new transition)
            if self._plain_text and self._scroll_offset >= len(self._plain_text):
                self._scroll_offset = self._scroll_offset % len(self._plain_text)
            # Filter out expired headlines and rebuild text if any were removed
            if self._filter_expired_headlines():
                self._rebuild_plain_text()
                # Reset scroll offset if text got shorter
                if self._plain_text and self._scroll_offset >= len(self._plain_text):
                    self._scroll_offset = 0

        self.refresh()

    def _expiry_check_tick(self) -> None:
        """Periodically check for and remove expired headlines."""
        if not self._headlines:
            return

        if self._filter_expired_headlines():
            self._rebuild_plain_text()
            # Reset scroll offset if text got shorter
            if self._plain_text and self._scroll_offset >= len(self._plain_text):
                self._scroll_offset = 0
            self.refresh()

    def _increment_appearance_counts(self) -> None:
        """Increment appearance count for all headlines after a full scroll cycle."""
        is_new_changed = False
        for headline in self._headlines:
            headline.appearance_count += 1
            # Update is_new status based on appearance count
            if headline.is_new and headline.appearance_count >= self.NEW_THRESHOLD_APPEARANCES:
                headline.is_new = False
                is_new_changed = True

        # Rebuild plain text if any headline transitioned from new to regular
        # This ensures _plain_text matches is_new state for correct positioning
        if is_new_changed:
            self._rebuild_plain_text()

    def _filter_expired_headlines(self) -> bool:
        """Remove expired headlines from the list.

        Returns:
            True if any headlines were removed, False otherwise.
        """
        now = datetime.now(timezone.utc)
        original_count = len(self._headlines)

        # Find expired IDs before filtering
        expired_ids = {
            h.id
            for h in self._headlines
            if h.expires is not None and h.expires <= now
        }

        # Filter out expired headlines
        self._headlines = [
            h for h in self._headlines if h.expires is None or h.expires > now
        ]

        # Remove expired IDs from known set so they can reappear if re-issued
        self._known_ids -= expired_ids

        return len(self._headlines) < original_count

    def update_headlines(self, headlines: list[TickerHeadline]) -> None:
        """Update the ticker with new headline data.

        Args:
            headlines: List of TickerHeadline objects to display
        """
        # Filter out any expired headlines
        now = datetime.now(timezone.utc)
        headlines = [h for h in headlines if h.expires is None or h.expires > now]

        new_ids = {h.id for h in headlines}

        # Identify truly new headlines (never seen before)
        brand_new_ids = new_ids - self._known_ids

        # Process each headline
        for headline in headlines:
            if headline.id in brand_new_ids:
                # Brand new headline
                headline.is_new = True
                headline.appearance_count = 0
            else:
                # Seen before - try to preserve state from previous
                prev = self._get_headline_by_id(headline.id)
                if prev:
                    headline.appearance_count = prev.appearance_count
                    headline.is_new = (
                        prev.is_new
                        and prev.appearance_count < self.NEW_THRESHOLD_APPEARANCES
                    )
                    headline.first_seen = prev.first_seen

        # Update known IDs (remove expired ones)
        self._known_ids = new_ids

        # Replace headlines list
        self._headlines = headlines
        self._rebuild_plain_text()
        self.refresh()

    def _get_headline_by_id(self, headline_id: str) -> TickerHeadline | None:
        """Find a headline by ID in the current list."""
        for h in self._headlines:
            if h.id == headline_id:
                return h
        return None

    def _rebuild_plain_text(self) -> None:
        """Rebuild the plain text string from headlines."""
        # Filter expired headlines before rebuilding
        now = datetime.now(timezone.utc)
        self._headlines = [
            h for h in self._headlines if h.expires is None or h.expires > now
        ]

        if not self._headlines:
            self._plain_text = ""
            return

        parts = []
        for headline in self._headlines:
            if headline.is_new:
                parts.append(f"***NEW: {headline.text}***")
            else:
                parts.append(headline.text)

        self._plain_text = self.SEPARATOR.join(parts)
        # Add separator at the end for seamless wrapping
        if self._plain_text:
            self._plain_text += self.SEPARATOR

    def render(self) -> RenderableType:
        """Render the currently visible portion of the ticker."""
        if not self._headlines:
            return Text("No active severe weather alerts", style="dim")

        if not self._plain_text:
            return Text("")

        width = self.size.width
        if width <= 0:
            return Text("")

        # Build the visible portion with styling
        return self._render_styled_ticker(width)

    def _render_styled_ticker(self, width: int) -> Text:
        """Render the visible ticker portion with Rich styling.

        This method calculates which portion of the ticker is visible
        and applies appropriate styling based on event types.
        """
        text_len = len(self._plain_text)
        if text_len == 0:
            return Text("")

        # Wrap offset to prevent unbounded growth
        offset = self._scroll_offset % text_len

        # Get visible characters (may need to wrap around)
        visible_chars = []
        for i in range(width):
            char_pos = (offset + i) % text_len
            visible_chars.append(self._plain_text[char_pos])

        visible_str = "".join(visible_chars)

        # Now apply styling by finding which headline each character belongs to
        result = Text()
        current_pos = 0

        while current_pos < len(visible_str):
            # Find the headline at this position in the original text
            abs_pos = (offset + current_pos) % text_len
            headline, rel_start, rel_end = self._find_headline_at_position(abs_pos)

            if headline is None:
                # In separator - render as dim
                sep_end = min(
                    len(visible_str),
                    current_pos + self._chars_until_next_headline(abs_pos),
                )
                result.append(visible_str[current_pos:sep_end], style="dim")
                current_pos = sep_end
            else:
                # In a headline - render with appropriate style
                # Calculate how many chars of this headline are visible
                headline_text = self._get_headline_display_text(headline)
                chars_in_headline = rel_end - rel_start
                chars_remaining = len(headline_text) - (abs_pos - rel_start)
                chars_to_render = min(chars_remaining, len(visible_str) - current_pos)

                style = self._get_headline_style(headline)
                result.append(
                    visible_str[current_pos : current_pos + chars_to_render], style=style
                )
                current_pos += chars_to_render

        return result

    def _find_headline_at_position(
        self, pos: int
    ) -> tuple[TickerHeadline | None, int, int]:
        """Find which headline contains the given character position.

        Returns:
            Tuple of (headline, start_pos, end_pos) or (None, -1, -1) if in separator
        """
        current_pos = 0

        for headline in self._headlines:
            headline_text = self._get_headline_display_text(headline)
            headline_len = len(headline_text)

            if current_pos <= pos < current_pos + headline_len:
                return headline, current_pos, current_pos + headline_len

            current_pos += headline_len

            # Account for separator after this headline
            sep_len = len(self.SEPARATOR)
            if current_pos <= pos < current_pos + sep_len:
                return None, -1, -1
            current_pos += sep_len

        return None, -1, -1

    def _chars_until_next_headline(self, pos: int) -> int:
        """Calculate characters until the next headline starts."""
        current_pos = 0

        for headline in self._headlines:
            headline_text = self._get_headline_display_text(headline)
            headline_len = len(headline_text)
            current_pos += headline_len

            sep_len = len(self.SEPARATOR)
            if current_pos <= pos < current_pos + sep_len:
                # In this separator
                return (current_pos + sep_len) - pos
            current_pos += sep_len

        # At the end separator
        return len(self._plain_text) - pos

    def _get_headline_display_text(self, headline: TickerHeadline) -> str:
        """Get the display text for a headline (with or without NEW prefix)."""
        if headline.is_new:
            return f"***NEW: {headline.text}***"
        return headline.text

    def _get_headline_style(self, headline: TickerHeadline) -> str:
        """Get the Rich style string for a headline."""
        event_key = headline.event_type
        if headline.source == "spc":
            event_key = f"SPC_{headline.event_type}"

        if headline.is_new:
            # Background color for new headlines with appropriate text color
            colors = EVENT_BG_COLORS.get(event_key, (DEFAULT_BG_COLOR, "white"))
            bg_color, text_color = colors
            return f"bold {text_color} on {bg_color}"
        else:
            # Foreground color only for regular headlines
            fg_color = EVENT_FG_COLORS.get(event_key, DEFAULT_FG_COLOR)
            return f"bold {fg_color}"

    def pause(self) -> None:
        """Pause the ticker scrolling."""
        self._paused = True

    def resume(self) -> None:
        """Resume the ticker scrolling."""
        self._paused = False

    def toggle_pause(self) -> None:
        """Toggle pause state."""
        self._paused = not self._paused
