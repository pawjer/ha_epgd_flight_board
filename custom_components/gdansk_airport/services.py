"""Services for Gdańsk Airport integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import CONF_TRACKED_FLIGHTS, DOMAIN
from .coordinator import GdanskAirportCoordinator

_LOGGER = logging.getLogger(__name__)

# Flight number validation pattern (e.g., "W6 1706", "LO 123", "FR1234")
FLIGHT_NUMBER_PATTERN = re.compile(r"^[A-Z0-9]{2}\s*\d{1,4}[A-Z]?$", re.IGNORECASE)

# Service names
SERVICE_TRACK_FLIGHT = "track_flight"
SERVICE_UNTRACK_FLIGHT = "untrack_flight"

# Service schemas
TRACK_FLIGHT_SCHEMA = vol.Schema(
    {
        vol.Required("flight_number"): cv.string,
    }
)

UNTRACK_FLIGHT_SCHEMA = vol.Schema(
    {
        vol.Required("flight_number"): cv.string,
    }
)


def validate_flight_number(flight_number: str) -> bool:
    """Validate flight number format.

    Args:
        flight_number: Flight number to validate

    Returns:
        True if valid format, False otherwise
    """
    return bool(FLIGHT_NUMBER_PATTERN.match(flight_number.strip()))


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Gdańsk Airport integration.

    Args:
        hass: Home Assistant instance
    """

    async def handle_track_flight(call: ServiceCall) -> None:
        """Handle track_flight service call.

        Args:
            call: Service call data
        """
        flight_number = call.data["flight_number"].strip()

        # Validate flight number format
        if not validate_flight_number(flight_number):
            _LOGGER.error(
                "Invalid flight number format: %s (expected format: 'W6 1706', 'LO 123')",
                flight_number,
            )
            return

        flight_number = flight_number.upper()

        # Get all config entries for this integration
        entries = hass.config_entries.async_entries(DOMAIN)

        if not entries:
            _LOGGER.warning("No Gdańsk Airport integrations configured")
            return

        # Add to all configured integrations
        for entry in entries:
            coordinator: GdanskAirportCoordinator = hass.data[DOMAIN][entry.entry_id][
                "coordinator"
            ]

            # Add to coordinator's tracked flights (using public method)
            coordinator.add_tracked_flight(flight_number)

            # Update config entry options
            new_options = dict(entry.options)
            tracked_set = coordinator.get_tracked_flights()
            new_options[CONF_TRACKED_FLIGHTS] = ", ".join(sorted(tracked_set))

            hass.config_entries.async_update_entry(entry, options=new_options)

            _LOGGER.info("Added flight %s to tracking", flight_number)

    async def handle_untrack_flight(call: ServiceCall) -> None:
        """Handle untrack_flight service call.

        Args:
            call: Service call data
        """
        flight_number = call.data["flight_number"].strip()

        # Validate flight number format
        if not validate_flight_number(flight_number):
            _LOGGER.error(
                "Invalid flight number format: %s (expected format: 'W6 1706', 'LO 123')",
                flight_number,
            )
            return

        flight_number = flight_number.upper()

        # Get all config entries for this integration
        entries = hass.config_entries.async_entries(DOMAIN)

        if not entries:
            _LOGGER.warning("No Gdańsk Airport integrations configured")
            return

        # Remove from all configured integrations
        for entry in entries:
            coordinator: GdanskAirportCoordinator = hass.data[DOMAIN][entry.entry_id][
                "coordinator"
            ]

            # Remove from coordinator's tracked flights (using public method)
            coordinator.remove_tracked_flight(flight_number)

            # Update config entry options
            new_options = dict(entry.options)
            tracked_set = coordinator.get_tracked_flights()
            new_options[CONF_TRACKED_FLIGHTS] = ", ".join(sorted(tracked_set))

            hass.config_entries.async_update_entry(entry, options=new_options)

            _LOGGER.info("Removed flight %s from tracking", flight_number)

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRACK_FLIGHT,
        handle_track_flight,
        schema=TRACK_FLIGHT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UNTRACK_FLIGHT,
        handle_untrack_flight,
        schema=UNTRACK_FLIGHT_SCHEMA,
    )

    _LOGGER.debug("Services registered: %s, %s", SERVICE_TRACK_FLIGHT, SERVICE_UNTRACK_FLIGHT)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for Gdańsk Airport integration.

    Args:
        hass: Home Assistant instance
    """
    hass.services.async_remove(DOMAIN, SERVICE_TRACK_FLIGHT)
    hass.services.async_remove(DOMAIN, SERVICE_UNTRACK_FLIGHT)

    _LOGGER.debug("Services unloaded")
