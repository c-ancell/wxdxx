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


@dataclass
class BrailleCanvas:
    """A canvas for rendering polygons as Braille characters."""

    width: int = 60  # Character width
    height: int = 25  # Character height
    _pixels: dict[tuple[int, int], int] = field(default_factory=dict, repr=False)
    _pixel_colors: dict[tuple[int, int], str] = field(default_factory=dict, repr=False)

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

    def set_pixel(self, x: int, y: int, color: str = "white") -> None:
        """Set a pixel at the given coordinates."""
        if 0 <= x < self.pixel_width and 0 <= y < self.pixel_height:
            col, row = x // 2, y // 4
            self._pixels.setdefault((row, col), 0)
            self._pixels[(row, col)] |= PIXEL_MAP[y % 4][x % 2]
            # Store per-pixel color for better color blending
            self._pixel_colors[(x, y)] = color

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
        scale_x = (max_lon - min_lon) / self.pixel_width
        scale_y = (max_lat - min_lat) / self.pixel_height

        for py in range(self.pixel_height):
            for px in range(self.pixel_width):
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

    def _get_cell_color(self, row: int, col: int) -> str:
        """Get the dominant color for a character cell."""
        # Collect colors of all pixels in this cell
        colors: dict[str, int] = {}
        for dy in range(4):
            for dx in range(2):
                px, py = col * 2 + dx, row * 4 + dy
                if (px, py) in self._pixel_colors:
                    c = self._pixel_colors[(px, py)]
                    colors[c] = colors.get(c, 0) + 1

        if not colors:
            return "white"

        # Return the most common color
        return max(colors, key=lambda c: colors[c])

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
        self._polygons: list[tuple[list[tuple[float, float]], str]] = []
        self._bounds: tuple[float, float, float, float] | None = None
        self._title: str = ""

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
    ) -> None:
        """Add a polygon to the map.

        Args:
            coordinates: List of (lon, lat) coordinate pairs
            color: Rich color name for the polygon fill
        """
        self._polygons.append((coordinates, color))

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

        # Draw all polygons
        for coords, color in self._polygons:
            self._canvas.draw_polygon(coords, self._bounds, color)

        # Build output
        text = Text()
        if self._title:
            text.append(self._title, style="bold")
            text.append("\n\n")
        text.append_text(self._canvas.render())

        self.update(text)

    def set_bounds(
        self, min_lon: float, min_lat: float, max_lon: float, max_lat: float
    ) -> None:
        """Manually set the viewport bounds."""
        self._bounds = (min_lon, min_lat, max_lon, max_lat)
