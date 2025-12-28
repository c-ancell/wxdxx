# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.8] - 2025-12-28

### Fixed

- WFO alerts now re-fetch from API on cache miss instead of showing error (#17)
- Snow Squall Warnings now appear in news ticker (#16)
- Alerts no longer show "NWS" as WFO - using senderCode for attribution (#12)
- WFO alerts no longer incorrectly deduplicated when WFO lookup fails (#15)

## [0.8.7] - 2025-12-28

### Added

- New `utils/datetime.py` module with consolidated datetime parsing utilities

### Changed

- Refactored datetime parsing to use shared utilities (~200 lines removed)
- `api/spc.py` and `api/nws.py` now use centralized parsing functions
- `widgets/sidebar.py` and `app.py` now use `format_countdown()` from utils

## [0.8.6] - 2025-12-28

### Added

- Mypy type checking enabled with permissive configuration
- 44 unit tests for cache module (TTLCache and ProductCache)

### Changed

- Extracted `BaseProduct` base class for all product models
- Refactored sidebar update methods with shared `_update_category_items()` helper

### Fixed

- 15 type errors caught by mypy (incorrect imports, type narrowing, return types)
- Watch fast-poll now correctly retrieves watch_type from cached watch

## [0.8.5] - 2025-12-28

### Changed

- Extracted `BaseProduct` base class for all product models (internal refactor)
- Refactored sidebar update methods with shared `_update_category_items()` helper

## [0.8.4] - 2025-12-28

### Added

- File-based logging: All API calls, retries, errors, and app events now logged to `~/.config/wxdxx/wxdxx.log`
- Rotating log files (5MB max, 3 backups) to prevent disk fill-up
- Debug logging for fetch operations, retry attempts, and refresh timing

## [0.8.3] - 2025-12-28

### Changed

- Consolidated API client base class: Extracted shared retry/rate-limiting logic into `BaseAPIClient`
- SPCClient and NWSClient now inherit from common base, eliminating ~90 lines of duplicate code

## [0.8.2] - 2025-12-28

### Changed

- Centralized event color mapping into single `colors.py` module (internal refactor)
- Added architecture standards and refactoring roadmap to CLAUDE.md

## [0.8.1] - 2025-12-27

### Fixed

- Sidebar 'g' and 'G' hotkeys now work (jump to top/bottom)

## [0.8.0] - 2025-12-27

### Added

- METAR lookup feature: Press 'O' to look up current conditions at any ICAO station
- Nearby stations in alerts: Bottom of alert text shows current conditions from up to 10 stations in affected zones
- Major airport priority: Nearby stations list major airports (KORD, KDFW, etc.) before regional stations
- Zone map colors: Affected zones now colored by alert type (TOR=red, SVR=yellow, FFW=green, etc.)
- City markers on zone maps: Major US cities shown as cyan reference points with legend
- UPDATE ticker prefix: Alert updates from NWS now show "UPDATE" instead of "NEW" flash

### Fixed

- City markers now display over alert fills on zone maps (priority-based rendering)

## [0.7.0] - 2025-12-27

### Added

- WFO lookup feature: Press 'L' to look up details about any WFO (name, address, phone, coverage area)
- New WFO details modal displays forecast zones, counties, and fire weather zones covered

## [0.4.0] - 2025-12-27

### Added

- Zone maps for NWS alerts: Press 'm' when viewing an alert to see a Braille-rendered map of affected zones
- Context zones: Map displays all WFO zones as gray outlines with affected zones highlighted in red
- Zone geometry API: Fetch and cache GeoJSON polygon data from NWS zone endpoints

### Fixed

- WFO extraction from alerts now uses tracked WFO ID (fixes "DEN" vs "BOU" mismatch)
- Map rendering no longer freezes news ticker (bounding box optimization + thread-based rendering)

## [0.3.0] - 2025-12-27

### Added

- Fast-polling for empty MDs/watches: When SPC publishes a product before full content is available, the app now polls every 15 seconds (up to 5 minutes) until content appears
- Automatic sidebar refresh when polled content becomes available

## [0.2.0] - 2025-12-27

### Added

- Configurable news ticker speed in settings (1-5 scale, where 1=slowest, 5=fastest)
- Ticker speed persists across restarts in config file
- Live ticker speed updates without app restart

## [0.1.3] - 2025-12-27

### Fixed

- News ticker headline color showing white instead of event-specific color when transitioning from "new" (background) to regular state. Root cause was stale plain text not being rebuilt when `is_new` status changed.

## [0.1.2] - 2025-12-27

### Added

- Request rate limiting via async semaphores (SPC: 3 concurrent, NWS: 8 concurrent)
- Retry with exponential backoff on transient failures (1s, 2s, 4s delays, max 3 retries)
- Retries on transport errors, timeouts, 5xx server errors, and 429 rate limits

## [0.1.1] - 2025-12-27

### Changed

- User-Agent headers now include GitHub repo URL and contact email per NWS API best practices

### Added

- README with installation, usage, and keyboard shortcuts documentation

## [0.1.0] - 2025-12-26

### Added

- Initial alpha release
- Convective Outlooks (Day 1-3) from SPC with risk level color coding
- Mesoscale Discussions with watch probability highlighting and expiry countdowns
- Watches (Tornado/Severe Thunderstorm/PDS) with NWS color coding
- WFO product tracking (AFD, ZFP, NOW, HWO, SPS) with persistence across restarts
- WFO active alerts (warnings, watches, advisories) by forecast zone
- Scrolling news ticker for nationwide NWS warnings and SPC watches
- Unread indicators for new/updated products
- UTC and local clocks in status bar with product timing info
- Auto-refresh with configurable interval (default 60 seconds)
- TTL-based in-memory caching for all data
- Vim-style keyboard navigation (j/k/g/G/d/u)
- Help screen (?) with keyboard shortcuts and version display
- Settings screen (s) for refresh interval configuration

### Technical

- Built with Textual TUI framework
- Async HTTP via httpx
- Pydantic models for data validation
- SPC HTML scraping (no official API)
- NWS API integration (api.weather.gov)
