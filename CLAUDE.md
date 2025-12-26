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

## Current Features
- Convective Outlooks (Day 1-3) fetched from SPC
- Mesoscale Discussions - listed in sidebar, click to view full text
- Watches - listed in sidebar, click to view full text
- UTC and local clocks in status bar with day number (e.g., "UTC: 25 14:32 | Local: 25 08:32")
- Time since issuance shown in status bar (minute resolution)
- Outlook validity shown as date range (e.g., "Valid: 251200Z - 261200Z")
- MDs and Watches show countdown to expiry (e.g., "Expires: in 2h 15m")
- Expired products (MDs, Watches) are automatically filtered from the sidebar
- Keyboard: q=quit, r=refresh, s=settings, 1/2/3=Day 1/2/3 outlooks, ?=help, Tab=switch panel
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

## TODO / Not Yet Implemented

### Larger effort
- Make sidebar sections collapsible
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)
- Status bar cleanup: information (refresh time, product timing, clocks) is starting to overlap with quick-key commands. Consider leaving only "?" in the footer and moving all other hotkey shortcuts into the help menu (verify they're all documented there first)
- Add "R" (SHIFT+r) for hard refresh: Currently 'r' clears all caches and refreshes. Consider making 'r' a soft refresh (use cached data if valid) and 'R' a hard refresh (clear all caches first). This would make auto-refresh and 'r' behave the same way.

### Epic: News Ticker for Watches/Warnings
**Concept:** A scrolling news-ticker bar at the top of the UI showing new watches and warnings issued nationwide. Headlines scroll infinitely.

**Display format:**
- New issuances: `***NEW: OUN issues Tornado Warning for Oklahoma County until 10pm CDT***`
- Existing products: `EWX: Flash Flood Warning in effect until 28/1200 CDT`

**Styling:**
- NEW prefix headlines: Background colored using NWS conventions (red for TOR, yellow for SVR, etc.) for first 2 appearances
- After 2 appearances: Text colored by convention on black background (e.g., red text on black for TOR)

**To flesh out:** Data source, refresh strategy, headline priority/ordering, scroll speed, max headlines

### Architecture
- Screens are stubs - all rendering happens in main app
