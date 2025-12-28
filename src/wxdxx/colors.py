"""Centralized color definitions for weather events.

This module provides a single source of truth for all event-to-color mappings
used across the application (sidebar, news ticker, zone maps).

Color Format Notes:
- bg_hex/fg_hex: CSS hex colors for Textual widgets
- bg_rich/fg_rich: Rich color names for terminal styling
- hover_hex: Darkened background for hover states (auto-calculated)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventColor:
    """Color definition for a weather event type."""

    bg_hex: str  # CSS background (e.g., "#ff0000")
    fg_hex: str  # CSS foreground (e.g., "#ffffff")
    bg_rich: str  # Rich/terminal background (e.g., "red")
    fg_rich: str  # Rich/terminal foreground (e.g., "white")

    @property
    def hover_hex(self) -> str:
        """Calculate a darkened background for hover states (~20% darker)."""
        bg = self.bg_hex.lstrip("#")
        r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
        # Darken by 20%
        r, g, b = int(r * 0.8), int(g * 0.8), int(b * 0.8)
        return f"#{r:02x}{g:02x}{b:02x}"


# =============================================================================
# Master Color Registry - Single Source of Truth
# =============================================================================
# Organized by category for clarity. Keys are short codes used for CSS classes.

# --- Warnings (most severe) ---
ALERT_COLORS: dict[str, EventColor] = {
    # Tornado Warning - NWS red
    "tor": EventColor("#ff0000", "#ffffff", "bright_red", "white"),
    # Severe Thunderstorm Warning - orange
    "svr": EventColor("#ffa500", "#000000", "yellow", "black"),
    # Flash Flood Warning - dark red
    "ffw": EventColor("#8b0000", "#ffffff", "red", "white"),
    # Flood Warning - bright green
    "flw": EventColor("#00ff00", "#000000", "bright_green", "black"),
    # Flood Watch/Advisory - sea green
    "fla": EventColor("#2e8b57", "#ffffff", "green", "white"),
    # Winter Storm Warning - hot pink
    "wsw": EventColor("#ff69b4", "#000000", "bright_magenta", "black"),
    # Winter Storm Watch - royal blue
    "wsa": EventColor("#4169e1", "#ffffff", "blue", "white"),
    # Winter Weather Advisory - medium slate blue
    "wwa": EventColor("#7b68ee", "#ffffff", "magenta", "white"),
    # Blizzard Warning - red
    "bzw": EventColor("#ff0000", "#ffffff", "red1", "white"),
    # Ice Storm Warning - dark magenta
    "isw": EventColor("#8b008b", "#ffffff", "dark_magenta", "white"),
    # Wind Advisory - tan
    "wind": EventColor("#d2b48c", "#000000", "bright_yellow", "black"),
    # High Wind Warning - goldenrod
    "hww": EventColor("#daa520", "#000000", "bright_yellow", "black"),
    # Heat Advisory - coral
    "heat": EventColor("#ff7f50", "#000000", "bright_red", "black"),
    # Excessive Heat Warning - medium violet red
    "ehw": EventColor("#c71585", "#ffffff", "magenta", "white"),
    # Freeze Warning - dark slate blue
    "frz": EventColor("#483d8b", "#ffffff", "blue", "white"),
    # Frost Advisory - cornflower blue
    "fst": EventColor("#6495ed", "#000000", "bright_blue", "black"),
    # Dense Fog Advisory - slate gray
    "fog": EventColor("#708090", "#ffffff", "grey", "white"),
    # Special Weather Statement - moccasin
    "sps": EventColor("#ffe4b5", "#000000", "bright_yellow", "black"),
    # Generic fallbacks
    "warning": EventColor("#ff0000", "#ffffff", "red", "white"),
    "watch": EventColor("#ffa500", "#000000", "yellow", "black"),
    "advisory": EventColor("#ffff00", "#000000", "bright_yellow", "black"),
}

# --- SPC Watch Colors (for sidebar) ---
WATCH_COLORS: dict[str, EventColor] = {
    # Tornado Watch - red
    "watch-tor": EventColor("#ff0000", "#ffffff", "red", "white"),
    # Severe Thunderstorm Watch - yellow
    "watch-svr": EventColor("#ffff00", "#000000", "yellow", "black"),
    # PDS (Particularly Dangerous Situation) - magenta
    "watch-pds": EventColor("#ff00ff", "#ffffff", "magenta", "white"),
}

# --- WFO Product Type Colors ---
WFO_COLORS: dict[str, EventColor] = {
    # Tornado Warning (WFO product)
    "wfo-warn-tor": EventColor("#ff0000", "#ffffff", "red", "white"),
    # Severe Thunderstorm Warning
    "wfo-warn-svr": EventColor("#ffa500", "#000000", "orange1", "black"),
    # Flash Flood Warning
    "wfo-warn-ffw": EventColor("#228b22", "#ffffff", "dark_green", "white"),
    # Winter Storm Warning (WFO product) - lighter pink
    "wfo-warn-wsw": EventColor("#ffb6c1", "#000000", "deep_pink3", "black"),
    # Special Weather Statement
    "wfo-stmt": EventColor("#f0e68c", "#000000", "khaki", "black"),
}

# --- Outlook Risk Level Colors (SPC) ---
OUTLOOK_COLORS: dict[str, EventColor] = {
    "risk-tstm": EventColor("#90ee90", "#000000", "light_green", "black"),
    "risk-mrgl": EventColor("#008000", "#ffffff", "green", "white"),
    "risk-slgt": EventColor("#ffff00", "#000000", "yellow", "black"),
    "risk-enh": EventColor("#ffa500", "#000000", "orange1", "black"),
    "risk-mdt": EventColor("#ff0000", "#ffffff", "red", "white"),
    "risk-high": EventColor("#ff00ff", "#ffffff", "magenta", "white"),
}

# --- MD Watch Probability Colors ---
MD_PROB_COLORS: dict[str, EventColor] = {
    "md-prob-med": EventColor("#fffacd", "#000000", "light_yellow", "black"),
    "md-prob-high": EventColor("#ffd700", "#000000", "gold", "black"),
    "md-prob-likely": EventColor("#ff6347", "#ffffff", "tomato", "white"),
}

# --- News Ticker Colors (Rich color names) ---
# These use Rich color names optimized for terminal display
TICKER_BG_COLORS: dict[str, tuple[str, str]] = {
    "TOR": ("red", "white"),
    "SVR": ("yellow", "black"),
    "FFW": ("dark_green", "white"),
    "FLW": ("green", "black"),
    "TOA": ("yellow", "black"),  # Tornado watch
    "SVA": ("dark_goldenrod", "black"),  # Severe thunderstorm watch
    "WSW": ("deep_pink4", "white"),  # Winter storm warning
    "WWY": ("purple4", "white"),  # Winter weather advisory
    "BZW": ("red1", "white"),  # Blizzard warning
    "ISW": ("dark_magenta", "white"),  # Ice storm warning
    "HWW": ("dark_goldenrod", "black"),  # High wind warning
    "EHW": ("magenta", "white"),  # Excessive heat warning
    "SPC_TOR": ("red", "white"),  # SPC Tornado watch
    "SPC_SVR": ("yellow", "black"),  # SPC Severe watch
}

TICKER_FG_COLORS: dict[str, str] = {
    "TOR": "red",
    "SVR": "orange1",
    "FFW": "green",
    "FLW": "dark_green",
    "TOA": "yellow",
    "SVA": "dark_goldenrod",
    "WSW": "deep_pink3",
    "WWY": "medium_purple1",
    "BZW": "red1",
    "ISW": "magenta",
    "HWW": "dark_goldenrod",
    "EHW": "magenta",
    "SPC_TOR": "red",
    "SPC_SVR": "yellow",
}

TICKER_DEFAULT_BG = "blue"
TICKER_DEFAULT_FG = "cyan"


# =============================================================================
# Helper Functions
# =============================================================================


def get_alert_css_class(event: str) -> str | None:
    """Get CSS class for alert based on event type.

    Uses NWS-standard colors for each specific alert type.
    Falls back to generic warning/watch/advisory colors for unknown types.

    Args:
        event: Event name from NWS API (e.g., "Tornado Warning")

    Returns:
        CSS class name (e.g., "alert-tor") or None if no special styling
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
    elif "blizzard" in event_lower:
        return "alert-bzw"
    elif "ice storm" in event_lower:
        return "alert-isw"
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


def get_wfo_css_class(product_type: str) -> str | None:
    """Get CSS class for WFO product type.

    Args:
        product_type: Product type code (e.g., "TOR", "SVR")

    Returns:
        CSS class name (e.g., "wfo-warn-tor") or None if no special styling
    """
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


def get_md_css_class(watch_prob: int | None) -> str | None:
    """Get CSS class based on MD watch probability.

    Args:
        watch_prob: Watch probability percentage (0-100)

    Returns:
        CSS class name or None if low probability
    """
    if watch_prob is None:
        return None
    if watch_prob >= 80:
        return "md-prob-likely"
    if watch_prob >= 60:
        return "md-prob-high"
    if watch_prob >= 20:
        return "md-prob-med"
    return None  # Low probability, no highlighting


def get_map_color(event: str) -> str:
    """Get the map fill color for an alert based on event type.

    Uses Rich color names for Braille rendering.

    Args:
        event: Event name from NWS API

    Returns:
        Rich color name (e.g., "bright_red")
    """
    css_class = get_alert_css_class(event)
    if css_class is None:
        return "bright_red"  # Default

    # Strip "alert-" prefix to get key
    key = css_class.replace("alert-", "")
    if key in ALERT_COLORS:
        return ALERT_COLORS[key].bg_rich

    return "bright_red"  # Default


def get_ticker_colors(event_code: str) -> tuple[tuple[str, str], str]:
    """Get ticker colors for an event code.

    Args:
        event_code: Short event code (e.g., "TOR", "SVR")

    Returns:
        Tuple of (bg_colors, fg_color) where bg_colors is (bg, text)
    """
    bg = TICKER_BG_COLORS.get(event_code, (TICKER_DEFAULT_BG, "white"))
    fg = TICKER_FG_COLORS.get(event_code, TICKER_DEFAULT_FG)
    return bg, fg


# =============================================================================
# CSS Generation
# =============================================================================


def _generate_css_block(selector: str, color: EventColor) -> str:
    """Generate CSS for a single color class with hover state."""
    return f"""    Sidebar ListItem.{selector} {{
        background: {color.bg_hex};
        color: {color.fg_hex};
    }}
    Sidebar ListItem.{selector}:hover {{
        background: {color.hover_hex};
    }}"""


def generate_sidebar_css() -> str:
    """Generate all sidebar CSS from color registry.

    Returns:
        Complete CSS string for all alert/watch/outlook colors
    """
    sections = []

    # Watch severity colors
    sections.append("    /* Watch severity colors (NWS standard) */")
    for key, color in WATCH_COLORS.items():
        sections.append(_generate_css_block(key, color))

    # Outlook risk level colors
    sections.append("\n    /* Outlook risk level colors (NWS/SPC standard) */")
    for key, color in OUTLOOK_COLORS.items():
        sections.append(_generate_css_block(key, color))

    # MD watch probability colors
    sections.append("\n    /* MD watch probability colors */")
    for key, color in MD_PROB_COLORS.items():
        sections.append(_generate_css_block(key, color))

    # WFO product type colors
    sections.append("\n    /* WFO product type colors */")
    for key, color in WFO_COLORS.items():
        sections.append(_generate_css_block(key, color))

    # Alert colors
    sections.append("\n    /* Alert colors (NWS standard per-event colors) */")
    for key, color in ALERT_COLORS.items():
        sections.append(_generate_css_block(f"alert-{key}", color))

    return "\n".join(sections)
