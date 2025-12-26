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

**SPC/NWS parsing gotchas:**
- Always deduplicate when parsing HTML link lists with `re.findall()` - pages often have multiple links to the same product (header, table, sidebar, etc.). Use `set()` before returning.
- The `_is_refreshing` flag now guards against concurrent refreshes - check it at the start of `_refresh_all_data_with_indicator()`

## Current Features
- Convective Outlooks (Day 1-3) fetched from SPC
- Mesoscale Discussions - listed in sidebar, click to view full text
- Watches - listed in sidebar, click to view full text
- UTC and local clocks in status bar for comparing product timestamps
- Time since issuance and time until expiry shown in status bar when viewing products (MDs, Watches, Outlooks, and WFO products all have timestamps extracted)
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
- Outlook status bar shows "Valid Until" (not "Expires") and "Next: in Xh Ym" for when the next outlook is scheduled
- Sidebar items color-coded using NWS conventions: red for tornado watches, yellow for SVR, magenta for PDS; outlook risk levels (TSTM→HIGH); MD watch probability; WFO warnings (TOR/SVR/FFW/WSW)

## TODO / Not Yet Implemented (prioritized: quick wins first)

### Quick wins
- Time display refinements: issued time only needs minute resolution (not seconds), "Valid Until" should maybe show "Valid: DDHHmm - DDHHmm" format, and clock widget should show today's day number (e.g., "25") in both UTC and local time
- Show minutes-until-expiry on sidebar items that have a set expiration time

### Larger effort
- Make sidebar sections collapsible
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)

### Spikes / Research
- Investigate why flood warnings/watches/statements and less-frequently issued WFO products don't appear when retrieving local text products (may be an issue with `DEFAULT_PRODUCT_TYPES` filtering, API query parameters, or how NWS categorizes products by issuing office)

### Architecture
- Screens are stubs - all rendering happens in main app
