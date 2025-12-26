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

## TODO / Not Yet Implemented

### Epic: WFO Active Alerts
**Background:** The NWS API separates text products (`/products`) from hazard alerts (`/alerts/active`). We currently only query text products (AFD, HWO, SPS, NOW, ZFP). Warnings, watches, and advisories (Flood Watch, Winter Storm Warning, etc.) are in the alerts system and require querying by forecast zone.

**Technical approach:** Each WFO has `responsibleForecastZones` (via `/offices/{wfoId}`). Query `/alerts/active?zone=...` with those zones to get active hazard alerts for that WFO's coverage area.

- [ ] Add `get_wfo_zones(wfo_id)` method to NWSClient to fetch responsible forecast zones
- [ ] Refactor `get_active_alerts()` to accept zone list and filter by zones instead of senderName
- [ ] Cache WFO zones (they rarely change) - consider long TTL or persist to config
- [ ] Call `get_active_alerts()` during `_refresh_wfo_products()`
- [ ] Update sidebar to display alerts alongside text products
- [ ] Add color coding for alerts based on severity/event type (red for warnings, orange for watches, yellow for advisories)
- [ ] Show expiry countdown for alerts (they have `expires` field)

### Epic: SPS Expiry Filtering
**Background:** SPS (Special Weather Statement) products describe active weather events with specific expiry times (e.g., "thunderstorms until 10 AM"). However, the NWS API's `expirationTime` field is not populated for text products. The expiry is embedded in the UGC (Universal Geographic Code) header within the product text.

**The problem:** We display the most recent SPS from each WFO regardless of age. If no new SPS is issued, an 18+ hour old expired SPS remains visible because:
- API always returns most recent product
- Cache refresh just re-fetches the same old product
- No expiry filtering exists

**Technical approach:** Parse the UGC header expiry (`DDHHMM-` format) from SPS product text and filter out expired products from the sidebar.

**UGC format example:**
```
CAZ103-104-106-261800-
               ^^^^^^
               Day 26, 18:00 UTC
```

- [ ] Add `parse_ugc_expiry(text)` helper function to extract expiry datetime from UGC header
- [ ] Modify `get_products_by_type()` to fetch full product text for SPS (currently lazy-loaded)
- [ ] Add `expires` field to WFOProduct model (populate from UGC for SPS, None for others)
- [ ] Filter expired SPS products in `_refresh_wfo_products()` before updating sidebar
- [ ] Pass `expires` to sidebar for SPS items to show countdown (reuse existing expiry display logic)
- [ ] Add unit tests for UGC expiry parsing with various formats

### Larger effort
- Make sidebar sections collapsible
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)
- Status bar cleanup: information (refresh time, product timing, clocks) is starting to overlap with quick-key commands. Consider leaving only "?" in the footer and moving all other hotkey shortcuts into the help menu (verify they're all documented there first)

### Architecture
- Screens are stubs - all rendering happens in main app
