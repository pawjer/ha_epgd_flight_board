"""Constants for Gdańsk Airport integration."""
from enum import StrEnum
from typing import Final

DOMAIN: Final = "gdansk_airport"

# Configuration keys
CONF_DIRECTION: Final = "direction"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Options keys
CONF_MAX_FLIGHTS: Final = "max_flights"
CONF_TIME_WINDOW: Final = "time_window_hours"
CONF_HIDE_LANDED: Final = "hide_landed"
CONF_HIDE_CANCELLED: Final = "hide_cancelled"
CONF_AIRLINES_FILTER: Final = "airlines_filter"
CONF_DESTINATIONS_FILTER: Final = "destinations_filter"

# Events options (v2)
CONF_TRACKED_FLIGHTS: Final = "tracked_flights"
CONF_EVENTS_ENABLED: Final = "events_enabled"
CONF_EVENTS_ALL_FLIGHTS: Final = "events_all_flights"

# Event types (v2)
EVENT_FLIGHT_LANDED: Final = "gdansk_airport_flight_landed"
EVENT_FLIGHT_DEPARTED: Final = "gdansk_airport_flight_departed"
EVENT_FLIGHT_DELAYED: Final = "gdansk_airport_flight_delayed"
EVENT_FLIGHT_CANCELLED: Final = "gdansk_airport_flight_cancelled"
EVENT_FLIGHT_STATUS_CHANGED: Final = "gdansk_airport_flight_status_changed"
EVENT_FLIGHT_BOARDING: Final = "gdansk_airport_flight_boarding"
EVENT_FLIGHT_GATE_CLOSED: Final = "gdansk_airport_flight_gate_closed"
EVENT_FLIGHT_FINAL_CALL: Final = "gdansk_airport_flight_final_call"

# Direction options
DIRECTION_ARRIVALS: Final = "arrivals"
DIRECTION_DEPARTURES: Final = "departures"
DIRECTION_BOTH: Final = "both"

# URLs
URL_ARRIVALS: Final = "https://www.airport.gdansk.pl/loty/tablica-przylotow-p1.html"
URL_DEPARTURES: Final = "https://www.airport.gdansk.pl/loty/tablica-odlotow-p2.html"

# User agent
USER_AGENT: Final = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 5  # minutes
DEFAULT_MAX_FLIGHTS: Final = 20
DEFAULT_TIME_WINDOW: Final = 24  # hours
DEFAULT_HIDE_LANDED: Final = False
DEFAULT_HIDE_CANCELLED: Final = True
DEFAULT_MAX_CACHE_AGE_HOURS: Final = 1  # Maximum age for cached data (flight data changes frequently)

# Limits
MIN_SCAN_INTERVAL: Final = 2
MAX_SCAN_INTERVAL: Final = 60
MIN_MAX_FLIGHTS: Final = 5
MAX_MAX_FLIGHTS: Final = 50
MIN_TIME_WINDOW: Final = 1
MAX_TIME_WINDOW: Final = 48

# Sensor names
SENSOR_ARRIVALS: Final = "arrivals"
SENSOR_DEPARTURES: Final = "departures"
SENSOR_NEXT_ARRIVAL: Final = "next_arrival"
SENSOR_NEXT_DEPARTURE: Final = "next_departure"


class FlightStatus(StrEnum):
    """Flight status enum."""

    LANDED = "landed"
    DEPARTED = "departed"
    EXPECTED = "expected"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    BOARDING = "boarding"
    GATE_CLOSED = "gate_closed"
    FINAL_CALL = "final_call"
    CHECK_IN = "check_in"
    GATE = "gate"
    UNKNOWN = "unknown"


# Status mapping from Polish to enum
# Covers various status texts found on the website
STATUS_MAPPING_PL: Final[dict[str, FlightStatus]] = {
    # Arrivals
    "WYLĄDOWAŁ": FlightStatus.LANDED,
    "WYLADOWAL": FlightStatus.LANDED,
    "OCZEKIWANY": FlightStatus.EXPECTED,
    "OPÓŹNIONY": FlightStatus.DELAYED,
    "OPOZNIONY": FlightStatus.DELAYED,
    "ODWOŁANY": FlightStatus.CANCELLED,
    "ODWOLANY": FlightStatus.CANCELLED,
    # Departures
    "WYSTARTOWAŁ": FlightStatus.DEPARTED,
    "WYSTARTOWAL": FlightStatus.DEPARTED,
    "BOARDING": FlightStatus.BOARDING,
    "GATE ZAMKNIĘTY": FlightStatus.GATE_CLOSED,
    "GATE ZAMKNIETY": FlightStatus.GATE_CLOSED,
    "OSTATNIE WEZWANIE": FlightStatus.FINAL_CALL,
    "ODPRAWA": FlightStatus.CHECK_IN,
    "ODPRAWA OD": FlightStatus.CHECK_IN,
    "DO WYJSCIA": FlightStatus.GATE,
    "DO WYJŚCIA": FlightStatus.GATE,
}


def parse_status(status_text: str) -> FlightStatus:
    """Parse status text to FlightStatus enum.

    Args:
        status_text: Raw status text from website (e.g., "OPÓŹNIONY 00:32", "WYLĄDOWAŁ")

    Returns:
        FlightStatus enum value
    """
    if not status_text:
        return FlightStatus.UNKNOWN

    # Normalize: uppercase and strip whitespace
    normalized = status_text.strip().upper()

    # Try exact match first
    if normalized in STATUS_MAPPING_PL:
        return STATUS_MAPPING_PL[normalized]

    # Try partial matches for statuses with additional info (e.g., "OPÓŹNIONY 00:32")
    for key, status in STATUS_MAPPING_PL.items():
        if normalized.startswith(key):
            return status

    return FlightStatus.UNKNOWN
