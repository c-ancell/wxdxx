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
├── cache.py            # TTL-based in-memory cache (ProductCache)
├── config.py           # Configuration model and persistence (TOML)
├── colors.py           # Centralized event color mapping
├── api/
│   ├── base.py         # BaseAPIClient with shared retry/rate limiting
│   ├── spc.py          # SPC website scraper (HTML parsing)
│   └── nws.py          # NWS API client (api.weather.gov)
├── models/             # Pydantic models (outlook, md, watch, wfo, alert)
├── utils/
│   └── datetime.py     # Datetime parsing and formatting utilities
├── widgets/            # Textual widgets (sidebar, product_view, news_ticker, zone_map, etc.)
└── screens/            # Screen stubs (unused)
```

## Running the App
```bash
source .venv/bin/activate
.venv/bin/pip install .   # Required after code changes
.venv/bin/wxdxx
```

## Development Workflow

### Branching
- Work directly on `main` for small changes
- Feature branch for 3+ files or experimental work: `feature/short-description`

### Testing
```bash
.venv/bin/pytest tests/ -v
```

### TODO Tracking
Add TODOs to the "TODO / Not Yet Implemented" section below. This file is the canonical source.

### Versioning
Semantic versioning with git tags. Version in `pyproject.toml`.
- Patch: bug fixes, parser updates
- Minor: new features
- Major: breaking changes (discuss first)

Workflow: Update `pyproject.toml` → Update `CHANGELOG.md` → Commit → Tag → Push

## Development Notes

**Textual gotchas:**
- `DOMQuery` objects are truthy even when empty; use `len(list(query(...))) == 0`
- Status bar needs forced updates via `_update_clock_display()` for fast operations
- `set_interval` timers unreliable from App context; use async worker loop pattern
- Defer `run_worker()` calls with `call_later()` in `on_mount`

**SPC/NWS parsing gotchas:**
- Deduplicate `re.findall()` results with `set()` - pages have duplicate links
- UGC expiry: Only roll back month when current day is 1-2 and expiry day is 28-31
- NWS API: Don't use `message_type=alert` filter - it excludes "Update" messages
- UTC display: Always `.astimezone(timezone.utc)` before formatting with "Z" suffix
- Filter expired items at multiple points (fetch, build, timer, display)

**Cache architecture:**
- Key format: `{source}:{category}:{identifier}` (e.g., `spc:md:2462`)
- Type-safe helpers: `get_md(num)`, `set_outlook(day, obj)`, etc.
- Zone cache has 24hr TTL, not cleared on refresh

## TODO / Not Yet Implemented

### Bugs
- Alert sidebar click shows "Error try refreshing": Sometimes clicking an alert shows error. Needs investigation.

### Small Enhancements
- METAR lookup: Show expanded station name with city/state

### Larger Effort
- Make sidebar sections collapsible
- Option to show older WFO product versions
- Add "R" (SHIFT+r) for hard refresh vs soft refresh
- AFD trend analysis: Track content changes to detect forecast confidence shifts

### Zone Map Enhancements
- Add map support for MDs and Watches (extract geometry from SPC data)
- Add zone labels or legend

### Refactoring Roadmap

**Medium Priority:**
- **9. Generate CSS from Color Registry** - Generate CSS from `EVENT_COLORS` instead of 400 lines hand-written
- **10. Use platformdirs for Config** - Replace hardcoded `~/.config/wxdxx/` with XDG support

**Low Priority:**
- **11. Optimize LRU Cache** - Replace O(n) list operations with `collections.OrderedDict`
- **12. Add Cache Instrumentation** - Track hit/miss ratios for debugging
- **13. Delete Unused screens/ Directory**

## Code Standards

- Type hints on all public functions (use `| None` not `Optional`)
- No magic numbers - use constants
- Exceptions in API layer, notifications in app layer
- Tests for new parser/logic code
