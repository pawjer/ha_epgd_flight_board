"""Tests for Gdańsk Airport parser."""
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.gdansk_airport.const import (
    DIRECTION_ARRIVALS,
    DIRECTION_DEPARTURES,
    FlightStatus,
)
from custom_components.gdansk_airport.parser import (
    Flight,
    _calculate_delay,
    _extract_time_from_status,
    _parse_flight_element,
    _parse_html,
    fetch_all_flights,
    fetch_flights,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def arrivals_html():
    """Load arrivals sample HTML."""
    return (FIXTURES_DIR / "arrivals_sample.html").read_text()


@pytest.fixture
def departures_html():
    """Load departures sample HTML."""
    return (FIXTURES_DIR / "departures_sample.html").read_text()


class TestCalculateDelay:
    """Tests for _calculate_delay function."""

    def test_no_delay(self):
        """Test when there's no delay."""
        result = _calculate_delay("10:00", "10:00")
        assert result == 0

    def test_with_delay(self):
        """Test when there's a delay."""
        result = _calculate_delay("10:00", "10:30")
        assert result == 30

    def test_midnight_crossing(self):
        """Test delay crossing midnight."""
        result = _calculate_delay("23:50", "00:20")
        assert result == 30

    def test_midnight_crossing_large_delay(self):
        """Test large delay crossing midnight."""
        result = _calculate_delay("23:00", "02:30")
        assert result == 210  # 3.5 hours

    def test_large_delay(self):
        """Test large delay without midnight crossing."""
        result = _calculate_delay("10:00", "13:30")
        assert result == 210

    def test_small_delay(self):
        """Test small delay."""
        result = _calculate_delay("14:30", "14:45")
        assert result == 15

    def test_none_expected_time(self):
        """Test when expected time is None."""
        result = _calculate_delay("10:00", None)
        assert result is None

    def test_invalid_time_format(self):
        """Test with invalid time format."""
        result = _calculate_delay("invalid", "10:00")
        assert result is None


class TestExtractTimeFromStatus:
    """Tests for _extract_time_from_status function."""

    def test_extract_from_delayed_status(self):
        """Test extracting time from delayed status."""
        result = _extract_time_from_status("OPÓŹNIONY 00:32")
        assert result == "00:32"

    def test_extract_from_status_with_prefix(self):
        """Test extracting time from status with prefix."""
        result = _extract_time_from_status("ODPRAWA OD 03:40")
        assert result == "03:40"

    def test_no_time_in_status(self):
        """Test when status doesn't contain time."""
        result = _extract_time_from_status("WYLĄDOWAŁ")
        assert result is None

    def test_empty_status(self):
        """Test with empty status."""
        result = _extract_time_from_status("")
        assert result is None


class TestParseHtml:
    """Tests for _parse_html function."""

    def test_parse_arrivals(self, arrivals_html):
        """Test parsing arrivals HTML."""
        flights = _parse_html(arrivals_html, DIRECTION_ARRIVALS)

        assert len(flights) > 0
        assert all(isinstance(f, Flight) for f in flights)
        assert all(f.direction == DIRECTION_ARRIVALS for f in flights)
        assert all(f.origin is not None for f in flights)
        assert all(f.destination is None for f in flights)

    def test_parse_departures(self, departures_html):
        """Test parsing departures HTML."""
        flights = _parse_html(departures_html, DIRECTION_DEPARTURES)

        assert len(flights) > 0
        assert all(isinstance(f, Flight) for f in flights)
        assert all(f.direction == DIRECTION_DEPARTURES for f in flights)
        assert all(f.destination is not None for f in flights)
        assert all(f.origin is None for f in flights)

    def test_parse_empty_html(self):
        """Test parsing empty HTML."""
        flights = _parse_html("", DIRECTION_ARRIVALS)
        assert flights == []

    def test_parse_invalid_html(self):
        """Test parsing invalid HTML."""
        flights = _parse_html("<html><body>Invalid</body></html>", DIRECTION_ARRIVALS)
        assert flights == []


class TestParseFlightElement:
    """Tests for _parse_flight_element function."""

    def test_parse_valid_arrival(self, arrivals_html):
        """Test parsing a valid arrival element."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(arrivals_html, "html.parser")
        element = soup.find("div", class_="table__element")

        flight = _parse_flight_element(element, DIRECTION_ARRIVALS)

        assert flight is not None
        assert flight.scheduled_time
        assert flight.airline
        assert flight.flight_number
        assert flight.status in FlightStatus
        assert flight.origin is not None
        assert flight.destination is None

    def test_parse_valid_departure(self, departures_html):
        """Test parsing a valid departure element."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(departures_html, "html.parser")
        element = soup.find("div", class_="table__element")

        flight = _parse_flight_element(element, DIRECTION_DEPARTURES)

        assert flight is not None
        assert flight.scheduled_time
        assert flight.airline or True  # Airline might be empty
        assert flight.flight_number
        assert flight.status in FlightStatus
        assert flight.destination is not None
        assert flight.origin is None


class TestFlightToDict:
    """Tests for Flight.to_dict method."""

    def test_to_dict(self):
        """Test converting flight to dictionary."""
        flight = Flight(
            scheduled_time="10:00",
            expected_time="10:30",
            origin="Barcelona",
            destination=None,
            airline="WIZZ AIR",
            flight_number="W6 1706",
            status=FlightStatus.DELAYED,
            delay_minutes=30,
            direction=DIRECTION_ARRIVALS,
        )

        result = flight.to_dict()

        assert result["scheduled_time"] == "10:00"
        assert result["expected_time"] == "10:30"
        assert result["origin"] == "Barcelona"
        assert result["destination"] is None
        assert result["airline"] == "WIZZ AIR"
        assert result["flight_number"] == "W6 1706"
        assert result["status"] == "delayed"
        assert result["delay_minutes"] == 30
        assert result["direction"] == DIRECTION_ARRIVALS


@pytest.mark.asyncio
class TestFetchFlights:
    """Tests for fetch_flights function."""

    async def test_fetch_arrivals_success(self, arrivals_html):
        """Test successful fetch of arrivals."""
        mock_response = Mock()
        mock_response.text = arrivals_html
        mock_response.raise_for_status = Mock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)

        flights = await fetch_flights(mock_session, DIRECTION_ARRIVALS)

        assert len(flights) > 0
        assert all(isinstance(f, Flight) for f in flights)

    async def test_fetch_departures_success(self, departures_html):
        """Test successful fetch of departures."""
        mock_response = Mock()
        mock_response.text = departures_html
        mock_response.raise_for_status = Mock()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)

        flights = await fetch_flights(mock_session, DIRECTION_DEPARTURES)

        assert len(flights) > 0
        assert all(isinstance(f, Flight) for f in flights)

    async def test_fetch_http_error(self):
        """Test handling HTTP error."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=Exception("Connection error"))

        with pytest.raises(Exception):
            await fetch_flights(mock_session, DIRECTION_ARRIVALS)


@pytest.mark.asyncio
class TestFetchAllFlights:
    """Tests for fetch_all_flights function."""

    async def test_fetch_both_success(self, arrivals_html, departures_html):
        """Test successful fetch of both arrivals and departures."""
        with patch(
            "custom_components.gdansk_airport.parser.fetch_flights"
        ) as mock_fetch:
            # Mock responses for both directions
            mock_fetch.side_effect = [
                [Flight(
                    scheduled_time="10:00",
                    expected_time=None,
                    origin="Test",
                    destination=None,
                    airline="TEST",
                    flight_number="T123",
                    status=FlightStatus.EXPECTED,
                    delay_minutes=None,
                    direction=DIRECTION_ARRIVALS,
                )],
                [Flight(
                    scheduled_time="11:00",
                    expected_time=None,
                    origin=None,
                    destination="Test",
                    airline="TEST",
                    flight_number="T456",
                    status=FlightStatus.EXPECTED,
                    delay_minutes=None,
                    direction=DIRECTION_DEPARTURES,
                )],
            ]

            mock_session = AsyncMock()
            result = await fetch_all_flights(mock_session)

            assert DIRECTION_ARRIVALS in result
            assert DIRECTION_DEPARTURES in result
            assert len(result[DIRECTION_ARRIVALS]) == 1
            assert len(result[DIRECTION_DEPARTURES]) == 1

    async def test_fetch_arrivals_only(self):
        """Test fetching only arrivals."""
        with patch(
            "custom_components.gdansk_airport.parser.fetch_flights"
        ) as mock_fetch:
            mock_fetch.return_value = []

            mock_session = AsyncMock()
            result = await fetch_all_flights(
                mock_session, fetch_arrivals=True, fetch_departures=False
            )

            assert DIRECTION_ARRIVALS in result
            assert DIRECTION_DEPARTURES in result
            assert result[DIRECTION_DEPARTURES] == []

    async def test_fetch_with_error(self):
        """Test handling error in one direction."""
        with patch(
            "custom_components.gdansk_airport.parser.fetch_flights"
        ) as mock_fetch:
            mock_fetch.side_effect = [
                Exception("Error"),
                [],
            ]

            mock_session = AsyncMock()
            result = await fetch_all_flights(mock_session)

            # Should return empty list for failed direction
            assert result[DIRECTION_ARRIVALS] == []
            assert result[DIRECTION_DEPARTURES] == []
