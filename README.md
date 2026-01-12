# Gdańsk Airport Flight Board - Home Assistant Integration

[![GitHub Release](https://img.shields.io/github/release/pawjer/ha_epgd_flight_board.svg?style=flat-square)](https://github.com/pawjer/ha_epgd_flight_board/releases)
[![License](https://img.shields.io/github/license/pawjer/ha_epgd_flight_board.svg?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

Custom integration for Home Assistant that scrapes flight arrivals and departures data from Gdańsk Airport (airport.gdansk.pl) and provides it as sensors.

**Current Version: 1.0.0** | [Changelog](CHANGELOG.md)

## Features

- 📥 **Arrivals sensor** - tracks incoming flights
- 📤 **Departures sensor** - tracks outgoing flights
- 🔜 **Next flight sensors** - dedicated sensors for next arrival/departure
- ⏱️ **Real-time updates** - configurable refresh interval (2-60 minutes)
- 🎯 **Smart filtering** - filter by airline, destination, time window
- 🔄 **Automatic status detection** - landed, delayed, boarding, cancelled, etc.
- 💾 **Smart caching** - maintains data freshness with 1-hour cache expiry
- 📊 **Cache transparency** - sensors show if data is live or cached
- 🌐 **Bilingual** - English and Polish translations

## Data Freshness & Reliability

This integration prioritizes data accuracy:

- **Live Data First**: Always attempts to fetch fresh data from the airport website
- **Smart Cache Fallback**: If the website is temporarily unavailable, uses cached data
- **Cache Expiry**: Cached data is valid for maximum **1 hour**
- **Transparency**: Sensors show `data_source: "live"` or `"cache"` with exact age
- **No Stale Data**: Sensors become unavailable if cache expires (better than showing outdated information)

This ensures you never see flight data that's more than 1 hour old!

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/pawjer/ha_epgd_flight_board` as repository
6. Select "Integration" as category
7. Click "Add"
8. Search for "Gdańsk Airport" in HACS
9. Click "Install"
10. Restart Home Assistant

### Manual Installation

1. Download the [latest release](https://github.com/pawjer/ha_epgd_flight_board/releases/latest)
2. Extract the `custom_components/gdansk_airport` directory to your Home Assistant `config/custom_components` directory
3. Restart Home Assistant

The directory structure should look like:
```
config/
  custom_components/
    gdansk_airport/
      __init__.py
      manifest.json
      ...
```

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Gdańsk Airport"
4. Configure:
   - **Name**: Custom name for the integration
   - **Direction**: Arrivals, Departures, or Both
   - **Update Interval**: How often to fetch data (2-60 minutes, default: 5)

### Options

After setup, you can configure additional options:

- **Maximum flights**: Limit number of flights displayed (5-50, default: 20)
- **Time window**: Show flights within X hours (1-48, default: 24)
- **Hide landed/departed**: Hide completed flights
- **Hide cancelled**: Hide cancelled flights
- **Airlines filter**: Comma-separated list of airlines (e.g., "WIZZ AIR, RYANAIR")
- **Destinations filter**: Comma-separated list of destinations (e.g., "London, Barcelona")

## Sensors

### Main Sensors

- `sensor.gdansk_airport_arrivals` - Number of arrivals
  - Attributes: Full list of flights, next flight, last updated
- `sensor.gdansk_airport_departures` - Number of departures
  - Attributes: Full list of flights, next flight, last updated

### Next Flight Sensors

- `sensor.gdansk_airport_next_arrival` - Time of next arrival
  - Attributes: Full flight details
- `sensor.gdansk_airport_next_departure` - Time of next departure
  - Attributes: Full flight details

### Flight Attributes

Each flight includes:
- `scheduled_time` - Planned time (HH:MM)
- `expected_time` - Expected time (if delayed)
- `origin` - Origin city (for arrivals)
- `destination` - Destination city (for departures)
- `airline` - Airline name
- `flight_number` - Flight number
- `status` - Flight status (landed, delayed, boarding, etc.)
- `delay_minutes` - Delay in minutes (if applicable)

### Sensor Attributes

Each sensor includes additional attributes:

- `flights` - Array of flight objects with full details
- `next_flight` - Next upcoming flight details
- `last_updated` - ISO 8601 timestamp of last update
- `data_source` - "live" or "cache" (shows if using cached data)
- `cache_age_seconds` - Age of cached data in seconds (if using cache)
- `cache_age_minutes` - Age of cached data in minutes (if using cache)

**Cache Behavior:**
- Fresh data is marked as `data_source: "live"`
- Cached data (during temporary outages) shows actual age
- Cache is valid for maximum 1 hour
- Sensors become unavailable if cache expires (better than showing stale data)

## Example Automation

```yaml
automation:
  - alias: "Notify on delayed flight"
    trigger:
      - platform: template
        value_template: >
          {{ states.sensor.gdansk_airport_next_departure.attributes.status == 'delayed' }}
    action:
      - service: notify.mobile_app
        data:
          message: >
            Your flight {{ states.sensor.gdansk_airport_next_departure.attributes.flight_number }}
            to {{ states.sensor.gdansk_airport_next_departure.attributes.destination }}
            is delayed by {{ states.sensor.gdansk_airport_next_departure.attributes.delay_minutes }} minutes.
```

## Example Lovelace Card

```yaml
type: markdown
content: |
  ## ✈️ Next Flights

  **Next Arrival:** {{ states.sensor.gdansk_airport_next_arrival.state }}
  - From: {{ state_attr('sensor.gdansk_airport_next_arrival', 'origin') }}
  - Flight: {{ state_attr('sensor.gdansk_airport_next_arrival', 'flight_number') }}
  - Status: {{ state_attr('sensor.gdansk_airport_next_arrival', 'status') }}

  **Next Departure:** {{ states.sensor.gdansk_airport_next_departure.state }}
  - To: {{ state_attr('sensor.gdansk_airport_next_departure', 'destination') }}
  - Flight: {{ state_attr('sensor.gdansk_airport_next_departure', 'flight_number') }}
  - Status: {{ state_attr('sensor.gdansk_airport_next_departure', 'status') }}
```

## Flight Statuses

The integration recognizes the following statuses:

- **landed** / **departed** - Flight completed
- **expected** - Flight on time
- **delayed** - Flight delayed
- **cancelled** - Flight cancelled
- **boarding** - Boarding in progress
- **gate_closed** - Gate closed
- **final_call** - Final boarding call
- **check_in** - Check-in open
- **gate** - Gate assigned

## Development

### Running Tests

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_test.txt
pytest tests/
```

### Code Quality

The project uses:
- **black** - Code formatting
- **isort** - Import sorting
- **ruff** - Linting
- **pytest** - Testing

## Data Source

This integration scrapes data from the official Gdańsk Airport website:
- Arrivals: https://www.airport.gdansk.pl/loty/tablica-przylotow-p1.html
- Departures: https://www.airport.gdansk.pl/loty/tablica-odlotow-p2.html

⚠️ **Note**: As this integration relies on web scraping, it may break if the airport website structure changes.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Support

If you encounter any issues, please [open an issue](https://github.com/pawjer/ha_epgd_flight_board/issues) on GitHub.

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Port Lotniczy Gdańsk.
