"""Data coordinator for Gdańsk Airport integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_AIRLINES_FILTER,
    CONF_DESTINATIONS_FILTER,
    CONF_DIRECTION,
    CONF_EVENTS_ALL_FLIGHTS,
    CONF_EVENTS_ENABLED,
    CONF_HIDE_CANCELLED,
    CONF_HIDE_LANDED,
    CONF_MAX_FLIGHTS,
    CONF_TIME_WINDOW,
    CONF_TRACKED_FLIGHTS,
    DEFAULT_HIDE_CANCELLED,
    DEFAULT_HIDE_LANDED,
    DEFAULT_MAX_CACHE_AGE_HOURS,
    DEFAULT_MAX_FLIGHTS,
    DEFAULT_TIME_WINDOW,
    DIRECTION_ARRIVALS,
    DIRECTION_BOTH,
    DIRECTION_DEPARTURES,
    DOMAIN,
    EVENT_FLIGHT_BOARDING,
    EVENT_FLIGHT_CANCELLED,
    EVENT_FLIGHT_DELAYED,
    EVENT_FLIGHT_DEPARTED,
    EVENT_FLIGHT_FINAL_CALL,
    EVENT_FLIGHT_GATE_CLOSED,
    EVENT_FLIGHT_LANDED,
    EVENT_FLIGHT_STATUS_CHANGED,
    FlightStatus,
)
from .parser import Flight, fetch_all_flights
from .state_tracker import FlightStateTracker

_LOGGER = logging.getLogger(__name__)


class GdanskAirportCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Gdańsk Airport data."""

    def __init__(
        self,
        hass: HomeAssistant,
        direction: str,
        scan_interval: timedelta,
    ) -> None:
        """Initialize coordinator.

        Args:
            hass: Home Assistant instance
            direction: Flight direction (arrivals, departures, both)
            scan_interval: Update interval
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self.direction = direction
        self.session: aiohttp.ClientSession = async_get_clientsession(hass)

        # Cache management
        self._last_successful_update: datetime | None = None
        self._max_cache_age = timedelta(hours=DEFAULT_MAX_CACHE_AGE_HOURS)

        # State tracking for events (v2)
        self._state_tracker = FlightStateTracker()
        self._tracked_flights: set[str] = set()
        self._events_enabled: bool = False
        self._events_all_flights: bool = False

        # Options (can be updated via options flow)
        self.max_flights: int = DEFAULT_MAX_FLIGHTS
        self.time_window_hours: int = DEFAULT_TIME_WINDOW
        self.hide_landed: bool = DEFAULT_HIDE_LANDED
        self.hide_cancelled: bool = DEFAULT_HIDE_CANCELLED
        self.airlines_filter: list[str] = []
        self.destinations_filter: list[str] = []

    def update_options(self, options: dict[str, Any]) -> None:
        """Update coordinator options.

        Args:
            options: Options dictionary from config entry
        """
        self.max_flights = options.get(CONF_MAX_FLIGHTS, DEFAULT_MAX_FLIGHTS)
        self.time_window_hours = options.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)
        self.hide_landed = options.get(CONF_HIDE_LANDED, DEFAULT_HIDE_LANDED)
        self.hide_cancelled = options.get(CONF_HIDE_CANCELLED, DEFAULT_HIDE_CANCELLED)

        # Parse filter strings
        airlines = options.get(CONF_AIRLINES_FILTER, "")
        self.airlines_filter = [
            a.strip().upper() for a in airlines.split(",") if a.strip()
        ]

        destinations = options.get(CONF_DESTINATIONS_FILTER, "")
        self.destinations_filter = [
            d.strip().lower() for d in destinations.split(",") if d.strip()
        ]

        # Events configuration (v2)
        self._events_enabled = options.get(CONF_EVENTS_ENABLED, False)
        self._events_all_flights = options.get(CONF_EVENTS_ALL_FLIGHTS, False)

        # Parse tracked flights
        tracked = options.get(CONF_TRACKED_FLIGHTS, "")
        self._tracked_flights = {
            f.strip().upper() for f in tracked.split(",") if f.strip()
        }

    def _filter_flights(self, flights: list[Flight]) -> list[Flight]:
        """Filter flights based on options.

        Args:
            flights: List of flights to filter

        Returns:
            Filtered list of flights
        """
        filtered = []

        for flight in flights:
            # Filter by status
            if self.hide_landed and flight.status in (
                FlightStatus.LANDED,
                FlightStatus.DEPARTED,
            ):
                continue

            if self.hide_cancelled and flight.status == FlightStatus.CANCELLED:
                continue

            # Filter by airline
            if self.airlines_filter and flight.airline.upper() not in self.airlines_filter:
                continue

            # Filter by destination/origin
            if self.destinations_filter:
                location = (flight.destination or flight.origin or "").lower()
                if not any(dest in location for dest in self.destinations_filter):
                    continue

            # Filter by time window
            try:
                scheduled_h, scheduled_m = map(int, flight.scheduled_time.split(":"))
                flight_time = datetime.now().replace(
                    hour=scheduled_h, minute=scheduled_m, second=0, microsecond=0
                )
                now = datetime.now()

                # Handle flights scheduled for next day
                if flight_time < now - timedelta(hours=12):
                    flight_time += timedelta(days=1)

                time_diff = abs((flight_time - now).total_seconds() / 3600)

                if time_diff > self.time_window_hours:
                    continue

            except (ValueError, AttributeError) as err:
                _LOGGER.debug("Could not filter by time for flight %s: %s", flight.flight_number, err)

            filtered.append(flight)

        # Sort by scheduled time
        filtered.sort(key=lambda f: f.scheduled_time)

        # Limit to max_flights
        return filtered[: self.max_flights]

    def _get_next_flight(self, flights: list[Flight]) -> Flight | None:
        """Get next upcoming flight.

        Args:
            flights: List of flights

        Returns:
            Next flight or None
        """
        if not flights:
            return None

        # Filter out already landed/departed flights
        upcoming = [
            f
            for f in flights
            if f.status
            not in (FlightStatus.LANDED, FlightStatus.DEPARTED, FlightStatus.CANCELLED)
        ]

        if not upcoming:
            return None

        # Sort by expected or scheduled time
        upcoming.sort(key=lambda f: f.expected_time or f.scheduled_time)

        return upcoming[0]

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid.

        Returns:
            True if cache is valid and not too old
        """
        if not self.data or not self._last_successful_update:
            return False

        cache_age = datetime.now() - self._last_successful_update
        is_valid = cache_age < self._max_cache_age

        if not is_valid:
            _LOGGER.warning(
                "Cached data is too old (age: %s, max: %s)",
                cache_age,
                self._max_cache_age,
            )

        return is_valid

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.

        Returns:
            Dictionary with flight data

        Raises:
            UpdateFailed: On error
        """
        try:
            # Determine what to fetch
            fetch_arrivals = self.direction in (DIRECTION_ARRIVALS, DIRECTION_BOTH)
            fetch_departures = self.direction in (DIRECTION_DEPARTURES, DIRECTION_BOTH)

            # Fetch data
            result = await fetch_all_flights(
                self.session,
                fetch_arrivals=fetch_arrivals,
                fetch_departures=fetch_departures,
            )

            # Process state changes for events (before filtering)
            all_flights = (
                result.get(DIRECTION_ARRIVALS, []) + result.get(DIRECTION_DEPARTURES, [])
            )
            self._process_state_changes(all_flights)

            # Filter flights
            arrivals = self._filter_flights(result.get(DIRECTION_ARRIVALS, []))
            departures = self._filter_flights(result.get(DIRECTION_DEPARTURES, []))

            # Get next flights
            next_arrival = self._get_next_flight(arrivals) if arrivals else None
            next_departure = self._get_next_flight(departures) if departures else None

            # Update timestamp
            now = datetime.now()
            self._last_successful_update = now

            data = {
                DIRECTION_ARRIVALS: arrivals,
                DIRECTION_DEPARTURES: departures,
                "next_arrival": next_arrival,
                "next_departure": next_departure,
                "last_updated": now.isoformat(),
                "data_source": "live",
                "cache_age_seconds": 0,
            }

            _LOGGER.debug(
                "Updated data: %d arrivals, %d departures",
                len(arrivals),
                len(departures),
            )

            return data

        except aiohttp.ClientError as err:
            return self._handle_update_error("HTTP error", err)

        except asyncio.TimeoutError as err:
            return self._handle_update_error("Timeout", err)

        except Exception as err:
            _LOGGER.exception("Unexpected error fetching data: %s", err)
            return self._handle_update_error("Unexpected error", err)

    def _handle_update_error(self, error_type: str, error: Exception) -> dict[str, Any]:
        """Handle update errors with cache fallback.

        Args:
            error_type: Type of error (for logging)
            error: The exception that occurred

        Returns:
            Cached data with metadata

        Raises:
            UpdateFailed: If no valid cache available
        """
        # Check if we have valid cached data
        if self._is_cache_valid():
            cache_age = datetime.now() - self._last_successful_update
            cache_age_seconds = int(cache_age.total_seconds())

            _LOGGER.warning(
                "%s: %s - Using cached data (age: %s)",
                error_type,
                error,
                cache_age,
            )

            # Return cached data with updated metadata
            cached_data = self.data.copy()
            cached_data["data_source"] = "cache"
            cached_data["cache_age_seconds"] = cache_age_seconds
            cached_data["cache_age_minutes"] = cache_age_seconds // 60

            return cached_data

        # No valid cache - fail the update
        _LOGGER.error("%s: %s - No valid cached data available", error_type, error)
        raise UpdateFailed(f"{error_type}: {error}") from error

    def _get_event_type(self, new_status: FlightStatus) -> str | None:
        """Map flight status to event type.

        Args:
            new_status: New flight status

        Returns:
            Event type string or None if no specific event
        """
        status_event_map = {
            FlightStatus.LANDED: EVENT_FLIGHT_LANDED,
            FlightStatus.DEPARTED: EVENT_FLIGHT_DEPARTED,
            FlightStatus.DELAYED: EVENT_FLIGHT_DELAYED,
            FlightStatus.CANCELLED: EVENT_FLIGHT_CANCELLED,
            FlightStatus.BOARDING: EVENT_FLIGHT_BOARDING,
            FlightStatus.GATE_CLOSED: EVENT_FLIGHT_GATE_CLOSED,
            FlightStatus.FINAL_CALL: EVENT_FLIGHT_FINAL_CALL,
        }
        return status_event_map.get(new_status)

    def _should_fire_event(self, flight: Flight) -> bool:
        """Check if event should be fired for this flight.

        Args:
            flight: Flight to check

        Returns:
            True if event should be fired
        """
        if not self._events_enabled:
            return False

        # Fire for all flights if enabled
        if self._events_all_flights:
            return True

        # Fire only for tracked flights
        return flight.flight_number.upper() in self._tracked_flights

    def _fire_event(self, event_type: str, flight: Flight, old_status: FlightStatus | None = None) -> None:
        """Fire a flight event to Home Assistant.

        Args:
            event_type: Type of event to fire
            flight: Flight object
            old_status: Previous status (optional)
        """
        event_data = {
            "flight_number": flight.flight_number,
            "airline": flight.airline,
            "scheduled_time": flight.scheduled_time,
            "status": flight.status.value,
            "direction": flight.direction,
        }

        # Add optional fields
        if flight.expected_time:
            event_data["expected_time"] = flight.expected_time
        if flight.delay_minutes is not None:
            event_data["delay_minutes"] = flight.delay_minutes
        if flight.origin:
            event_data["origin"] = flight.origin
        if flight.destination:
            event_data["destination"] = flight.destination
        if old_status:
            event_data["old_status"] = old_status.value

        self.hass.bus.fire(event_type, event_data)

        _LOGGER.info(
            "Fired event %s for flight %s (status: %s)",
            event_type,
            flight.flight_number,
            flight.status.value,
        )

    def _process_state_changes(self, all_flights: list[Flight]) -> None:
        """Process state changes and fire events.

        Args:
            all_flights: List of all current flights (before filtering)
        """
        if not self._events_enabled:
            return

        # Detect changes
        changes = self._state_tracker.detect_changes(all_flights)

        for change in changes:
            if not self._should_fire_event(change.flight):
                continue

            # Get specific event type for status change
            event_type = self._get_event_type(change.new_status)

            # Fire specific event if available
            if event_type:
                self._fire_event(event_type, change.flight, change.old_status)

            # Always fire generic status_changed event
            if change.old_status != change.new_status:
                self._fire_event(
                    EVENT_FLIGHT_STATUS_CHANGED,
                    change.flight,
                    change.old_status,
                )
