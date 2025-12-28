"""Widget for displaying zone maps using Braille rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from rich.text import Text
from textual.widgets import Static


# Braille dot encoding: each char is 2 wide x 4 tall dots
# Dot positions and their bit values:
#   1 4  ->  0x01 0x08
#   2 5  ->  0x02 0x10
#   3 6  ->  0x04 0x20
#   7 8  ->  0x40 0x80
BRAILLE_OFFSET = 0x2800
PIXEL_MAP = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)


@dataclass
class Polygon:
    """A polygon with coordinates and styling."""

    coordinates: list[tuple[float, float]]  # [(lon, lat), ...]
    fill_color: str = "white"
    outline_color: str | None = None
    label: str = ""


# Major US cities for reference on maps (lon, lat, name)
# Subset of state capitals and major metros for key weather regions
MAJOR_CITIES: list[tuple[float, float, str]] = [
    # Plains/Tornado Alley
    (-97.5164, 35.4676, "OKC"),
    (-95.9928, 36.1540, "Tulsa"),
    (-97.3308, 32.7555, "DFW"),
    (-96.7970, 32.7767, "Dallas"),
    (-95.3698, 29.7604, "Houston"),
    (-98.4936, 29.4241, "SAT"),
    (-97.7431, 30.2672, "Austin"),
    (-101.8313, 35.2220, "AMA"),
    (-94.5786, 39.0997, "KC"),
    (-90.1994, 38.6270, "STL"),
    (-89.6501, 39.7817, "SPI"),
    (-93.6250, 41.5868, "DSM"),
    (-96.7898, 43.5460, "FSD"),
    (-100.7837, 46.8083, "BIS"),
    (-96.8005, 46.8772, "FAR"),
    (-97.4395, 35.2226, "Norman"),
    # Southeast
    (-84.3880, 33.7490, "ATL"),
    (-86.7816, 36.1627, "BNA"),
    (-90.0490, 35.1495, "MEM"),
    (-86.8025, 33.5207, "BHM"),
    (-81.6557, 30.3322, "JAX"),
    (-80.1918, 25.7617, "MIA"),
    (-82.4572, 27.9506, "TPA"),
    (-81.3792, 28.5383, "ORL"),
    (-78.6382, 35.7796, "RDU"),
    (-80.8431, 35.2271, "CLT"),
    (-79.9311, 32.7765, "CHS"),
    (-84.2807, 30.4383, "TLH"),
    (-88.0399, 30.6954, "MOB"),
    (-90.0715, 29.9511, "MSY"),
    (-91.1871, 30.4515, "BTR"),
    # Midwest
    (-87.6298, 41.8781, "ORD"),
    (-83.0458, 42.3314, "DTW"),
    (-81.6944, 41.4993, "CLE"),
    (-84.5120, 39.1031, "CVG"),
    (-85.7585, 38.2527, "SDF"),
    (-86.1581, 39.7684, "IND"),
    (-89.4012, 43.0731, "MSN"),
    (-87.9065, 43.0389, "MKE"),
    (-93.2650, 44.9778, "MSP"),
    # Northeast
    (-73.9857, 40.7484, "NYC"),
    (-71.0589, 42.3601, "BOS"),
    (-75.1652, 39.9526, "PHL"),
    (-76.6122, 39.2904, "BWI"),
    (-77.0369, 38.9072, "DCA"),
    (-79.9959, 40.4406, "PIT"),
    # Mountain/West
    (-104.9903, 39.7392, "DEN"),
    (-105.2705, 40.0150, "Boulder"),
    (-104.8214, 38.8339, "COS"),
    (-111.8910, 40.7608, "SLC"),
    (-106.6504, 35.0844, "ABQ"),
    (-110.9265, 32.2226, "TUS"),
    (-112.0740, 33.4484, "PHX"),
    (-115.1398, 36.1699, "LAS"),
    # Pacific
    (-122.4194, 37.7749, "SFO"),
    (-118.2437, 34.0522, "LAX"),
    (-117.1611, 32.7157, "SAN"),
    (-121.4944, 38.5816, "SAC"),
    (-122.3321, 47.6062, "SEA"),
    (-122.6765, 45.5152, "PDX"),
]


@dataclass
class BrailleCanvas:
    """A canvas for rendering polygons as Braille characters."""

    width: int = 60  # Character width
    height: int = 25  # Character height
    _pixels: dict[tuple[int, int], int] = field(default_factory=dict, repr=False)
    _pixel_colors: dict[tuple[int, int], tuple[str, int]] = field(default_factory=dict, repr=False)  # (color, priority)

    @property
    def pixel_width(self) -> int:
        """Pixel width (2x character width)."""
        return self.width * 2

    @property
    def pixel_height(self) -> int:
        """Pixel height (4x character height)."""
        return self.height * 4

    def clear(self) -> None:
        """Clear the canvas."""
        self._pixels.clear()
        self._pixel_colors.clear()

    def set_pixel(self, x: int, y: int, color: str = "white", priority: int = 0) -> None:
        """Set a pixel at the given coordinates.

        Args:
            x: X coordinate (pixel)
            y: Y coordinate (pixel)
            color: Rich color name
            priority: Higher priority colors override lower (default 0 for fills, 10 for markers)
        """
        if 0 <= x < self.pixel_width and 0 <= y < self.pixel_height:
            col, row = x // 2, y // 4
            self._pixels.setdefault((row, col), 0)
            self._pixels[(row, col)] |= PIXEL_MAP[y % 4][x % 2]
            # Only update color if new priority is >= existing
            existing = self._pixel_colors.get((x, y))
            if existing is None or priority >= existing[1]:
                self._pixel_colors[(x, y)] = (color, priority)

    def _point_in_polygon(
        self, x: float, y: float, polygon: list[tuple[float, float]]
    ) -> bool:
        """Ray casting algorithm for point-in-polygon test."""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi) + xi
            ):
                inside = not inside
            j = i
        return inside

    def draw_polygon(
        self,
        coords: list[tuple[float, float]],
        bounds: tuple[float, float, float, float],
        color: str = "white",
    ) -> None:
        """Draw a filled polygon on the canvas.

        Args:
            coords: List of (lon, lat) coordinates
            bounds: (min_lon, min_lat, max_lon, max_lat) for the viewport
            color: Rich color name for the polygon
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat

        if lon_range == 0 or lat_range == 0:
            return

        scale_x = lon_range / self.pixel_width
        scale_y = lat_range / self.pixel_height

        # Calculate polygon bounding box in pixel coordinates for optimization
        poly_lons = [c[0] for c in coords]
        poly_lats = [c[1] for c in coords]
        poly_min_lon, poly_max_lon = min(poly_lons), max(poly_lons)
        poly_min_lat, poly_max_lat = min(poly_lats), max(poly_lats)

        # Convert to pixel bounds (with 1px padding for rounding)
        px_min = max(0, int((poly_min_lon - min_lon) / scale_x) - 1)
        px_max = min(self.pixel_width, int((poly_max_lon - min_lon) / scale_x) + 2)
        py_min = max(0, int((max_lat - poly_max_lat) / scale_y) - 1)
        py_max = min(self.pixel_height, int((max_lat - poly_min_lat) / scale_y) + 2)

        # Only test pixels within polygon's bounding box
        for py in range(py_min, py_max):
            for px in range(px_min, px_max):
                lon = min_lon + px * scale_x
                lat = max_lat - py * scale_y  # Y inverted for screen coords
                if self._point_in_polygon(lon, lat, coords):
                    self.set_pixel(px, py, color)

    def draw_polygon_outline(
        self,
        coords: list[tuple[float, float]],
        bounds: tuple[float, float, float, float],
        color: str = "white",
    ) -> None:
        """Draw a polygon outline using Bresenham's line algorithm.

        Args:
            coords: List of (lon, lat) coordinates
            bounds: (min_lon, min_lat, max_lon, max_lat) for the viewport
            color: Rich color name for the outline
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        scale_x = self.pixel_width / (max_lon - min_lon)
        scale_y = self.pixel_height / (max_lat - min_lat)

        def to_pixel(lon: float, lat: float) -> tuple[int, int]:
            px = int((lon - min_lon) * scale_x)
            py = int((max_lat - lat) * scale_y)
            return px, py

        for i in range(len(coords)):
            x0, y0 = to_pixel(*coords[i])
            x1, y1 = to_pixel(*coords[(i + 1) % len(coords)])
            self._draw_line(x0, y0, x1, y1, color)

    def _draw_line(
        self, x0: int, y0: int, x1: int, y1: int, color: str = "white"
    ) -> None:
        """Draw a line using Bresenham's algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_marker(
        self,
        lon: float,
        lat: float,
        bounds: tuple[float, float, float, float],
        color: str = "bright_white",
    ) -> bool:
        """Draw a small cross marker at a geographic location.

        Args:
            lon: Longitude
            lat: Latitude
            bounds: (min_lon, min_lat, max_lon, max_lat) for the viewport
            color: Rich color name for the marker

        Returns:
            True if marker was drawn (within bounds), False otherwise.
        """
        min_lon, min_lat, max_lon, max_lat = bounds

        # Check if point is within bounds
        if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
            return False

        # Convert to pixel coordinates
        scale_x = self.pixel_width / (max_lon - min_lon)
        scale_y = self.pixel_height / (max_lat - min_lat)
        px = int((lon - min_lon) * scale_x)
        py = int((max_lat - lat) * scale_y)

        # Draw a small 3x3 cross pattern with high priority (10) to override fills
        self.set_pixel(px, py, color, priority=10)
        self.set_pixel(px - 1, py, color, priority=10)
        self.set_pixel(px + 1, py, color, priority=10)
        self.set_pixel(px, py - 1, color, priority=10)
        self.set_pixel(px, py + 1, color, priority=10)
        return True

    def _get_cell_color(self, row: int, col: int) -> str:
        """Get the dominant color for a character cell.

        Priority-based: if any pixel has a higher priority, that color wins.
        Among equal priorities, most common color wins.
        """
        # Collect colors and priorities of all pixels in this cell
        max_priority = -1
        colors_at_max: dict[str, int] = {}

        for dy in range(4):
            for dx in range(2):
                px, py = col * 2 + dx, row * 4 + dy
                if (px, py) in self._pixel_colors:
                    color, priority = self._pixel_colors[(px, py)]
                    if priority > max_priority:
                        # New highest priority - reset color counts
                        max_priority = priority
                        colors_at_max = {color: 1}
                    elif priority == max_priority:
                        colors_at_max[color] = colors_at_max.get(color, 0) + 1

        if not colors_at_max:
            return "white"

        # Return the most common color at the highest priority level
        return max(colors_at_max, key=lambda c: colors_at_max[c])

    def render(self) -> Text:
        """Render the canvas as Rich Text with colors."""
        text = Text()
        for row in range(self.height):
            if row > 0:
                text.append("\n")
            for col in range(self.width):
                bits = self._pixels.get((row, col), 0)
                char = chr(BRAILLE_OFFSET + bits)
                color = self._get_cell_color(row, col)
                text.append(char, style=color)
        return text

    def render_plain(self) -> str:
        """Render the canvas as plain text (no colors)."""
        lines = []
        for row in range(self.height):
            line = ""
            for col in range(self.width):
                bits = self._pixels.get((row, col), 0)
                line += chr(BRAILLE_OFFSET + bits)
            lines.append(line.rstrip())
        return "\n".join(lines)


def calculate_bounds(
    polygons: Sequence[list[tuple[float, float]]], padding: float = 0.1
) -> tuple[float, float, float, float]:
    """Calculate bounding box for a list of polygons with padding.

    Args:
        polygons: List of polygon coordinate lists
        padding: Fractional padding to add (0.1 = 10%)

    Returns:
        (min_lon, min_lat, max_lon, max_lat)
    """
    all_lons = [lon for poly in polygons for lon, lat in poly]
    all_lats = [lat for poly in polygons for lon, lat in poly]

    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)

    # Add padding
    pad_lon = (max_lon - min_lon) * padding
    pad_lat = (max_lat - min_lat) * padding

    return (min_lon - pad_lon, min_lat - pad_lat, max_lon + pad_lon, max_lat + pad_lat)


class ZoneMap(Static):
    """A widget that displays zone polygons as a Braille map."""

    DEFAULT_CSS = """
    ZoneMap {
        height: auto;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(
        self,
        width: int = 60,
        height: int = 20,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._canvas = BrailleCanvas(width=width, height=height)
        # Polygons: (coords, color, outline_only)
        self._polygons: list[tuple[list[tuple[float, float]], str, bool]] = []
        self._bounds: tuple[float, float, float, float] | None = None
        self._title: str = ""
        self._show_cities: bool = True  # Show city reference markers

    def clear(self) -> None:
        """Clear all polygons from the map."""
        self._polygons.clear()
        self._bounds = None
        self._canvas.clear()
        self.update("")

    def set_title(self, title: str) -> None:
        """Set a title to display above the map."""
        self._title = title
        self._render_map()

    def add_polygon(
        self,
        coordinates: list[tuple[float, float]],
        color: str = "bright_white",
        outline_only: bool = False,
    ) -> None:
        """Add a polygon to the map.

        Args:
            coordinates: List of (lon, lat) coordinate pairs
            color: Rich color name for the polygon
            outline_only: If True, only draw outline (no fill)
        """
        self._polygons.append((coordinates, color, outline_only))

    def render_map(self) -> None:
        """Render all polygons to the map."""
        self._render_map()

    def _render_map(self) -> None:
        """Internal render method."""
        if not self._polygons:
            self.update("No zones to display")
            return

        self._canvas.clear()

        # Calculate bounds if not set
        if self._bounds is None:
            self._bounds = calculate_bounds([p[0] for p in self._polygons])

        # Draw all polygons (outlines first, then fills, so fills are on top)
        # First pass: outlines only
        for coords, color, outline_only in self._polygons:
            if outline_only:
                self._canvas.draw_polygon_outline(coords, self._bounds, color)

        # Second pass: filled polygons
        for coords, color, outline_only in self._polygons:
            if not outline_only:
                self._canvas.draw_polygon(coords, self._bounds, color)

        # Third pass: city markers (drawn on top)
        visible_cities: list[str] = []
        if self._show_cities and self._bounds:
            for lon, lat, name in MAJOR_CITIES:
                if self._canvas.draw_marker(lon, lat, self._bounds, color="cyan"):
                    visible_cities.append(name)

        # Build output
        text = Text()
        if self._title:
            text.append(self._title, style="bold")
            text.append("\n\n")
        text.append_text(self._canvas.render())

        # Add city legend if we have visible cities
        if visible_cities:
            text.append("\n")
            text.append("Cities: ", style="dim")
            text.append(", ".join(visible_cities[:8]), style="cyan")  # Limit to 8 cities
            if len(visible_cities) > 8:
                text.append(f" +{len(visible_cities) - 8} more", style="dim")

        self.update(text)

    def set_bounds(
        self, min_lon: float, min_lat: float, max_lon: float, max_lat: float
    ) -> None:
        """Manually set the viewport bounds."""
        self._bounds = (min_lon, min_lat, max_lon, max_lat)
