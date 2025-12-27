# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
