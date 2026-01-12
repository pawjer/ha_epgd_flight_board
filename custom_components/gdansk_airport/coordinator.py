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
    CONF_HIDE_CANCELLED,
    CONF_HIDE_LANDED,
    CONF_MAX_FLIGHTS,
    CONF_TIME_WINDOW,
    DEFAULT_HIDE_CANCELLED,
    DEFAULT_HIDE_LANDED,
    DEFAULT_MAX_FLIGHTS,
    DEFAULT_TIME_WINDOW,
    DIRECTION_ARRIVALS,
    DIRECTION_BOTH,
    DIRECTION_DEPARTURES,
    DOMAIN,
    FlightStatus,
)
from .parser import Flight, fetch_all_flights

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

            # Filter flights
            arrivals = self._filter_flights(result.get(DIRECTION_ARRIVALS, []))
            departures = self._filter_flights(result.get(DIRECTION_DEPARTURES, []))

            # Get next flights
            next_arrival = self._get_next_flight(arrivals) if arrivals else None
            next_departure = self._get_next_flight(departures) if departures else None

            data = {
                DIRECTION_ARRIVALS: arrivals,
                DIRECTION_DEPARTURES: departures,
                "next_arrival": next_arrival,
                "next_departure": next_departure,
                "last_updated": datetime.now().isoformat(),
            }

            _LOGGER.debug(
                "Updated data: %d arrivals, %d departures",
                len(arrivals),
                len(departures),
            )

            return data

        except aiohttp.ClientError as err:
            # If we have cached data, log error but don't fail
            if self.data:
                _LOGGER.warning("Failed to update data, using cached data: %s", err)
                return self.data

            _LOGGER.error("Failed to fetch data: %s", err)
            raise UpdateFailed(f"Failed to fetch data: {err}") from err

        except asyncio.TimeoutError as err:
            if self.data:
                _LOGGER.warning("Timeout updating data, using cached data")
                return self.data

            _LOGGER.error("Timeout fetching data")
            raise UpdateFailed("Timeout fetching data") from err

        except Exception as err:
            if self.data:
                _LOGGER.warning("Unexpected error, using cached data: %s", err)
                return self.data

            _LOGGER.exception("Unexpected error fetching data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err
