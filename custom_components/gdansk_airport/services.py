"""Services for Gdańsk Airport integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import CONF_TRACKED_FLIGHTS, DOMAIN
from .coordinator import GdanskAirportCoordinator

_LOGGER = logging.getLogger(__name__)

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
        flight_number = call.data["flight_number"].strip().upper()

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

            # Add to coordinator's tracked flights
            coordinator._tracked_flights.add(flight_number)

            # Update config entry options
            new_options = dict(entry.options)
            tracked_set = coordinator._tracked_flights
            new_options[CONF_TRACKED_FLIGHTS] = ", ".join(sorted(tracked_set))

            hass.config_entries.async_update_entry(entry, options=new_options)

            _LOGGER.info("Added flight %s to tracking", flight_number)

    async def handle_untrack_flight(call: ServiceCall) -> None:
        """Handle untrack_flight service call.

        Args:
            call: Service call data
        """
        flight_number = call.data["flight_number"].strip().upper()

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

            # Remove from coordinator's tracked flights
            coordinator._tracked_flights.discard(flight_number)

            # Update config entry options
            new_options = dict(entry.options)
            tracked_set = coordinator._tracked_flights
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
