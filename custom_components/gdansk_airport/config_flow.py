"""Config flow for Gdańsk Airport integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AIRLINES_FILTER,
    CONF_DESTINATIONS_FILTER,
    CONF_DIRECTION,
    CONF_EVENTS_ALL_FLIGHTS,
    CONF_EVENTS_ENABLED,
    CONF_HIDE_CANCELLED,
    CONF_HIDE_LANDED,
    CONF_MAX_FLIGHTS,
    CONF_SCAN_INTERVAL,
    CONF_TIME_WINDOW,
    CONF_TRACKED_FLIGHTS,
    DEFAULT_HIDE_CANCELLED,
    DEFAULT_HIDE_LANDED,
    DEFAULT_MAX_FLIGHTS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_WINDOW,
    DIRECTION_ARRIVALS,
    DIRECTION_BOTH,
    DIRECTION_DEPARTURES,
    DOMAIN,
    MAX_MAX_FLIGHTS,
    MAX_SCAN_INTERVAL,
    MAX_TIME_WINDOW,
    MIN_MAX_FLIGHTS,
    MIN_SCAN_INTERVAL,
    MIN_TIME_WINDOW,
    URL_ARRIVALS,
)
from .parser import fetch_flights

_LOGGER = logging.getLogger(__name__)


async def validate_connection(hass: HomeAssistant) -> bool:
    """Validate that we can connect to the airport website.

    Args:
        hass: Home Assistant instance

    Returns:
        True if connection is successful

    Raises:
        aiohttp.ClientError: On connection error
    """
    session = async_get_clientsession(hass)

    try:
        # Try to fetch arrivals page
        _LOGGER.debug("Validating connection to airport website: %s", URL_ARRIVALS)
        await asyncio.wait_for(
            fetch_flights(session, DIRECTION_ARRIVALS),
            timeout=30.0,
        )
        _LOGGER.debug("Connection validation successful")
        return True
    except asyncio.TimeoutError as err:
        _LOGGER.error(
            "Timeout connecting to airport website %s after 30s: %s",
            URL_ARRIVALS,
            type(err).__name__,
        )
        raise
    except aiohttp.ClientError as err:
        _LOGGER.error(
            "Failed to connect to airport website %s: %s - %s",
            URL_ARRIVALS,
            type(err).__name__,
            str(err) or "No error message available",
        )
        raise
    except Exception as err:
        _LOGGER.exception(
            "Unexpected error connecting to airport website %s: %s",
            URL_ARRIVALS,
            type(err).__name__,
        )
        raise


class GdanskAirportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gdańsk Airport."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate connection
                await validate_connection(self.hass)

                # Create unique ID based on direction
                await self.async_set_unique_id(
                    f"gdansk_airport_{user_input[CONF_DIRECTION]}"
                )
                self._abort_if_unique_id_configured()

                # Create entry
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Gdańsk Airport"),
                    data=user_input,
                )

            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout connecting to airport website during setup")
                errors["base"] = "timeout_connect"
            except aiohttp.ClientError as err:
                _LOGGER.warning("Client error connecting to airport website: %s", type(err).__name__)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during config flow setup")
                errors["base"] = "unknown"

        # Show form
        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default="Gdańsk Airport"): str,
                vol.Required(CONF_DIRECTION, default=DIRECTION_BOTH): vol.In(
                    {
                        DIRECTION_ARRIVALS: "Arrivals",
                        DIRECTION_DEPARTURES: "Departures",
                        DIRECTION_BOTH: "Both",
                    }
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GdanskAirportOptionsFlow:
        """Get the options flow for this handler.

        Args:
            config_entry: Config entry

        Returns:
            Options flow handler
        """
        return GdanskAirportOptionsFlow(config_entry)


class GdanskAirportOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Gdańsk Airport."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.

        Args:
            config_entry: Config entry
        """
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options.

        Args:
            user_input: User input data

        Returns:
            Flow result
        """
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current options or defaults
        options = self.config_entry.options

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MAX_FLIGHTS,
                    default=options.get(CONF_MAX_FLIGHTS, DEFAULT_MAX_FLIGHTS),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_MAX_FLIGHTS, max=MAX_MAX_FLIGHTS),
                ),
                vol.Optional(
                    CONF_TIME_WINDOW,
                    default=options.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_TIME_WINDOW, max=MAX_TIME_WINDOW),
                ),
                vol.Optional(
                    CONF_HIDE_LANDED,
                    default=options.get(CONF_HIDE_LANDED, DEFAULT_HIDE_LANDED),
                ): bool,
                vol.Optional(
                    CONF_HIDE_CANCELLED,
                    default=options.get(CONF_HIDE_CANCELLED, DEFAULT_HIDE_CANCELLED),
                ): bool,
                vol.Optional(
                    CONF_AIRLINES_FILTER,
                    default=options.get(CONF_AIRLINES_FILTER, ""),
                ): str,
                vol.Optional(
                    CONF_DESTINATIONS_FILTER,
                    default=options.get(CONF_DESTINATIONS_FILTER, ""),
                ): str,
                # Events configuration (v2)
                vol.Optional(
                    CONF_EVENTS_ENABLED,
                    default=options.get(CONF_EVENTS_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_EVENTS_ALL_FLIGHTS,
                    default=options.get(CONF_EVENTS_ALL_FLIGHTS, False),
                ): bool,
                vol.Optional(
                    CONF_TRACKED_FLIGHTS,
                    default=options.get(CONF_TRACKED_FLIGHTS, ""),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
