# SPC Dash

A TUI application for viewing Storm Prediction Center (SPC) products and WFO text products.

## Tech Stack
- Python 3.11+ with Textual (TUI framework)
- httpx for async HTTP requests
- Pydantic for data models

## Project Structure
```
src/spc_dash/
├── app.py              # Main Textual application
├── api/spc.py          # SPC website client
├── models/             # Pydantic models (outlook, md, watch)
├── widgets/            # Sidebar, ProductView
└── screens/            # Screen stubs (not fully implemented)
```

## Running the App
```bash
source .venv/bin/activate
.venv/bin/pip install .   # Required after code changes (editable install broken on Python 3.14)
.venv/bin/spc-dash
```

## Current Features
- Convective Outlooks (Day 1-3) fetched from SPC
- Mesoscale Discussions - listed in sidebar, click to view full text
- Watches - listed in sidebar, click to view full text
- UTC and local clocks in status bar for comparing product timestamps
- Time since issuance and time until expiry shown in status bar when viewing products
- Keyboard: q=quit, r=refresh, 1/2/3=Day 1/2/3 outlooks, ?=help
- Scrolling in content view: j/k=line up/down, d/u=page down/up, g/G=top/bottom, arrows also work
- Help screen (?) shows all keyboard shortcuts

## TODO / Not Yet Implemented
- Auto-refresh data every 1 minute with status bar indicator when refresh is running
- Extract issued/expires timestamps from MDs, Watches, and Outlooks (currently only WFO products have timing info; once extracted, set via `app._set_product_timing(issued=, expires=)` and ClockWidget will display them)
- Highlight sidebar items for new products using NWS color conventions (e.g., red/white for tornado warnings, purple/white for PDS, etc.)
- Response caching
- Configuration file for default WFO
- Keyboard shortcut for moving focus between main content window and navigation sidebar
- Create a reference for NWS/NOAA product abbreviations
- Option to show older WFO product versions (currently only shows latest; some users may want to see previous versions)
- Rename app/title to better reflect its nature as a text product viewer for SPC and other NOAA centers/offices
- Screens are stubs - all rendering happens in main app
