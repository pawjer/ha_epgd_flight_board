# Gdańsk Airport Flight Board - Home Assistant Integration

Custom integration for Home Assistant that scrapes flight arrivals and departures data from Gdańsk Airport (airport.gdansk.pl) and provides it as sensors.

## Features

- 📥 **Arrivals sensor** - tracks incoming flights
- 📤 **Departures sensor** - tracks outgoing flights
- 🔜 **Next flight sensors** - dedicated sensors for next arrival/departure
- ⏱️ **Real-time updates** - configurable refresh interval (2-60 minutes)
- 🎯 **Smart filtering** - filter by airline, destination, time window
- 🔄 **Automatic status detection** - landed, delayed, boarding, cancelled, etc.
- 🌐 **Bilingual** - English and Polish translations

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Gdańsk Airport" in HACS
3. Click Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/gdansk_airport` directory to your Home Assistant `config/custom_components` directory
2. Restart Home Assistant

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

If you encounter any issues, please [open an issue](https://github.com/proboszcz/ha-gdansk-airport/issues) on GitHub.

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Port Lotniczy Gdańsk.
