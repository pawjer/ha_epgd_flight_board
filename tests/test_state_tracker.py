"""Tests for flight state tracking."""
import pytest

from custom_components.gdansk_airport.const import FlightStatus
from custom_components.gdansk_airport.parser import Flight
from custom_components.gdansk_airport.state_tracker import (
    FlightStateChange,
    FlightStateTracker,
)


@pytest.fixture
def tracker():
    """Create a FlightStateTracker instance."""
    return FlightStateTracker()


@pytest.fixture
def sample_flight():
    """Create a sample flight."""
    return Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )


def test_get_flight_key(tracker, sample_flight):
    """Test flight key generation."""
    key = tracker.get_flight_key(sample_flight)
    assert key == "LO 123_10:00_arrivals"


def test_get_flight_key_unique_for_different_times(tracker):
    """Test that different scheduled times produce different keys."""
    flight1 = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )
    flight2 = Flight(
        scheduled_time="14:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )

    key1 = tracker.get_flight_key(flight1)
    key2 = tracker.get_flight_key(flight2)

    assert key1 != key2
    assert key1 == "LO 123_10:00_arrivals"
    assert key2 == "LO 123_14:00_arrivals"


def test_detect_changes_no_previous_state(tracker, sample_flight):
    """Test that no changes are detected for new flights."""
    changes = tracker.detect_changes([sample_flight])
    assert len(changes) == 0


def test_detect_changes_status_change(tracker):
    """Test detection of status change."""
    flight = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )

    # First update - no changes
    changes = tracker.detect_changes([flight])
    assert len(changes) == 0

    # Update status to delayed
    flight_updated = Flight(
        scheduled_time="10:00",
        expected_time="10:30",
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.DELAYED,
        delay_minutes=30,
        direction="arrivals",
    )

    changes = tracker.detect_changes([flight_updated])
    assert len(changes) == 1
    change = changes[0]
    assert change.old_status == FlightStatus.EXPECTED
    assert change.new_status == FlightStatus.DELAYED
    assert change.delay_changed is True
    assert change.old_delay is None
    assert change.new_delay == 30
    assert change.flight == flight_updated


def test_detect_changes_delay_change_only(tracker):
    """Test detection of delay change without status change."""
    flight = Flight(
        scheduled_time="10:00",
        expected_time="10:15",
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.DELAYED,
        delay_minutes=15,
        direction="arrivals",
    )

    # First update - no changes
    changes = tracker.detect_changes([flight])
    assert len(changes) == 0

    # Update delay to 30 minutes (status still delayed)
    flight_updated = Flight(
        scheduled_time="10:00",
        expected_time="10:30",
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.DELAYED,
        delay_minutes=30,
        direction="arrivals",
    )

    changes = tracker.detect_changes([flight_updated])
    assert len(changes) == 1
    change = changes[0]
    assert change.old_status == FlightStatus.DELAYED
    assert change.new_status == FlightStatus.DELAYED
    assert change.delay_changed is True
    assert change.old_delay == 15
    assert change.new_delay == 30


def test_detect_changes_status_to_landed(tracker):
    """Test detection of flight landing."""
    flight = Flight(
        scheduled_time="10:00",
        expected_time="10:30",
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.DELAYED,
        delay_minutes=30,
        direction="arrivals",
    )

    # First update
    tracker.detect_changes([flight])

    # Flight lands
    flight_landed = Flight(
        scheduled_time="10:00",
        expected_time="10:30",
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.LANDED,
        delay_minutes=30,
        direction="arrivals",
    )

    changes = tracker.detect_changes([flight_landed])
    assert len(changes) == 1
    change = changes[0]
    assert change.old_status == FlightStatus.DELAYED
    assert change.new_status == FlightStatus.LANDED
    assert change.delay_changed is False
    assert change.old_delay == 30
    assert change.new_delay == 30


def test_detect_changes_status_to_cancelled(tracker):
    """Test detection of flight cancellation."""
    flight = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )

    # First update
    tracker.detect_changes([flight])

    # Flight cancelled
    flight_cancelled = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.CANCELLED,
        delay_minutes=None,
        direction="arrivals",
    )

    changes = tracker.detect_changes([flight_cancelled])
    assert len(changes) == 1
    change = changes[0]
    assert change.old_status == FlightStatus.EXPECTED
    assert change.new_status == FlightStatus.CANCELLED


def test_detect_changes_multiple_flights(tracker):
    """Test detection with multiple flights."""
    flight1 = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )
    flight2 = Flight(
        scheduled_time="11:00",
        expected_time=None,
        origin="London",
        destination=None,
        airline="WIZZ AIR",
        flight_number="W6 456",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )

    # First update
    tracker.detect_changes([flight1, flight2])

    # Update both flights
    flight1_updated = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.LANDED,
        delay_minutes=None,
        direction="arrivals",
    )
    flight2_updated = Flight(
        scheduled_time="11:00",
        expected_time="11:20",
        origin="London",
        destination=None,
        airline="WIZZ AIR",
        flight_number="W6 456",
        status=FlightStatus.DELAYED,
        delay_minutes=20,
        direction="arrivals",
    )

    changes = tracker.detect_changes([flight1_updated, flight2_updated])
    assert len(changes) == 2

    # Verify both changes detected
    change_dict = {change.flight.flight_number: change for change in changes}
    assert "LO 123" in change_dict
    assert "W6 456" in change_dict

    # Verify LO 123 change
    change1 = change_dict["LO 123"]
    assert change1.old_status == FlightStatus.EXPECTED
    assert change1.new_status == FlightStatus.LANDED

    # Verify W6 456 change
    change2 = change_dict["W6 456"]
    assert change2.old_status == FlightStatus.EXPECTED
    assert change2.new_status == FlightStatus.DELAYED
    assert change2.delay_changed is True
    assert change2.new_delay == 20


def test_detect_changes_no_change(tracker, sample_flight):
    """Test that no changes are detected when state is the same."""
    # First update
    tracker.detect_changes([sample_flight])

    # Second update with same state
    changes = tracker.detect_changes([sample_flight])
    assert len(changes) == 0


def test_detect_changes_flight_disappears(tracker):
    """Test that disappeared flights don't cause issues."""
    flight1 = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin="Warsaw",
        destination=None,
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )
    flight2 = Flight(
        scheduled_time="11:00",
        expected_time=None,
        origin="London",
        destination=None,
        airline="WIZZ AIR",
        flight_number="W6 456",
        status=FlightStatus.EXPECTED,
        delay_minutes=None,
        direction="arrivals",
    )

    # First update with both flights
    tracker.detect_changes([flight1, flight2])

    # Second update with only flight2 (flight1 landed and removed)
    changes = tracker.detect_changes([flight2])
    assert len(changes) == 0

    # Verify that tracker only tracks flight2 now
    assert len(tracker._states) == 1
    key = tracker.get_flight_key(flight2)
    assert key in tracker._states


def test_detect_changes_departure_flight(tracker):
    """Test with departure flight."""
    flight = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin=None,
        destination="Warsaw",
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.CHECK_IN,
        delay_minutes=None,
        direction="departures",
    )

    # First update
    tracker.detect_changes([flight])

    # Update to boarding
    flight_boarding = Flight(
        scheduled_time="10:00",
        expected_time=None,
        origin=None,
        destination="Warsaw",
        airline="LOT",
        flight_number="LO 123",
        status=FlightStatus.BOARDING,
        delay_minutes=None,
        direction="departures",
    )

    changes = tracker.detect_changes([flight_boarding])
    assert len(changes) == 1
    change = changes[0]
    assert change.old_status == FlightStatus.CHECK_IN
    assert change.new_status == FlightStatus.BOARDING
