# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-13

### Added
- Initial release of Gdańsk Airport Flight Board integration
- HTML parser for scraping flight data from airport.gdansk.pl
- Support for both arrivals and departures
- 4 sensor entities:
  - `sensor.gdansk_airport_arrivals` - Number of arrivals with full flight list
  - `sensor.gdansk_airport_departures` - Number of departures with full flight list
  - `sensor.gdansk_airport_next_arrival` - Next upcoming arrival
  - `sensor.gdansk_airport_next_departure` - Next upcoming departure
- Config flow with GUI setup
- Options flow for advanced filtering:
  - Maximum flights to display (5-50)
  - Time window filter (1-48 hours)
  - Hide landed/departed flights
  - Hide cancelled flights
  - Airline filter (comma-separated)
  - Destination filter (comma-separated)
- Configurable scan interval (2-60 minutes, default: 5)
- Automatic flight status detection:
  - Landed, Departed, Expected, Delayed, Cancelled
  - Boarding, Gate Closed, Final Call, Check-in
- Delay calculation in minutes
- Smart caching with 1-hour expiry
- Cache metadata in sensor attributes (data_source, cache_age)
- English and Polish translations
- Comprehensive unit tests (22 tests)
- HACS compatible with proper manifest.json

### Features
- Real-time flight data scraping
- Automatic status updates
- Flight filtering by multiple criteria
- Graceful error handling with cache fallback
- Detailed logging for debugging
- Type hints throughout codebase
- Production-ready reliability

### Technical
- BeautifulSoup4 for HTML parsing
- aiohttp for async HTTP requests
- DataUpdateCoordinator for efficient updates
- Proper async/await patterns
- 30-second request timeout
- User-Agent spoofing to avoid blocking

[1.0.0]: https://github.com/pawjer/ha_epgd_flight_board/releases/tag/v1.0.0
