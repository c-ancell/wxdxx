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
- Batch multiple small changes into a single version bump when reasonable
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
- Implement text-based reference maps: WFO areas, counties/zones affected by warnings, and potentially other geographic reference displays
- METAR support
- Handle empty MDs/watches on initial issuance: SPC sometimes publishes MDs and watches before the full content is available (appears in sidebar but content window is empty). Temporarily increase refresh rate for that specific product until full content is published and viewable.

### Spikes (Research/Discussion)
- Research ways we can be better stewards of the data sources we're using (SPC, NWS API) and suggest the top 5 most impactful changes. Consider: rate limiting, caching strategies, User-Agent best practices, error handling for API outages, respecting robots.txt, reducing unnecessary requests.

### Architecture
- Screens directory contains unused stubs (OutlooksScreen, WatchesScreen, etc.) from early development. The current single-screen architecture with sidebar + ProductView is simpler and works well for this app's scope. Could delete the stubs or revisit if the app grows significantly more complex, but not a priority.
