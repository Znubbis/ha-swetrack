"""Switches for SweTrack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SwetrackError
from .coordinator import SwetrackConfigEntry, SwetrackCoordinator
from .entity import SwetrackEntity, nested, setup_device_entities

ALREADY_QUEUED = "already queued"


@dataclass(frozen=True, kw_only=True)
class SwetrackSwitchDescription(SwitchEntityDescription):
    """Describes a SweTrack switch."""

    # Key of the block in /devices/info, and the key of the current value in it.
    block: str
    current_key: str
    # Field name in /device/edit.
    edit_field: str


SWITCHES: tuple[SwetrackSwitchDescription, ...] = (
    SwetrackSwitchDescription(
        key="relay_switch",
        translation_key="relay",
        block="relay_switch",
        current_key="value",
        edit_field="relayswitch",
        # The relay usually cuts the vehicle's ignition or fuel. It has to be
        # enabled on purpose so it can't be flipped by accident.
        entity_registry_enabled_default=False,
    ),
    SwetrackSwitchDescription(
        key="powersaving_switch",
        translation_key="powersaving_mode",
        block="powersaving_mode",
        current_key="current",
        edit_field="powersavingswitch",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwetrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SweTrack switches."""
    coordinator = entry.runtime_data

    def _add(device_id: str, device: dict[str, Any]) -> None:
        # Features a model lacks come back as null; skip those.
        async_add_entities(
            SwetrackSwitch(coordinator, device_id, description)
            for description in SWITCHES
            if nested(device, description.block, description.current_key) is not None
        )

    entry.async_on_unload(setup_device_entities(coordinator, _add))


class SwetrackSwitch(SwetrackEntity, SwitchEntity):
    """A setting that is queued and applied when the tracker is next awake."""

    entity_description: SwetrackSwitchDescription

    def __init__(
        self,
        coordinator: SwetrackCoordinator,
        device_id: str,
        description: SwetrackSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def _block(self) -> dict[str, Any]:
        block = self.device.get(self.entity_description.block)
        return block if isinstance(block, dict) else {}

    @property
    def _pending(self) -> bool:
        block = self._block
        return bool(block.get("pending")) and isinstance(block.get("new_mode"), bool)

    @property
    def is_on(self) -> bool | None:
        """Show the queued value while a change waits for the tracker."""
        block = self._block
        if self._pending:
            return block["new_mode"]
        return block.get(self.entity_description.current_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Tell whether the shown state is still waiting to be applied."""
        return {"pending": self._pending}

    async def _async_set(self, value: bool) -> None:
        field = self.entity_description.edit_field
        try:
            result = await self.coordinator.api.async_edit_device(
                self._device_id, {field: value}
            )
        except SwetrackError as err:
            raise HomeAssistantError(
                f"SweTrack did not accept the change: {err}"
            ) from err
        skipped = (result.get("skipped_fields") or {}).get(field)
        if skipped and skipped != ALREADY_QUEUED:
            raise HomeAssistantError(f"SweTrack skipped the change: {skipped}")
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Queue switching on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Queue switching off."""
        await self._async_set(False)
