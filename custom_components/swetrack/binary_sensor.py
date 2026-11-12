"""Binary sensors for SweTrack."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SwetrackConfigEntry, SwetrackCoordinator
from .entity import SwetrackEntity, nested, setup_device_entities


def _online(device: dict[str, Any]) -> bool | None:
    status = device.get("status")
    return status == "online" if isinstance(status, str) else None


@dataclass(frozen=True, kw_only=True)
class SwetrackBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a SweTrack binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[SwetrackBinarySensorDescription, ...] = (
    SwetrackBinarySensorDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_online,
    ),
    SwetrackBinarySensorDescription(
        key="ignition",
        translation_key="ignition",
        value_fn=lambda d: nested(d, "ignition", "value"),
    ),
    SwetrackBinarySensorDescription(
        key="external_power",
        translation_key="external_power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda d: nested(d, "battery", "external_power_supply"),
    ),
    SwetrackBinarySensorDescription(
        key="relay",
        translation_key="relay",
        value_fn=lambda d: nested(d, "relay_switch", "value"),
    ),
    SwetrackBinarySensorDescription(
        key="powersaving_mode",
        translation_key="powersaving_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: nested(d, "powersaving_mode", "current"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwetrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SweTrack binary sensors."""
    coordinator = entry.runtime_data

    def _add(device_id: str, device: dict[str, Any]) -> None:
        # Features a model lacks come back as null; skip those.
        async_add_entities(
            SwetrackBinarySensor(coordinator, device_id, description)
            for description in BINARY_SENSORS
            if description.value_fn(device) is not None
        )

    entry.async_on_unload(setup_device_entities(coordinator, _add))


class SwetrackBinarySensor(SwetrackEntity, BinarySensorEntity):
    """An on/off state reported by a tracker."""

    entity_description: SwetrackBinarySensorDescription

    def __init__(
        self,
        coordinator: SwetrackCoordinator,
        device_id: str,
        description: SwetrackBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        return self.entity_description.value_fn(self.device)
