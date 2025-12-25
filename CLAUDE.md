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

## TODO / Not Yet Implemented (prioritized: quick wins first)

### Quick wins
- Create a reference for NWS/NOAA product abbreviations
- WFO loading indicator: When adding a WFO (e.g., "LUB"), it can take a while to load. The initial loading card disappears before data arrives, leaving no indication that loading is still in progress. Add a subtle indicator (e.g., in sidebar or status bar) to show data is still being fetched.
- Removing all WFOs should restore the "Add a WFO" hint message in the sidebar (currently leaves the WFO products section empty)

### Medium effort
- Configuration file for default WFO
- Response caching
- Convective Outlooks get reissued throughout the day. Most (if not all) have a line like "The next Day X outlook is scheduled by xxxxZ". Add a subtle UI element showing how long until the next outlook is issued. Also distinguish between "expiry" and "valid til" times in the status bar (expiry = product no longer relevant, valid til = end of forecast period but product may still be useful)

### Larger effort
- Highlight sidebar items for new products using NWS color conventions (e.g., red/white for tornado warnings, purple/white for PDS, etc.)
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)

### Architecture
- Screens are stubs - all rendering happens in main app
