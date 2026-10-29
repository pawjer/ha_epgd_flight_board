"""Tests for coordinator ordering and per-direction cache fallback."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from custom_components.gdansk_airport.const import (
    DEFAULT_MAX_CACHE_AGE_HOURS,
    DEFAULT_MAX_FLIGHTS,
    DIRECTION_ARRIVALS,
    DIRECTION_BOTH,
    DIRECTION_DEPARTURES,
    FlightStatus,
)
from custom_components.gdansk_airport.coordinator import GdanskAirportCoordinator
from custom_components.gdansk_airport.parser import Flight


def _flight(time: str, direction: str = DIRECTION_DEPARTURES) -> Flight:
    return Flight(
        scheduled_time=time,
        expected_time=None,
        origin=None,
        destination="X",
        airline="TEST",
        flight_number=f"T{time}",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction=direction,
    )


def _coordinator() -> GdanskAirportCoordinator:
    """Coordinator without hass: only the fields the tested methods use."""
    coord = object.__new__(GdanskAirportCoordinator)
    coord.direction = DIRECTION_BOTH
    coord.session = None
    coord.data = None
    coord._last_successful_update = None
    coord._max_cache_age = timedelta(hours=DEFAULT_MAX_CACHE_AGE_HOURS)
    coord.max_flights = DEFAULT_MAX_FLIGHTS
    coord.time_window_hours = 24
    coord.hide_landed = False
    coord.hide_cancelled = True
    coord.airlines_filter = []
    coord.destinations_filter = []
    coord._process_state_changes = lambda flights: None
    return coord


# Departures as the airport lists them at 14:40: today, then tomorrow morning
FEED = [_flight(t) for t in (
    "11:40 14:20 14:25 14:25 14:50 14:50 15:10 15:15 15:25 15:30 15:45 16:05 16:10 "
    "16:20 16:30 16:55 17:00 17:10 17:15 18:15 18:20 18:25 18:50 19:25 20:10 21:00 "
    "21:30 00:35 05:30 05:40 05:45 06:00 06:00 06:05 06:10 06:15 06:15 06:15 06:20 06:30"
).split()]


def test_filter_keeps_chronological_feed_order():
    """Tomorrow's early flights must not push out today's later ones."""
    with patch("custom_components.gdansk_airport.coordinator.datetime") as dt:
        dt.now.return_value = datetime(2026, 10, 29, 14, 40)
        flights = _coordinator()._filter_flights(FEED)

    times = [f.scheduled_time for f in flights]
    assert len(times) == DEFAULT_MAX_FLIGHTS
    assert times[0] == "11:40"
    assert "00:35" not in times  # 20 nearest flights are all today
    assert times[-1] == "18:15"


def test_next_flight_is_first_upcoming_not_midnight():
    coord = _coordinator()
    flights = [_flight("14:50"), _flight("15:10"), _flight("00:35")]
    assert coord._get_next_flight(flights).scheduled_time == "14:50"


@pytest.mark.asyncio
async def test_failed_direction_keeps_cached_data():
    """One direction timing out must not empty its board."""
    coord = _coordinator()
    cached = [_flight("14:00", DIRECTION_ARRIVALS)]
    coord.data = {DIRECTION_ARRIVALS: cached, DIRECTION_DEPARTURES: []}
    coord._last_successful_update = datetime.now() - timedelta(minutes=5)

    with patch(
        "custom_components.gdansk_airport.coordinator.fetch_all_flights",
        return_value={DIRECTION_ARRIVALS: None, DIRECTION_DEPARTURES: [_flight("15:00")]},
    ):
        data = await coord._async_update_data()

    assert data[DIRECTION_ARRIVALS] == cached
    assert len(data[DIRECTION_DEPARTURES]) == 1
    assert data["data_source"] == "partial_cache"


@pytest.mark.asyncio
async def test_both_directions_failed_uses_full_cache():
    coord = _coordinator()
    coord.data = {DIRECTION_ARRIVALS: [_flight("14:00", DIRECTION_ARRIVALS)],
                  DIRECTION_DEPARTURES: [_flight("15:00")]}
    coord._last_successful_update = datetime.now() - timedelta(minutes=5)

    with patch(
        "custom_components.gdansk_airport.coordinator.fetch_all_flights",
        return_value={DIRECTION_ARRIVALS: None, DIRECTION_DEPARTURES: None},
    ):
        data = await coord._async_update_data()

    assert data["data_source"] == "cache"
    assert len(data[DIRECTION_ARRIVALS]) == 1 and len(data[DIRECTION_DEPARTURES]) == 1
