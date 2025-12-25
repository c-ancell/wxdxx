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
- Keyboard: q=quit, r=refresh, 1/2/3=Day 1/2/3 outlooks

## TODO / Not Yet Implemented
- Response caching
- Configuration file for default WFO
- Screens are stubs - all rendering happens in main app
- Option to show only latest WFO product versions (e.g., hide older AFD amendments since offices typically append updates to the latest full AFD)
- Keyboard-based scrolling in main content window (currently requires mousepad)
- Improve the help menu
- Rename app/title to better reflect its nature as a text product viewer for SPC and other NOAA centers/offices
- Show time since issuance and time until expiry in status bar when viewing products with valid times
