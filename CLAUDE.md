# WxDXX

A TUI application for viewing NWS text products from SPC, WPC, NHC, and local WFOs.

## Tech Stack
- Python 3.11+ with Textual (TUI framework)
- httpx for async HTTP requests
- Pydantic for data models

## Project Structure
```
src/wxdxx/
├── app.py              # Main Textual application, ClockWidget
├── cache.py            # TTL-based in-memory cache
├── config.py           # Configuration model and persistence (TOML)
├── api/
│   ├── spc.py          # SPC website scraper (HTML parsing)
│   └── nws.py          # NWS API client (api.weather.gov)
├── models/             # Pydantic models (outlook, md, watch, wfo)
├── widgets/
│   ├── sidebar.py      # Navigation sidebar with categories
│   ├── product_view.py # Scrollable content display
│   ├── news_ticker.py  # Scrolling nationwide alerts ticker
│   ├── help_screen.py  # Help modal with keyboard shortcuts
│   ├── settings_screen.py # Settings modal for app configuration
│   ├── wfo_input.py    # WFO add/remove dialog
│   └── zone_map.py     # Braille-rendered zone maps (BrailleCanvas, ZoneMap)
└── screens/            # Screen stubs (not fully implemented)
```

## API Notes
- SPC: Scrapes HTML from spc.noaa.gov (no official API)
- NWS: Uses api.weather.gov with generous rate limits for typical usage
- Both clients set proper User-Agent headers

## Running the App
```bash
source .venv/bin/activate
.venv/bin/pip install .   # Required after code changes (editable install broken on Python 3.14)
.venv/bin/wxdxx
```

## Development Workflow

### Branching Strategy
- Work directly on `main` for small changes (single file, minor fixes, documentation)
- Create a feature branch from `main` when:
  - The change requires significant modification of a file
  - The change touches 3 or more files
  - The feature is experimental or might break existing functionality
- Branch naming: `feature/short-description` or `fix/short-description`

### Testing
Run tests with:
```bash
.venv/bin/pytest tests/ -v
```

**Test structure:**
- `tests/test_app_smoke.py` - Smoke tests verifying the app starts and core widgets render
- `tests/test_spc_parser.py` - Unit tests for SPC HTML parsing (uses fixtures)
- `tests/fixtures/` - Sample HTML files for parser testing

**Testing philosophy:**
- Add tests incrementally as we work on the project
- Prioritize tests for fragile code (HTML scrapers, external API parsing)
- Smoke tests catch regressions in app startup and widget composition
- When modifying parser code, add or update corresponding fixture tests

### TODO Tracking
When the user asks to add a TODO, always add it to the "TODO / Not Yet Implemented" section in this file. You may also add inline `# TODO:` comments in the code if it helps with context, but this file is the canonical source for tracking all TODOs.

### Versioning
We use [Semantic Versioning](https://semver.org/) with git tags. Version is stored in `pyproject.toml` and read at runtime.

**When to tag a new version:**
- **Patch (0.1.x)**: Bug fixes, parser updates for API changes, documentation updates
- **Minor (0.x.0)**: New features (new product types, new UI elements, new hotkeys), non-breaking changes
- **Major (x.0.0)**: Breaking changes, major UI overhauls - always discuss with user first

**Tagging workflow:**
1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` with new section
3. Commit: `git commit -m "Bump version to vX.Y.Z"`
4. Tag: `git tag -a vX.Y.Z -m "Release description"`

**Guidelines for Claude:**
- Proactively suggest a version bump after completing significant features or bug fixes
- Batch multiple small changes into a single version bump when reasonable - suggest tagging every 3-4 commits or when pivoting to new work
- For alpha (0.x.y), be liberal with minor bumps for new features
- Never bump to 1.0.0 without explicit user approval

### Development Notes

**Textual gotchas:**
- `DOMQuery` objects are truthy even when empty; use `len(list(query(...))) == 0` to check for no results
- Status bar indicators (like "Refreshing...") need forced updates via `_update_clock_display()` when state changes - the 1-second polling interval is too slow to catch fast operations
- `set_interval` timers don't fire reliably from App context; use async worker loop pattern instead (see `_auto_refresh_loop()` in app.py)
- When starting background tasks in `on_mount`, use `call_later()` to defer `run_worker()` calls until after mount completes

**SPC/NWS parsing gotchas:**
- Always deduplicate when parsing HTML link lists with `re.findall()` - pages often have multiple links to the same product (header, table, sidebar, etc.). Use `set()` before returning.
- The `_is_refreshing` flag now guards against concurrent refreshes - check it at the start of `_refresh_all_data_with_indicator()`
- UGC expiry parsing: Don't assume future month rollover when expiry day < current day - the product may just be expired. Only roll back to previous month when current day is 1-2 and expiry day is 28-31.
- NWS API `message_type=alert` filter: Don't use this when querying `/alerts/active` - it excludes "Update" messages, which is what most active alerts have (re-issued alerts). This caused WFO sidebar alerts to be empty while ticker showed alerts.
- UTC display with "Z" suffix: Always convert to UTC with `.astimezone(timezone.utc)` before formatting. Just appending "Z" to `strftime()` output shows the datetime's original timezone, not UTC - e.g., midnight PST displays as "0000Z" but is actually 0800 UTC.
- Expiry filtering for cached data: Filter at multiple points (API fetch, headline building, periodic timer, display) since cached data can become stale between refreshes.

**ProductCache architecture (cache.py):**
- Unified cache replaced 10 separate TTLCache instances. Single `self._cache` in app.py.
- Key format: `{source}:{category}:{identifier}` (e.g., `spc:md:2462`, `nws:list:OUN:AFD`)
- Sources: `spc`, `nws` (future: `wpc`, `nhc`)
- Categories: `outlook`, `md`, `watch`, `alert`, `product`, `zone`, `list`, `ticker`
- Use type-safe helpers: `get_md(num)`, `set_outlook(day, obj)`, `get_wfo_product_list(wfo, type)`, etc.
- Empty content detection: Products with `content_text` < 100 chars get 30s TTL (vs normal category TTL)
- Targeted invalidation: `invalidate_by_source("spc")`, `invalidate_by_pattern(source="nws", category="list")`
- Zone cache intentionally NOT cleared on refresh (24hr TTL, zones rarely change)
- `get_empty_products()` returns keys for empty content - useful for future fast-polling feature

## Current Features
- Convective Outlooks (Day 1-3) fetched from SPC
- Mesoscale Discussions - listed in sidebar, click to view full text
- Watches - listed in sidebar, click to view full text
- UTC and local clocks in status bar with day number (e.g., "UTC: 25 14:32 | Local: 25 08:32")
- Time since issuance shown in status bar (minute resolution)
- Outlook validity shown as date range (e.g., "Valid: 251200Z - 261200Z")
- MDs and Watches show countdown to expiry (e.g., "Expires: in 2h 15m")
- Expired products (MDs, Watches) are automatically filtered from the sidebar
- Keyboard: q=quit, r=refresh, s=settings, 1/2/3=Day 1/2/3 outlooks, ?=help, Tab=switch panel, M=mark all read
- Scrolling in content view: j/k=line up/down, d/u=page down/up, g/G=top/bottom, arrows also work
- Help screen (?) shows all keyboard shortcuts
- Settings screen (s) for configuring refresh interval
- Auto-refresh with configurable interval (default 60 seconds), "Refreshing..." indicator in status bar
- WFO loading indicator in status bar shows which WFOs are being fetched
- Tracked WFOs persist across app restarts (stored in ~/.config/wxdxx/config.toml)
- TTL-based in-memory caching for all data (outlooks 5min, lists 2min, details 10-30min)
- Auto-refresh uses cached data if not expired; manual refresh (r) clears all caches
- Outlook status bar shows "Next: in Xh Ym" for when the next outlook is scheduled
- Sidebar items color-coded using NWS conventions: red for tornado watches, yellow for SVR, magenta for PDS; outlook risk levels (TSTM→HIGH); MD watch probability; WFO warnings (TOR/SVR/FFW/WSW)
- Sidebar shows time-until-expiry for MDs and Watches (e.g., "MD 2457 (2h 15m)", "TOR 127 (4h 30m)")
- Status bar shows "Refreshed: Xm ago" timestamp that updates dynamically
- WFO Active Alerts: Hazard alerts (warnings, watches, advisories) fetched by forecast zone and displayed alongside text products with NWS color coding and expiry countdowns
- SPS Expiry Filtering: Special Weather Statements parsed for UGC header expiry times; expired SPS products automatically filtered from sidebar with countdown display
- Unread indicators: New/updated products show a filled circle (●) in sidebar; circle disappears when product is viewed. Dark circle for highlighted items, light circle for regular items.
- News Ticker: Scrolling bar below header showing nationwide NWS warnings and SPC watches. Headlines colored by event type (TOR=red, SVR=yellow, etc.). New alerts (appearing after startup) flash for first scroll cycle, solid background for second cycle, then text color only. Headlines at startup display as regular (no flash). Headlines sorted by severity (TOR > SVR > FFW > watches). Expired alerts are automatically filtered out on each scroll cycle.
- METAR Lookup: Press 'O' to look up current weather observations by ICAO station code (e.g., KORD, KDFW). Shows temperature, wind, visibility, humidity, pressure, and raw METAR text.
- Alert Nearby Stations: When viewing an alert, nearby weather stations from affected zones are displayed at the bottom showing current conditions.

## TODO / Not Yet Implemented

### Small enhancements
- ~~Zone map: Color affected zones to match alert color~~: ✅ Done - Zones now colored by event type (TOR=red, SVR=yellow, etc.)
- ~~Zone map: Render major cities as reference points~~: ✅ Done - Major US cities shown as cyan markers with legend
- ~~News ticker: Alert updates should display "UPDATE" instead of "NEW"~~: ✅ Done - Updates now show "UPDATE" prefix
- ~~Nearby stations in alerts should list in order of importance~~: ✅ Done - Major airports prioritized over regional stations
- METAR lookup: Show expanded station name with city/state (e.g., "Austin Bergstrom International Airport - Austin, TX")

### Bugs
- Alert sidebar click shows "Error try refreshing": Sometimes an alert appears in sidebar and clicking on it shows an error message. Normally a refresh works, but a recent occurrence crashed the UI. Needs investigation.
- ~~Sidebar 'g' and 'G' hotkeys not working~~: ✅ Fixed - Added action_first and action_last methods to VimListView

### Larger effort
- Make sidebar sections collapsible
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)
- Add "R" (SHIFT+r) for hard refresh: Currently 'r' clears all caches and refreshes. Consider making 'r' a soft refresh (use cached data if valid) and 'R' a hard refresh (clear all caches first). This would make auto-refresh and 'r' behave the same way.
- ~~METAR support~~: ✅ Done - Added METAR lookup (O hotkey) and nearby stations display in alerts
- AFD trend analysis: Track AFD content across issuances to detect changes in forecast confidence for major weather events. Flag increasing/decreasing confidence, highlight surprises vs long-range expectations, and alert users to "things to keep an eye on."

### Epic: Data Source Stewardship
Findings from spike research on SPC/NWS API best practices. SPC robots.txt has 10-second crawl-delay (targets search crawlers, not interactive apps). NWS API requires User-Agent with contact info and has generous rate limits with retry-after-5s on throttle.

1. ~~**User-Agent with contact info**~~: ✅ Done - Updated to `WxDXX/0.1.0 (https://github.com/c-ancell/wxdxx, wxdxxapp@gmail.com)` in both api/spc.py and api/nws.py.

2. ~~**Retry with exponential backoff**~~: ✅ Done - Added retry logic (1s, 2s, 4s backoff, max 3 retries) in `_get()` methods. Retries on transport errors, timeouts, 5xx errors, and 429 rate limits.

3. ~~**Conditional requests (ETag/If-Modified-Since)**~~: ❌ Not feasible - Investigated 2025-12-27. Neither SPC nor NWS return `ETag` or `Last-Modified` headers, so conditional requests won't work. They do return `Cache-Control` with `max-age` (SPC: 120s, NWS alerts: 30s, NWS products: 120s), which our TTL-based caching already approximates.

4. ~~**Request rate limiting**~~: ✅ Done - Added async semaphores to limit concurrent requests (SPC: 3, NWS: 8). See `_get()` wrapper methods in api/spc.py and api/nws.py.

5. ~~**Smart cache invalidation**~~: ✅ Done - Implemented unified `ProductCache` in cache.py with structured keys (`source:category:identifier`), targeted invalidation (`invalidate_by_source`, `invalidate_by_pattern`), content state tracking (empty detection), and staleness tracking. Replaced 10 separate TTLCache instances with single ProductCache. See cache.py for implementation.

### Epic: Text-Based Reference Maps
Display geographic context for warnings, watches, MDs, and WFO coverage areas using ASCII/text rendering in the TUI.

**Use cases:**
1. Warning context - See which counties/zones are affected ("where is this happening?")
2. WFO coverage - Understand which WFO covers which area
3. MD/Watch areas - Visualize geographic extent of SPC products

**NWS data sources identified:**
- GeoJSON geometry in api.weather.gov alert responses
- Public Forecast Zone shapefiles: https://www.weather.gov/gis/PublicZones
- Zone-County correlation: https://www.weather.gov/gis/ZoneCounty
- CWA (County Warning Area) boundaries for WFO coverage

**Open questions:**
1. ~~Resolution vs. complexity - State-level (feasible) vs. county/zone-level (3000+ polygons)?~~ **Answered:** Regional zoom makes county-level viable. Full US = state-level only (160×100 px, ~5px/county). Regional zoom to affected area (e.g., 20-60 counties in 120×80 px) = 160-480 px/county, enough for recognizable shapes. Approach: auto-zoom viewport to bounding box of affected zones.
2. ~~Static vs. dynamic - Pre-made ASCII templates vs. runtime GeoJSON→ASCII conversion?~~ **Answered (2025-12-27):** Dynamic is recommended for regional/county maps.

   **Static templates:**
   - Pros: Simple (~50 lines), no deps, instant render, works with Rich styling
   - Cons: Fixed resolution, state-level only, requires manual maintenance, limited accuracy
   - Best for: Quick "which states affected?" overview if we want one

   **Dynamic GeoJSON→Braille:**
   - Pros: Accurate NWS boundaries, auto-zoom to affected area, county-level detail, future-proof
   - Cons: More complex (~150 lines), extra API calls for zone geometry, ~50ms render time
   - Best for: Regional maps showing affected zones with actual boundaries

   **Key discovery:** NWS alerts don't embed geometry - they reference zone URLs. Zone endpoints (`/zones/forecast/{id}`) return full GeoJSON polygons (67-479 points per zone). We already fetch zone data for alerts, so geometry is available at no extra API cost.

   **Recommendation:** Use dynamic rendering for alert/MD/watch maps (regional zoom with county detail). Consider adding a static US overview map for "at a glance" nationwide view, but this is lower priority.
3. Integration - Modal screen, inline in ProductView, or separate panel?
4. ~~Data bundling - Fetch on-demand, bundle simplified boundaries, or cache locally?~~ **Answered:** Fetch on-demand from NWS zone API. Zone geometry (67-479 points) is small enough to fetch per-request. We already fetch zone info for alerts; just need to include geometry. Cache with 24hr TTL (zones rarely change). No bundling needed.

**Spikes to complete before implementation:**

1. ~~**Explore MapSCII rendering approach**~~: ✅ Complete (2025-12-27)

   **How MapSCII works:** Uses Unicode Braille patterns (U+2800-U+28FF) where each character encodes a 2x4 dot matrix (8 dots total). The algorithm:
   - Divide canvas into 2x4 pixel blocks
   - For each block, calculate which of 8 dots are "on"
   - Use bit mapping: `pixel_map = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))`
   - Unicode codepoint = `0x2800 + bits`

   **Python implementation:** The [drawille](https://github.com/asciimoo/drawille) library (AGPL-3.0) already implements this. Simple API: `Canvas.set(x, y)` and `Canvas.frame()` to render. Could use directly or port the ~50 lines of core logic.

   **Resolution achievable:**
   - Each character cell = 2 pixels wide × 4 pixels tall
   - 80-char terminal = 160 pixel width
   - 40-line widget area = 160 pixel height
   - For a US map: 160×160 is roughly enough for state-level detail but not county-level

   **Textual integration:** No built-in Canvas widget, but can render Braille strings via `Static` or custom widget with Rich markup for colors. Tested successfully - Braille renders correctly in macOS Terminal.

   **Compatibility concern:** Some fonts show hollow circles for "off" dots (e.g., GNOME Terminal default). Modern terminals (iTerm2, kitty, macOS Terminal) with good Unicode fonts work well.

   **Conclusion:** Braille rendering is viable for state-level US maps. For our use case (highlighting affected states), 160×100 resolution is sufficient. We can either use drawille directly (adds AGPL dependency) or implement the ~50 lines ourselves.

2. ~~**Inspect NWS alert geometry**~~: ✅ Complete (2025-12-27, covered in static vs dynamic spike)

   **Finding:** Alerts don't embed geometry - they reference zone URLs (e.g., `https://api.weather.gov/zones/forecast/OKZ025`). Zone endpoints return full GeoJSON:
   - Type: Polygon or MultiPolygon
   - Complexity: 67-479 points per zone (tested OK, TX, KS, CO zones)
   - Format: `[[lon, lat], ...]` coordinate arrays
   - We already fetch zones for alert display; just need to request geometry field

3. **Prototype ASCII US map**: Hand-draw a simple US map with state outlines (~40 lines tall). Test rendering in a Textual widget. Can individual states be highlighted legibly with Rich styling?

4. ~~**Evaluate Braille vs. block characters**~~: ✅ Complete (2025-12-27, covered in MapSCII spike)

   Braille is superior: 2×4 dots per char vs 2×2 for block chars. Braille gives 160×160 resolution in 80×40 char area; blocks give 160×80. Both render well in modern terminals. Braille recommended.

5. **UGC-to-state mapping**: We already parse UGC codes from warnings. Build a mapping from zone/county codes to state abbreviations. How complete can we make this without external data?

**Prototype complete (2025-12-27):** `src/wxdxx/widgets/zone_map.py`
- `BrailleCanvas`: Core rendering class (~180 lines)
  - `set_pixel(x, y, color)`: Set individual pixels with color
  - `draw_polygon(coords, bounds, color)`: Fill polygons using ray casting
  - `draw_polygon_outline(coords, bounds, color)`: Draw outlines using Bresenham
  - `render()`: Returns Rich Text with per-character dominant color
- `ZoneMap(Static)`: Textual widget wrapper
  - `add_polygon(coords, color)`: Add zones to render
  - `set_title(title)`: Set map title
  - `render_map()`: Trigger rendering with auto-zoom to bounds
- Tested with real NWS zone geometry (67-615 points/zone)
- Render time: ~50ms for 6 zones at 70x22 chars

**Integration complete (2025-12-27):**
- ✅ `ZoneGeometry` model and `get_zone_geometry()`/`get_zones_geometry()` in NWS client
- ✅ `affected_zones` field added to `WFOAlert` model
- ✅ Zone IDs extracted from alerts during fetch
- ✅ `ZoneMap` widget added to app layout (below ProductView)
- ✅ 'm' keybind toggles map visibility
- ✅ Map renders when viewing alerts with affected zones

**Future enhancements:**
- Add map support for MDs and Watches (need to extract geometry from SPC data)
- Color zones by alert severity (currently all zones rendered in red)
- Add zone labels or legend

### Spikes (Research/Discussion)
(None currently - see Epic sections above for spike items)

### Architecture
- Screens directory contains unused stubs (OutlooksScreen, WatchesScreen, etc.) from early development. The current single-screen architecture with sidebar + ProductView is simpler and works well for this app's scope. Could delete the stubs or revisit if the app grows significantly more complex, but not a priority.

## Architecture Standards & Best Practices

*Established 2025-12-27 during comprehensive codebase review.*

### Overall Assessment

**Current Grade: B+** — Solid foundation with clean domain modeling, excellent caching, and good async patterns. Main weaknesses are code duplication (especially color mapping), inconsistent error handling, and sparse test coverage. Estimated 20-30% of code could be eliminated through better abstraction.

### Code Organization Principles

**1. Single Source of Truth**
- Constants, color mappings, and configuration values should have ONE canonical location
- Currently violated: event-to-color mapping exists in 4+ places (sidebar.py, news_ticker.py, app.py, zone_map.py)

**2. DRY (Don't Repeat Yourself)**
- Extract shared logic into utilities when patterns appear 3+ times
- Currently violated: API client `_get()` methods, sidebar update methods, datetime parsing

**3. Fail Fast, Fail Loudly**
- Prefer exceptions over silent failures or magic return values
- Log all errors (currently: zero logging)

**4. Type Everything**
- All public functions should have type hints
- Use `| None` instead of `Optional[]` (Python 3.10+ style)
- Avoid `Any` except for truly dynamic data

### Standards to Follow

**Error Handling**
```python
# DO: Raise custom exceptions from API layer
class APIError(Exception): pass
class NetworkError(APIError): pass
class DataError(APIError): pass

# DO: Convert to user notifications in app layer
try:
    result = await api.fetch()
except APIError as e:
    self.notify(f"Error: {e}", severity="error")

# DON'T: Return None and check everywhere
result = await api.fetch()  # Returns None on error
if result is None:
    # Easy to forget this check
```

**Return Types**
```python
# DO: Use consistent return patterns
async def get_product(self, id: str) -> Product | None:
    """Returns None if not found, raises APIError on network issues."""

# DON'T: Mix patterns
async def get_product(self, id: str) -> Product:  # Sometimes returns empty Product
async def get_other(self, id: str) -> str:  # Returns "" on error
async def get_third(self, id: str) -> dict | None:  # Returns None on ANY error
```

**Magic Numbers → Constants**
```python
# DO: Use module-level or class constants
class App:
    MIN_REFRESH_DISPLAY_TIME = 2.0  # seconds
    FAST_POLL_INTERVAL = 15  # seconds
    FAST_POLL_MAX_DURATION = 300  # seconds

# DON'T: Inline magic numbers
await asyncio.sleep(2.0)
if elapsed > 300:
```

**Model Consistency**
- All product models should inherit from a `BaseProduct` with common fields
- Use `id` as the standard identifier field name (not `number`, `day`, etc.)
- Computed properties should be `@property` methods, not stored fields

### Refactoring Roadmap

#### Critical (Do Before Adding Features)

**1. Centralize Event Color Mapping**
Create `src/wxdxx/colors.py`:
```python
from enum import Enum

class EventType(Enum):
    TORNADO_WARNING = "tor"
    SEVERE_THUNDERSTORM_WARNING = "svr"
    # ...

EVENT_COLORS = {
    EventType.TORNADO_WARNING: {"bg": "#ff0000", "fg": "#ffffff"},
    # ...
}

def get_event_color(event_code: str) -> tuple[str, str]:
    """Returns (background, foreground) color for event type."""
```
This eliminates 400+ lines of duplicate CSS and 4 separate mapping functions.

**2. Consolidate API Client Base**
Create `src/wxdxx/api/base.py`:
```python
class BaseAPIClient:
    def __init__(self, base_url: str, max_concurrent: int):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client = httpx.AsyncClient(...)

    async def _get(self, url: str) -> httpx.Response:
        """Shared retry/backoff logic."""
```
SPC and NWS clients inherit from this.

**3. Add Logging**
```python
import logging
logger = logging.getLogger(__name__)

# At module level in each file
logger.debug("Fetching MD %s", md_number)
logger.error("Failed to parse response", exc_info=True)
```

#### High Priority

**4. ~~Extract BaseProduct Model~~**: ✅ Done - Created `models/base.py` with `BaseProduct(BaseModel)` containing `issued: datetime | None` and abstract `title` property. All product models (MesoscaleDiscussion, Watch, ConvectiveOutlook, WFOProduct, WFOAlert) now inherit from it. Kept minimal (no forced `id` or `text` fields) since models have varying identifier types and WFOAlert computes text dynamically.

**5. Refactor Sidebar Update Methods**
Extract generic `_update_category(category: str, items: list, item_builder: Callable)`.

**6. Add Cache Unit Tests**
ProductCache has complex logic (LRU eviction, pattern invalidation, TTL) but zero tests.

**7. Enable mypy**
Add to CI/pre-commit. Start with `--ignore-missing-imports` and tighten over time.

#### Medium Priority

**8. Extract Datetime Parsing Utilities**
Create `src/wxdxx/utils/datetime.py` for:
- `parse_local_timestamp()`
- `parse_zulu_time()`
- `parse_ugc_expiry()`
- `format_countdown()`

**9. Generate CSS from Color Registry**
Instead of 400 lines of hand-written CSS, generate from `EVENT_COLORS`:
```python
def generate_alert_css() -> str:
    lines = []
    for event_type, colors in EVENT_COLORS.items():
        lines.append(f".alert-{event_type.value} {{ background: {colors['bg']}; }}")
    return "\n".join(lines)
```

**10. Use platformdirs for Config**
Replace hardcoded `~/.config/wxdxx/` with proper XDG support.

#### Low Priority

**11. Optimize LRU Cache**
Replace O(n) list operations with `collections.OrderedDict`.

**12. Add Cache Instrumentation**
Track hit/miss ratios, eviction counts for debugging.

**13. Delete Unused screens/ Directory**
Or repurpose if we add multi-screen navigation.

### Testing Strategy

**Current Coverage:**
- ✅ Smoke tests (app startup, widget rendering)
- ✅ SPC parser tests (with HTML fixtures)
- ✅ NWS parser tests (with JSON fixtures)
- ❌ Cache tests
- ❌ Config tests
- ❌ Widget interaction tests
- ❌ Integration tests

**Testing Priorities:**
1. Add cache.py unit tests (TTL, LRU, invalidation patterns)
2. Add widget pilot tests for Sidebar interactions
3. Add VCR.py-style cassette tests for API clients
4. Add model validation tests (edge cases, invalid data)

**Test File Naming:**
- `test_{module}_unit.py` - Unit tests
- `test_{module}_integration.py` - Integration tests
- `fixtures/{module}/` - Test fixtures per module

### Performance Considerations

**Current Bottlenecks:**
- Zone geometry fetching (67-615 points/zone, but cached 24hr)
- Ticker headline sorting on every scroll (could cache sort)
- Sidebar re-rendering on every update (could diff)

**Future Optimization Opportunities:**
- Lazy load zone geometry only when map is visible
- Debounce rapid sidebar updates
- Consider virtual scrolling if sidebar grows large

### Dependencies Philosophy

**Current Approach (Minimal):**
- httpx for HTTP (async-native, better than aiohttp)
- Pydantic for models (validation + serialization)
- Textual for TUI (Rich-based, modern)

**Adding Dependencies:**
- Prefer stdlib when possible (e.g., `zoneinfo` over `pytz`)
- Avoid AGPL dependencies (e.g., didn't use drawille)
- New deps need justification — what problem does it solve that we can't easily solve ourselves?

### Code Review Checklist

When reviewing code changes, verify:
- [ ] Type hints on all public functions
- [ ] No magic numbers (use constants)
- [ ] Error handling follows the pattern (exceptions in API, notifications in app)
- [ ] No duplicate logic (especially color mapping)
- [ ] Tests added for new parser/logic code
- [ ] CLAUDE.md updated if adding features or TODOs
