"""Parser for Gdańsk Airport flight board."""
from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import Timeout as CurlTimeout

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

# Retry configuration
MAX_RETRIES = 2
RETRY_DELAY = 3  # Initial retry delay in seconds


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

    Note: expected_time from airport website always indicates a delay (or on-time).
    The website does not provide expected_time for early arrivals.
    If expected < scheduled in simple comparison, it means midnight crossing.

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

        # Handle midnight crossing (e.g., 23:50 -> 00:20)
        # If expected < scheduled, it means the delay caused midnight crossing
        if expected < scheduled:
            expected += timedelta(days=1)

        delay = (expected - scheduled).total_seconds() / 60
        return int(delay)
    except (ValueError, AttributeError) as err:
        _LOGGER.debug("Could not calculate delay: %s", err)
        return None


def _parse_status_from_remarks(remarks: str, remarks_status: int, direction: str) -> FlightStatus:
    """Parse flight status from remarks and remarksStatus code.

    Args:
        remarks: Remarks text (e.g., "wylądował", "oczekiwany 14:31")
        remarks_status: Status code from API
        direction: Flight direction (arrivals/departures)

    Returns:
        FlightStatus enum

    remarksStatus codes observed:
    1 = expected/on-time
    2 = landed/departed (completed)
    3 = delayed (oczekiwany with time != scheduled)
    4 = cancelled (observed in other data)
    5 = scheduled/no status yet
    """
    # Map remarksStatus codes to flight status
    if remarks_status == 2:
        # Completed flight
        return FlightStatus.LANDED if direction == DIRECTION_ARRIVALS else FlightStatus.DEPARTED
    elif remarks_status == 4:
        return FlightStatus.CANCELLED
    elif remarks_status == 3:
        # Delayed (expected time differs from scheduled)
        return FlightStatus.DELAYED
    elif remarks_status == 1:
        return FlightStatus.EXPECTED
    elif remarks_status == 5:
        # Scheduled, no specific status
        return FlightStatus.EXPECTED
    elif remarks_status == 7:
        return FlightStatus.GATE_CLOSED
    elif remarks_status == 10:
        return FlightStatus.CHECK_IN

    # Fallback: try to parse from remarks text
    if remarks:
        parsed = parse_status(remarks)
        if parsed != FlightStatus.UNKNOWN:
            return parsed

    return FlightStatus.UNKNOWN


def _extract_json_from_react_props(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Extract JSON data from Symfony UX React component props.

    The website embeds flight data in a React component as HTML-encoded JSON:
    <div data-symfony--ux-react--react-props-value="{&quot;arrivals&quot;:...}">

    Args:
        soup: BeautifulSoup parsed HTML

    Returns:
        Decoded JSON data or None if not found
    """
    try:
        # Find the React component container
        react_container = soup.find("div", {"data-controller": "symfony--ux-react--react"})

        if not react_container:
            _LOGGER.warning("React component container not found")
            return None

        # Extract the props data attribute
        props_data = react_container.get("data-symfony--ux-react--react-props-value")

        if not props_data:
            _LOGGER.warning("React props data attribute not found")
            return None

        # Decode HTML entities
        decoded_data = html.unescape(props_data)

        # Parse JSON
        json_data = json.loads(decoded_data)

        return json_data

    except json.JSONDecodeError as err:
        _LOGGER.error("Failed to parse JSON from React props: %s", err)
        return None
    except Exception as err:
        _LOGGER.error("Error extracting JSON from React props: %s", err)
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


def _parse_flight_from_json(flight_data: dict[str, Any], direction: str) -> Flight | None:
    """Parse a single flight from JSON data.

    Args:
        flight_data: Dictionary with flight data from JSON
        direction: "arrivals" or "departures"

    Returns:
        Flight object or None if parsing fails

    JSON structure:
    {
        "origin": "PAFOS",
        "remarks": "wylądował",
        "dateTime": "2026-02-16T13:20:00+01:00",
        "carrierName": "RYANAIR",
        "expectedDateTime": "2026-02-16T14:09:00+01:00",
        "flight": "FR 3554",
        "remarksStatus": 2
    }
    """
    try:
        # Extract required fields
        flight_number = flight_data.get("flight")
        if not flight_number:
            return None

        airline = flight_data.get("carrierName", "")
        location = flight_data.get("origin" if direction == DIRECTION_ARRIVALS else "destination", "")

        # Parse scheduled time from ISO datetime
        date_time_str = flight_data.get("dateTime")
        if not date_time_str:
            return None

        # Parse ISO format: "2026-02-16T13:20:00+01:00"
        date_time = datetime.fromisoformat(date_time_str)
        scheduled_time = date_time.strftime("%H:%M")

        # Parse expected time if present
        expected_time = None
        expected_date_time_str = flight_data.get("expectedDateTime")
        if expected_date_time_str:
            expected_date_time = datetime.fromisoformat(expected_date_time_str)
            expected_time = expected_date_time.strftime("%H:%M")

        # Parse status
        remarks = flight_data.get("remarks", "")
        remarks_status = flight_data.get("remarksStatus", 5)
        status = _parse_status_from_remarks(remarks, remarks_status, direction)

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

    except (ValueError, KeyError) as err:
        _LOGGER.debug("Failed to parse flight from JSON: %s", err)
        return None


def _parse_flight_element(element: Any, direction: str) -> Flight | None:
    """Parse a single flight element from HTML (legacy method).

    Args:
        element: BeautifulSoup element representing a flight row
        direction: "arrival" or "departure"

    Returns:
        Flight object or None if parsing fails

    NOTE: This is the old parsing method for HTML elements.
    The website now uses JSON data, so this is kept as fallback only.
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


def _parse_html(html_content: str, direction: str) -> list[Flight]:
    """Parse HTML and extract flights.

    Tries to extract JSON data from React props first (new format),
    falls back to HTML scraping if not found (legacy format).

    Args:
        html_content: Raw HTML content
        direction: "arrivals" or "departures"

    Returns:
        List of Flight objects
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Try new JSON-based format first
        json_data = _extract_json_from_react_props(soup)

        if json_data:
            _LOGGER.debug("Using JSON data extraction (new format)")

            # Get the flights array for this direction
            flights_key = direction  # "arrivals" or "departures"
            flights_json = json_data.get(flights_key)

            if flights_json is None:
                _LOGGER.warning("No %s data found in JSON", direction)
                return []

            # The flights data might be a JSON string (double-encoded)
            if isinstance(flights_json, str):
                try:
                    flights_data = json.loads(flights_json)
                except json.JSONDecodeError as err:
                    _LOGGER.error("Failed to parse flights JSON string: %s", err)
                    return []
            else:
                flights_data = flights_json

            # Parse each flight from JSON
            flights = []
            for flight_data in flights_data:
                flight = _parse_flight_from_json(flight_data, direction)
                if flight:
                    flights.append(flight)

            _LOGGER.info("Parsed %d flights for %s from JSON", len(flights), direction)
            return flights

        # Fallback to old HTML scraping method
        _LOGGER.debug("Using HTML scraping (legacy format)")
        flight_elements = soup.find_all("div", class_="table__element")

        if not flight_elements:
            _LOGGER.warning("No flight elements found in HTML")
            return []

        # Parse each flight from HTML
        flights = []
        for element in flight_elements:
            flight = _parse_flight_element(element, direction)
            if flight:
                flights.append(flight)

        _LOGGER.debug("Parsed %d flights for %s from HTML", len(flights), direction)
        return flights

    except Exception as err:
        _LOGGER.error("Failed to parse HTML: %s", err)
        return []


async def fetch_flights(
    session: AsyncSession,
    direction: str,
) -> list[Flight]:
    """Fetch and parse flights from airport website with retry logic.

    Args:
        session: curl_cffi AsyncSession
        direction: "arrivals" or "departures"

    Returns:
        List of Flight objects

    Raises:
        Exception: On HTTP errors or timeout after all retries
    """
    url = URL_ARRIVALS if direction == DIRECTION_ARRIVALS else URL_DEPARTURES

    _LOGGER.debug("Fetching flights from %s", url)

    # When using impersonate="chrome120", curl_cffi automatically sets appropriate
    # browser headers. We should NOT override them as it breaks the fingerprinting.
    # Only add headers that aren't part of standard Chrome behavior.
    headers = {
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",  # Prefer Polish
    }

    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            if attempt > 0:
                delay = RETRY_DELAY * (2 ** (attempt - 1))  # Exponential backoff
                _LOGGER.warning(
                    "Retry attempt %d/%d for %s after %d seconds",
                    attempt,
                    MAX_RETRIES,
                    direction,
                    delay,
                )
                await asyncio.sleep(delay)

            # Make request (session already configured with timeout, redirects, verify)
            response = await session.get(url, headers=headers)
            response.raise_for_status()
            html = response.text

            flights = _parse_html(html, direction)
            _LOGGER.info(
                "Successfully fetched %d %s", len(flights), direction
            )
            return flights

        except CurlTimeout as err:
            last_error = err
            _LOGGER.warning("Timeout fetching %s from %s (attempt %d/%d)", direction, url, attempt + 1, MAX_RETRIES + 1)
        except Exception as err:
            last_error = err
            _LOGGER.warning("Error fetching %s (attempt %d/%d): %s", direction, attempt + 1, MAX_RETRIES + 1, err)

    # All retries exhausted
    if last_error:
        _LOGGER.error("Failed to fetch %s after %d attempts: %s", direction, MAX_RETRIES + 1, last_error)
        raise last_error
    else:
        # Should never happen, but handle gracefully
        error_msg = f"Failed to fetch {direction} after {MAX_RETRIES + 1} attempts with no error captured"
        _LOGGER.error(error_msg)
        raise RuntimeError(error_msg)


async def fetch_all_flights(
    session: AsyncSession,
    fetch_arrivals: bool = True,
    fetch_departures: bool = True,
) -> dict[str, list[Flight]]:
    """Fetch both arrivals and departures.

    Args:
        session: curl_cffi AsyncSession
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
