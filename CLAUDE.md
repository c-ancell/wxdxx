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
│   └── wfo_input.py    # WFO add/remove dialog
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
- News Ticker: Scrolling bar below header showing nationwide NWS warnings and SPC watches. Headlines colored by event type (TOR=red, SVR=yellow, etc.). New alerts show with background color for first 2 scroll cycles, then text color only. Headlines sorted by severity (TOR > SVR > FFW > watches). Expired alerts are automatically filtered out on each scroll cycle.

## TODO / Not Yet Implemented

### Larger effort
- Make sidebar sections collapsible
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)
- Add "R" (SHIFT+r) for hard refresh: Currently 'r' clears all caches and refreshes. Consider making 'r' a soft refresh (use cached data if valid) and 'R' a hard refresh (clear all caches first). This would make auto-refresh and 'r' behave the same way.
- METAR support
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
1. Resolution vs. complexity - State-level (feasible) vs. county/zone-level (3000+ polygons)?
2. Static vs. dynamic - Pre-made ASCII templates vs. runtime GeoJSON→ASCII conversion?
3. Integration - Modal screen, inline in ProductView, or separate panel?
4. Data bundling - Fetch on-demand, bundle simplified boundaries, or cache locally?

**Spikes to complete before implementation:**

1. **Explore MapSCII rendering approach**: Study https://github.com/rastapasta/mapscii to understand Braille-based map rendering. Could we port concepts to Python/Textual? What resolution is achievable?

2. **Inspect NWS alert geometry**: Fetch a real warning with geometry from api.weather.gov, examine GeoJSON structure. How complex are the polygons? Do we get state/county identifiers or just coordinates?

3. **Prototype ASCII US map**: Hand-draw a simple US map with state outlines (~40 lines tall). Test rendering in a Textual widget. Can individual states be highlighted legibly with Rich styling?

4. **Evaluate Braille vs. block characters**: Test terminal compatibility for Braille characters (⠿⣿). Compare visual quality against standard block characters (█▀▄). What's the practical resolution difference?

5. **UGC-to-state mapping**: We already parse UGC codes from warnings. Build a mapping from zone/county codes to state abbreviations. How complete can we make this without external data?

**Potential MVP (after spikes):** Pre-generated ASCII US map with state outlines, highlight affected states based on UGC codes. Limits detail but covers most use cases with minimal complexity.

### Spikes (Research/Discussion)
(None currently - see Epic sections above for spike items)

### Architecture
- Screens directory contains unused stubs (OutlooksScreen, WatchesScreen, etc.) from early development. The current single-screen architecture with sidebar + ProductView is simpler and works well for this app's scope. Could delete the stubs or revisit if the app grows significantly more complex, but not a priority.
