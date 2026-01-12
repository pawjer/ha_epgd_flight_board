"""Parser for Gdańsk Airport flight board."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    DIRECTION_ARRIVALS,
    DIRECTION_DEPARTURES,
    URL_ARRIVALS,
    URL_DEPARTURES,
    USER_AGENT,
    FlightStatus,
    parse_status,
)

_LOGGER = logging.getLogger(__name__)

# Timeout for HTTP requests
REQUEST_TIMEOUT = 30


@dataclass
class Flight:
    """Flight data model."""

    scheduled_time: str  # "22:50"
    expected_time: str | None  # "23:32" or None
    origin: str | None  # for arrivals
    destination: str | None  # for departures
    airline: str  # "WIZZ AIR"
    flight_number: str  # "W6 1706"
    status: FlightStatus  # enum
    delay_minutes: int | None  # calculated delay
    direction: str  # "arrival" | "departure"

    def to_dict(self) -> dict[str, Any]:
        """Convert flight to dictionary."""
        return {
            "scheduled_time": self.scheduled_time,
            "expected_time": self.expected_time,
            "origin": self.origin,
            "destination": self.destination,
            "airline": self.airline,
            "flight_number": self.flight_number,
            "status": self.status.value,
            "delay_minutes": self.delay_minutes,
            "direction": self.direction,
        }


def _calculate_delay(scheduled_time: str, expected_time: str | None) -> int | None:
    """Calculate delay in minutes between scheduled and expected time.

    Args:
        scheduled_time: Scheduled time in HH:MM format
        expected_time: Expected time in HH:MM format or None

    Returns:
        Delay in minutes, or None if cannot be calculated
    """
    if not expected_time or not scheduled_time:
        return None

    try:
        # Parse times
        sched_h, sched_m = map(int, scheduled_time.split(":"))
        exp_h, exp_m = map(int, expected_time.split(":"))

        # Create datetime objects for today
        today = datetime.now().replace(second=0, microsecond=0)
        scheduled = today.replace(hour=sched_h, minute=sched_m)
        expected = today.replace(hour=exp_h, minute=exp_m)

        # Handle midnight crossing (e.g., 23:50 -> 00:30)
        if expected < scheduled:
            expected += timedelta(days=1)

        delay = (expected - scheduled).total_seconds() / 60
        return int(delay)
    except (ValueError, AttributeError) as err:
        _LOGGER.debug("Could not calculate delay: %s", err)
        return None


def _extract_time_from_status(status_text: str) -> str | None:
    """Extract time from status text like 'OPÓŹNIONY 00:32'.

    Args:
        status_text: Status text potentially containing time

    Returns:
        Extracted time in HH:MM format or None
    """
    if not status_text:
        return None

    # Look for time pattern HH:MM
    match = re.search(r"\b(\d{1,2}:\d{2})\b", status_text)
    if match:
        return match.group(1)
    return None


def _parse_flight_element(element: Any, direction: str) -> Flight | None:
    """Parse a single flight element from HTML.

    Args:
        element: BeautifulSoup element representing a flight row
        direction: "arrival" or "departure"

    Returns:
        Flight object or None if parsing fails
    """
    try:
        # Extract scheduled time
        time_elem = element.find("div", class_="table__time")
        if not time_elem or "table__time_expected" in time_elem.get("class", []):
            return None
        scheduled_time = time_elem.get_text(strip=True)

        # Extract location (origin for arrivals, destination for departures)
        airport_elem = element.find("div", class_="table__airport")
        if not airport_elem:
            return None
        location = airport_elem.get_text(strip=True)

        # Extract airline
        company_elem = element.find("div", class_="table__company")
        airline = company_elem.get_text(strip=True) if company_elem else ""

        # Extract flight number
        flight_elem = element.find("div", class_="table__flight")
        if not flight_elem:
            return None
        flight_number = flight_elem.get_text(strip=True)

        # Extract status
        status_elem = element.find("div", class_="table__status")
        status_text = status_elem.get_text(strip=True) if status_elem else ""
        status = parse_status(status_text)

        # Extract expected time
        expected_elem = element.find("div", class_="table__time_expected")
        expected_time = None
        if expected_elem:
            expected_text = expected_elem.get_text(strip=True)
            # Expected time might be in the element or in status text
            if expected_text and ":" in expected_text:
                expected_time = expected_text
            elif status == FlightStatus.DELAYED:
                # Try to extract time from status text
                expected_time = _extract_time_from_status(status_text)

        # Calculate delay
        delay_minutes = _calculate_delay(scheduled_time, expected_time)

        # Create flight object
        flight = Flight(
            scheduled_time=scheduled_time,
            expected_time=expected_time,
            origin=location if direction == DIRECTION_ARRIVALS else None,
            destination=location if direction == DIRECTION_DEPARTURES else None,
            airline=airline,
            flight_number=flight_number,
            status=status,
            delay_minutes=delay_minutes,
            direction=direction,
        )

        return flight

    except (AttributeError, ValueError) as err:
        _LOGGER.debug("Failed to parse flight element: %s", err)
        return None


def _parse_html(html: str, direction: str) -> list[Flight]:
    """Parse HTML and extract flights.

    Args:
        html: Raw HTML content
        direction: "arrival" or "departure"

    Returns:
        List of Flight objects
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Find all flight elements
        flight_elements = soup.find_all("div", class_="table__element")

        if not flight_elements:
            _LOGGER.warning("No flight elements found in HTML")
            return []

        # Parse each flight
        flights = []
        for element in flight_elements:
            flight = _parse_flight_element(element, direction)
            if flight:
                flights.append(flight)

        _LOGGER.debug("Parsed %d flights for %s", len(flights), direction)
        return flights

    except Exception as err:
        _LOGGER.error("Failed to parse HTML: %s", err)
        return []


async def fetch_flights(
    session: aiohttp.ClientSession,
    direction: str,
) -> list[Flight]:
    """Fetch and parse flights from airport website.

    Args:
        session: aiohttp ClientSession
        direction: "arrivals" or "departures"

    Returns:
        List of Flight objects

    Raises:
        aiohttp.ClientError: On HTTP errors
        asyncio.TimeoutError: On timeout
    """
    url = URL_ARRIVALS if direction == DIRECTION_ARRIVALS else URL_DEPARTURES

    _LOGGER.debug("Fetching flights from %s", url)

    headers = {"User-Agent": USER_AGENT}

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                html = await response.text()

                flights = _parse_html(html, direction)
                _LOGGER.info(
                    "Successfully fetched %d %s", len(flights), direction
                )
                return flights

    except asyncio.TimeoutError:
        _LOGGER.error("Timeout fetching %s from %s", direction, url)
        raise
    except aiohttp.ClientError as err:
        _LOGGER.error("HTTP error fetching %s: %s", direction, err)
        raise
    except Exception as err:
        _LOGGER.error("Unexpected error fetching %s: %s", direction, err)
        raise


async def fetch_all_flights(
    session: aiohttp.ClientSession,
    fetch_arrivals: bool = True,
    fetch_departures: bool = True,
) -> dict[str, list[Flight]]:
    """Fetch both arrivals and departures.

    Args:
        session: aiohttp ClientSession
        fetch_arrivals: Whether to fetch arrivals
        fetch_departures: Whether to fetch departures

    Returns:
        Dictionary with 'arrivals' and 'departures' keys containing flight lists
    """
    tasks = []
    keys = []

    if fetch_arrivals:
        tasks.append(fetch_flights(session, DIRECTION_ARRIVALS))
        keys.append(DIRECTION_ARRIVALS)

    if fetch_departures:
        tasks.append(fetch_flights(session, DIRECTION_DEPARTURES))
        keys.append(DIRECTION_DEPARTURES)

    if not tasks:
        return {DIRECTION_ARRIVALS: [], DIRECTION_DEPARTURES: []}

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                _LOGGER.error("Failed to fetch %s: %s", key, result)
                output[key] = []
            else:
                output[key] = result

        # Ensure both keys exist
        if DIRECTION_ARRIVALS not in output:
            output[DIRECTION_ARRIVALS] = []
        if DIRECTION_DEPARTURES not in output:
            output[DIRECTION_DEPARTURES] = []

        return output

    except Exception as err:
        _LOGGER.error("Unexpected error in fetch_all_flights: %s", err)
        return {DIRECTION_ARRIVALS: [], DIRECTION_DEPARTURES: []}
