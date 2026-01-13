"""The Gdańsk Airport integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DIRECTION, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import GdanskAirportCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gdańsk Airport from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if setup was successful
    """
    # Get configuration
    direction = entry.data.get(CONF_DIRECTION)
    scan_interval_minutes = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = timedelta(minutes=scan_interval_minutes)

    # Create coordinator
    coordinator = GdanskAirportCoordinator(
        hass,
        direction=direction,
        scan_interval=scan_interval,
    )

    # Update options if available
    if entry.options:
        coordinator.update_options(entry.options)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # Set up services (only once for all instances)
    if len(hass.data[DOMAIN]) == 1:
        await async_setup_services(hass)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options.

    Args:
        hass: Home Assistant instance
        entry: Config entry
    """
    coordinator: GdanskAirportCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.update_options(entry.options)
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if unload was successful
    """
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove coordinator and cleanup
    if unload_ok:
        coordinator: GdanskAirportCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

        # Close curl_cffi session
        await coordinator.session.close()

        hass.data[DOMAIN].pop(entry.entry_id)

        # Unload services when last instance is removed
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)

    return unload_ok
