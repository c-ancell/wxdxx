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
- Keyboard: q=quit, r=refresh, 1/2/3=Day 1/2/3 outlooks

## TODO / Not Yet Implemented
- WFO products (AFDs, warnings) via NWS API
- Response caching
- Configuration file for default WFO
- Screens are stubs - all rendering happens in main app
