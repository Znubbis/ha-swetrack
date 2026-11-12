"""Sensors for SweTrack."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SwetrackConfigEntry, SwetrackCoordinator
from .entity import SwetrackAccountEntity, SwetrackEntity, nested, setup_device_entities


def _timestamp(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


@dataclass(frozen=True, kw_only=True)
class SwetrackSensorDescription(SensorEntityDescription):
    """Describes a SweTrack sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    # Sensors that only some tracker models support are created only when the
    # API reports a value for them.
    optional: bool = False


SENSORS: tuple[SwetrackSensorDescription, ...] = (
    SwetrackSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: nested(d, "battery", "internal"),
        optional=True,
    ),
    SwetrackSensorDescription(
        key="external_voltage",
        translation_key="external_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: nested(d, "battery", "external_voltage"),
        optional=True,
    ),
    SwetrackSensorDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: nested(d, "speed", "current_speed", "value"),
    ),
    SwetrackSensorDescription(
        key="position_time",
        translation_key="position_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _timestamp(nested(d, "position_info", "datetime")),
    ),
    SwetrackSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _timestamp(d.get("last_update")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwetrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SweTrack sensors."""
    coordinator = entry.runtime_data
    async_add_entities([SwetrackRequestsRemainingSensor(coordinator)])

    def _add(device_id: str, device: dict[str, Any]) -> None:
        async_add_entities(
            SwetrackSensor(coordinator, device_id, description)
            for description in SENSORS
            if not description.optional or description.value_fn(device) is not None
        )

    entry.async_on_unload(setup_device_entities(coordinator, _add))


class SwetrackSensor(SwetrackEntity, SensorEntity):
    """A value reported by a tracker."""

    entity_description: SwetrackSensorDescription

    def __init__(
        self,
        coordinator: SwetrackCoordinator,
        device_id: str,
        description: SwetrackSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.device)


class SwetrackRequestsRemainingSensor(SwetrackAccountEntity, SensorEntity):
    """API calls left of today's quota."""

    _attr_translation_key = "requests_remaining"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SwetrackCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "requests_remaining")

    @property
    def native_value(self) -> int | None:
        """Return the remaining calls."""
        return self.coordinator.api.usage.get("remaining_requests")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the daily limit and when it resets."""
        usage = self.coordinator.api.usage
        return {
            "daily_limit": usage.get("daily_limit"),
            "reset_at": usage.get("reset_at"),
        }
