"""Sensor platform for Gdańsk Airport integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DIRECTION_ARRIVALS,
    DIRECTION_BOTH,
    DIRECTION_DEPARTURES,
    DOMAIN,
    SENSOR_ARRIVALS,
    SENSOR_DEPARTURES,
    SENSOR_NEXT_ARRIVAL,
    SENSOR_NEXT_DEPARTURE,
)
from .coordinator import GdanskAirportCoordinator
from .parser import Flight

_LOGGER = logging.getLogger(__name__)


@dataclass
class GdanskAirportSensorEntityDescription(SensorEntityDescription):
    """Describes Gdańsk Airport sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    should_create_fn: Callable[[str], bool] | None = None


SENSOR_TYPES: tuple[GdanskAirportSensorEntityDescription, ...] = (
    GdanskAirportSensorEntityDescription(
        key=SENSOR_ARRIVALS,
        translation_key=SENSOR_ARRIVALS,
        name="Arrivals",
        icon="mdi:airplane-landing",
        native_unit_of_measurement="flights",
        value_fn=lambda data: len(data.get(DIRECTION_ARRIVALS, [])),
        attributes_fn=lambda data: {
            "flights": [
                f.to_dict() for f in data.get(DIRECTION_ARRIVALS, [])
            ],
            "last_updated": data.get("last_updated"),
            "next_flight": data.get("next_arrival").to_dict()
            if data.get("next_arrival")
            else None,
            "data_source": data.get("data_source", "unknown"),
            "cache_age_seconds": data.get("cache_age_seconds"),
            "cache_age_minutes": data.get("cache_age_minutes"),
        },
        should_create_fn=lambda direction: direction
        in (DIRECTION_ARRIVALS, DIRECTION_BOTH),
    ),
    GdanskAirportSensorEntityDescription(
        key=SENSOR_DEPARTURES,
        translation_key=SENSOR_DEPARTURES,
        name="Departures",
        icon="mdi:airplane-takeoff",
        native_unit_of_measurement="flights",
        value_fn=lambda data: len(data.get(DIRECTION_DEPARTURES, [])),
        attributes_fn=lambda data: {
            "flights": [
                f.to_dict() for f in data.get(DIRECTION_DEPARTURES, [])
            ],
            "last_updated": data.get("last_updated"),
            "next_flight": data.get("next_departure").to_dict()
            if data.get("next_departure")
            else None,
            "data_source": data.get("data_source", "unknown"),
            "cache_age_seconds": data.get("cache_age_seconds"),
            "cache_age_minutes": data.get("cache_age_minutes"),
        },
        should_create_fn=lambda direction: direction
        in (DIRECTION_DEPARTURES, DIRECTION_BOTH),
    ),
    GdanskAirportSensorEntityDescription(
        key=SENSOR_NEXT_ARRIVAL,
        translation_key=SENSOR_NEXT_ARRIVAL,
        name="Next Arrival",
        icon="mdi:airplane-landing",
        value_fn=lambda data: (
            data.get("next_arrival").scheduled_time
            if data.get("next_arrival")
            else None
        ),
        attributes_fn=lambda data: (
            data.get("next_arrival").to_dict() if data.get("next_arrival") else {}
        ),
        should_create_fn=lambda direction: direction
        in (DIRECTION_ARRIVALS, DIRECTION_BOTH),
    ),
    GdanskAirportSensorEntityDescription(
        key=SENSOR_NEXT_DEPARTURE,
        translation_key=SENSOR_NEXT_DEPARTURE,
        name="Next Departure",
        icon="mdi:airplane-takeoff",
        value_fn=lambda data: (
            data.get("next_departure").scheduled_time
            if data.get("next_departure")
            else None
        ),
        attributes_fn=lambda data: (
            data.get("next_departure").to_dict() if data.get("next_departure") else {}
        ),
        should_create_fn=lambda direction: direction
        in (DIRECTION_DEPARTURES, DIRECTION_BOTH),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gdańsk Airport sensors based on a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    coordinator: GdanskAirportCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Get direction from config entry
    direction = entry.data.get("direction", DIRECTION_BOTH)

    # Create sensors based on direction
    entities = [
        GdanskAirportSensor(coordinator, description, entry)
        for description in SENSOR_TYPES
        if description.should_create_fn and description.should_create_fn(direction)
    ]

    async_add_entities(entities)


class GdanskAirportSensor(CoordinatorEntity[GdanskAirportCoordinator], SensorEntity):
    """Representation of a Gdańsk Airport sensor."""

    entity_description: GdanskAirportSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GdanskAirportCoordinator,
        description: GdanskAirportSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator
            description: Sensor entity description
            entry: Config entry
        """
        super().__init__(coordinator)
        self.entity_description = description

        # Set unique ID
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Gdańsk Airport"),
            "manufacturer": "Port Lotniczy Gdańsk",
            "model": "Flight Board",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor.

        Returns:
            Sensor value
        """
        if not self.coordinator.data:
            return None

        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator.data)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes.

        Returns:
            Dictionary of attributes
        """
        if not self.coordinator.data:
            return {}

        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.coordinator.data)

        return {}

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Returns:
            True if available, False otherwise
        """
        return self.coordinator.last_update_success and self.coordinator.data is not None
