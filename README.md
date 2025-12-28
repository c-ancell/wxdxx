# WxDXX

A terminal user interface (TUI) for viewing NWS text products from SPC, WPC, NHC, and local WFOs.

> **Note:** This project is in alpha. Features may change and some functionality is still being developed.

## Features

**SPC Products**
- Convective Outlooks (Day 1-3) with risk level color coding
- Mesoscale Discussions with watch probability indicators
- Watches (Tornado, Severe Thunderstorm) with PDS highlighting

**WFO Products**
- Track multiple Weather Forecast Offices
- Area Forecast Discussions (AFD), Hazardous Weather Outlooks (HWO), Special Weather Statements (SPS), and more
- Active alerts with NWS color coding (TOR=red, SVR=yellow, FFW=green, etc.)
- WFO lookup (`L`) shows office details, coverage areas, and contact info

**METAR Observations**
- METAR lookup (`O`) for current conditions at any ICAO station
- Nearby stations displayed at bottom of alerts (major airports prioritized)
- Temperature, wind, visibility, and raw METAR text

**Zone Maps**
- Braille-rendered maps showing affected zones for alerts (`m` to toggle)
- Zones colored by alert type (tornado=red, severe=yellow, flood=green, etc.)
- Major US cities shown as reference points

**News Ticker**
- Scrolling nationwide alerts bar showing active warnings and SPC watches
- Color-coded by severity, sorted by priority

**Smart Updates**
- Auto-refresh with configurable interval (default 60 seconds)
- TTL-based caching to minimize API requests
- Unread indicators for new/updated products
- Automatic filtering of expired products

## Installation

Requires Python 3.11+

```bash
# Clone the repository
git clone https://github.com/c-ancell/wxdxx.git
cd wxdxx

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

## Usage

```bash
# Activate virtual environment if not already active
source .venv/bin/activate

# Run the app
wxdxx
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all data |
| `s` | Settings |
| `?` | Help screen |
| `1` `2` `3` | View Day 1/2/3 Outlook |
| `Tab` | Switch between sidebar and content |
| `M` | Mark all as read |
| `w` | Add WFO |
| `W` | Remove WFO |
| `L` | Lookup WFO details |
| `O` | Lookup METAR station |
| `m` | Toggle zone map (when viewing alerts) |

**Navigation (vim-style)**
| Key | Action |
|-----|--------|
| `j` / `k` | Line down / up |
| `d` / `u` | Page down / up |
| `g` / `G` | Top / Bottom |
| Arrow keys | Also work |

## Configuration

Settings are stored in `~/.config/wxdxx/config.toml`:
- Tracked WFOs persist across restarts
- Refresh interval is configurable (10-600 seconds)

## Data Sources

- **SPC**: Storm Prediction Center (spc.noaa.gov) - outlooks, MDs, watches
- **NWS API**: National Weather Service API (api.weather.gov) - WFO products and alerts

## License

MIT
