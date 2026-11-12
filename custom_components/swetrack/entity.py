"""Shared entity helpers for SweTrack."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SwetrackCoordinator


def nested(data: dict[str, Any], *keys: str) -> Any:
    """Return data[k1][k2]... or None when any level is missing."""
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


class SwetrackEntity(CoordinatorEntity[SwetrackCoordinator]):
    """An entity that belongs to one tracker."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SwetrackCoordinator, device_id: str, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        device = self.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("name"),
            manufacturer=MANUFACTURER,
            model=nested(device, "model", "model"),
            serial_number=device.get("uniqueid"),
        )

    @property
    def device(self) -> dict[str, Any]:
        """Latest data for this tracker."""
        return self.coordinator.data.get(self._device_id, {})

    @property
    def available(self) -> bool:
        """Available while the tracker is still on the account.

        A sleeping tracker reports "offline" most of the time; its last known
        values are still valid, so that does not make the entities unavailable.
        """
        return super().available and self._device_id in self.coordinator.data


class SwetrackAccountEntity(CoordinatorEntity[SwetrackCoordinator]):
    """An entity that belongs to the account / API itself."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SwetrackCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="SweTrack API",
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )


def setup_device_entities(
    coordinator: SwetrackCoordinator,
    add: Callable[[str, dict[str, Any]], None],
) -> Callable[[], None]:
    """Call add(device_id, device) for every tracker, now and when new ones appear."""
    known: set[str] = set()

    @callback
    def _check() -> None:
        for device_id, device in coordinator.data.items():
            if device_id not in known:
                known.add(device_id)
                add(device_id, device)

    _check()
    return coordinator.async_add_listener(_check)
