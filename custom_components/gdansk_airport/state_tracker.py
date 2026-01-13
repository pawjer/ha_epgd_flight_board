"""Flight state tracking for detecting changes between updates."""
from dataclasses import dataclass

from .const import FlightStatus
from .parser import Flight


@dataclass
class FlightStateChange:
    """Represents a detected change in flight state."""

    flight: Flight
    old_status: FlightStatus
    new_status: FlightStatus
    delay_changed: bool = False
    old_delay: int | None = None
    new_delay: int | None = None


class FlightStateTracker:
    """Tracks flight states between updates to detect changes."""

    def __init__(self):
        """Initialize the state tracker."""
        self._states: dict[str, tuple[FlightStatus, int | None]] = {}

    def get_flight_key(self, flight: Flight) -> str:
        """Generate unique key for flight.

        Args:
            flight: Flight object

        Returns:
            Unique string key combining flight number, scheduled time, and direction
        """
        return f"{flight.flight_number}_{flight.scheduled_time}_{flight.direction}"

    def detect_changes(self, flights: list[Flight]) -> list[FlightStateChange]:
        """Detect changes in flight states compared to previous update.

        Args:
            flights: List of current flights

        Returns:
            List of FlightStateChange objects for flights that changed
        """
        changes = []
        new_states = {}

        for flight in flights:
            key = self.get_flight_key(flight)
            new_states[key] = (flight.status, flight.delay_minutes)

            if key in self._states:
                old_status, old_delay = self._states[key]

                # Check for status change
                if old_status != flight.status:
                    changes.append(
                        FlightStateChange(
                            flight=flight,
                            old_status=old_status,
                            new_status=flight.status,
                            delay_changed=old_delay != flight.delay_minutes,
                            old_delay=old_delay,
                            new_delay=flight.delay_minutes,
                        )
                    )
                # Check for delay change only (status same)
                elif old_delay != flight.delay_minutes:
                    changes.append(
                        FlightStateChange(
                            flight=flight,
                            old_status=old_status,
                            new_status=flight.status,
                            delay_changed=True,
                            old_delay=old_delay,
                            new_delay=flight.delay_minutes,
                        )
                    )

        # Update tracked states
        self._states = new_states

        return changes
