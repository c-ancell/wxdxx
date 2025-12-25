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
├── api/
│   ├── spc.py          # SPC website scraper (HTML parsing)
│   └── nws.py          # NWS API client (api.weather.gov)
├── models/             # Pydantic models (outlook, md, watch, wfo)
├── widgets/
│   ├── sidebar.py      # Navigation sidebar with categories
│   ├── product_view.py # Scrollable content display
│   ├── help_screen.py  # Help modal with keyboard shortcuts
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

## Current Features
- Convective Outlooks (Day 1-3) fetched from SPC
- Mesoscale Discussions - listed in sidebar, click to view full text
- Watches - listed in sidebar, click to view full text
- UTC and local clocks in status bar for comparing product timestamps
- Time since issuance and time until expiry shown in status bar when viewing products (MDs, Watches, Outlooks, and WFO products all have timestamps extracted)
- Expired products (MDs, Watches) are automatically filtered from the sidebar
- Keyboard: q=quit, r=refresh, 1/2/3=Day 1/2/3 outlooks, ?=help, Tab=switch panel
- Scrolling in content view: j/k=line up/down, d/u=page down/up, g/G=top/bottom, arrows also work
- Help screen (?) shows all keyboard shortcuts
- Auto-refresh every 60 seconds with "Refreshing..." indicator in status bar
- WFO loading indicator in status bar shows which WFOs are being fetched

## TODO / Not Yet Implemented (prioritized: quick wins first)

### Quick wins
- Create a reference for NWS/NOAA product abbreviations

### Medium effort
- Configuration file for default WFO
- Response caching
- Convective Outlooks get reissued throughout the day. Most (if not all) have a line like "The next Day X outlook is scheduled by xxxxZ". Add a subtle UI element showing how long until the next outlook is issued. Also distinguish between "expiry" and "valid til" times in the status bar (expiry = product no longer relevant, valid til = end of forecast period but product may still be useful)

### Larger effort
- Highlight sidebar items for new products using NWS color conventions (e.g., red/white for tornado warnings, purple/white for PDS, etc.)
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)

### Architecture
- Screens are stubs - all rendering happens in main app
