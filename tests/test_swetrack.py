"""Tests for the SweTrack integration."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.swetrack.api import (
    SwetrackAuthError,
    SwetrackConnectionError,
    SwetrackRateLimitError,
)
from custom_components.swetrack.const import DOMAIN

from .conftest import DEVICE


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="user_abc", data={CONF_API_TOKEN: "token"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_user_flow(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """A valid key creates an entry; a rejected key shows an error first."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_api.async_get_account.side_effect = SwetrackAuthError("nope")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api.async_get_account.side_effect = SwetrackConnectionError("down")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "good"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_api.async_get_account.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: " good "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_TOKEN: "good"}
    assert result["result"].unique_id == "user_abc"


async def test_entities(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """The tracker and its sensors get the values from the API."""
    await _setup(hass)

    tracker = hass.states.get("device_tracker.test_atv")
    assert tracker is not None
    assert tracker.attributes["latitude"] == 59.3293
    assert tracker.attributes["longitude"] == 18.0686

    assert hass.states.get("sensor.test_atv_battery").state == "87"
    assert hass.states.get("sensor.test_atv_external_voltage").state == "13.2"
    assert hass.states.get("sensor.test_atv_speed").state == "12"
    assert (
        hass.states.get("sensor.test_atv_last_position").state
        == "2026-01-08T10:10:00+00:00"
    )
    assert hass.states.get("binary_sensor.test_atv_ignition").state == "off"
    assert hass.states.get("binary_sensor.test_atv_external_power").state == "on"
    assert hass.states.get("binary_sensor.test_atv_connectivity").state == "off"
    assert hass.states.get("switch.test_atv_power_saving_mode").state == "on"
    assert hass.states.get("binary_sensor.test_atv_power_saving_mode") is None
    # The relay switch must be enabled on purpose.
    assert hass.states.get("switch.test_atv_relay") is None
    assert hass.states.get("binary_sensor.test_atv_relay").state == "off"
    assert (
        hass.states.get("sensor.swetrack_api_api_calls_remaining_today").state == "990"
    )


async def test_unsupported_features_are_skipped(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """A battery-only tracker gets no vehicle entities."""
    mock_api.async_get_devices.return_value = [
        {
            **DEVICE,
            "battery": {
                "internal": 50,
                "external_voltage": None,
                "external_power_supply": None,
            },
            "ignition": {"value": None},
            "relay_switch": {"value": None},
        }
    ]
    await _setup(hass)

    assert hass.states.get("sensor.test_atv_battery").state == "50"
    assert hass.states.get("sensor.test_atv_external_voltage") is None
    assert hass.states.get("binary_sensor.test_atv_ignition") is None
    assert hass.states.get("binary_sensor.test_atv_relay") is None


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """A rejected token puts the entry in reauth instead of retrying forever."""
    mock_api.async_get_devices.side_effect = SwetrackAuthError("nope")
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="user_abc", data={CONF_API_TOKEN: "token"}
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["step_id"] for flow in flows] == ["reauth_confirm"]

    mock_api.async_get_devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_API_TOKEN: "new"}
    )
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_TOKEN] == "new"


async def test_rate_limit_stops_polling_until_reset(
    hass: HomeAssistant, mock_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """After a 429 no more calls are made until the quota resets."""

    async def _tick(seconds: int) -> None:
        freezer.tick(timedelta(seconds=seconds))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    await _setup(hass)
    assert mock_api.async_get_devices.call_count == 1

    reset_at = dt_util.utcnow() + timedelta(minutes=10)
    mock_api.async_get_devices.side_effect = SwetrackRateLimitError("full", reset_at)

    await _tick(121)
    assert mock_api.async_get_devices.call_count == 2
    assert hass.states.get("sensor.test_atv_battery").state == STATE_UNAVAILABLE

    # Still inside the blocked window: polled, but the API is not called.
    mock_api.async_get_devices.side_effect = None
    await _tick(121)
    await _tick(121)
    assert mock_api.async_get_devices.call_count == 2

    # Past the reset time the next poll calls the API again.
    await _tick(300)
    assert mock_api.async_get_devices.call_count == 3
    assert hass.states.get("sensor.test_atv_battery").state == "87"


def _event(event_id: str, event_type: str, age: timedelta) -> dict:
    return {
        "id": event_id,
        "device": {"id": DEVICE["id"], "name": "Test ATV"},
        "type": event_type,
        "description": event_type,
        "eventtime": (dt_util.utcnow() - age).isoformat(),
        "position": {"exists": True, "latitude": 59.1, "longitude": 18.1},
        "additionalinfo": {"reason": {"value": "Vibration Wake-up"}},
    }


async def test_events(
    hass: HomeAssistant, mock_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """New events fire once, and only after the tracker has reported something."""

    async def _poll() -> None:
        freezer.tick(timedelta(seconds=121))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = "event.test_atv_event"
    mock_api.async_get_events.return_value = [
        _event("event_old", "ignitionOff", timedelta(minutes=1))
    ]
    await _setup(hass)
    # Events that already existed at startup only seed the seen list.
    assert mock_api.async_get_events.call_count == 1
    assert hass.states.get(entity_id).state == "unknown"

    # Nothing new from the tracker: no events call.
    await _poll()
    assert mock_api.async_get_events.call_count == 1

    # The tracker wakes up: fetch, fire the fresh one, skip seen and stale ones.
    mock_api.async_get_devices.return_value = [
        {**DEVICE, "status": "online", "last_update": "2026-01-08T11:00:00.000Z"}
    ]
    mock_api.async_get_events.return_value = [
        _event("event_new", "vibration", timedelta(seconds=30)),
        _event("event_stale", "geofenceExit", timedelta(hours=2)),
        _event("event_old", "ignitionOff", timedelta(minutes=3)),
    ]
    await _poll()
    assert mock_api.async_get_events.call_count == 2
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "vibration"
    assert state.attributes["latitude"] == 59.1
    assert state.attributes["reason"] == "Vibration Wake-up"
    fired_at = state.state

    # Same data again: nothing is fetched or fired twice.
    await _poll()
    assert mock_api.async_get_events.call_count == 2
    assert hass.states.get(entity_id).state == fired_at

    # Unknown types still fire, as "other" with the raw type kept.
    mock_api.async_get_devices.return_value = [
        {**DEVICE, "status": "online", "last_update": "2026-01-08T11:05:00.000Z"}
    ]
    mock_api.async_get_events.return_value = [
        _event("event_x", "somethingNew", timedelta(seconds=5))
    ]
    await _poll()
    state = hass.states.get(entity_id)
    assert state.attributes["event_type"] == "other"
    assert state.attributes["swetrack_type"] == "somethingNew"


async def test_events_skipped_when_quota_is_needed_for_positions(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """With too few calls left for the rest of the day, events are not fetched."""
    mock_api.usage = {
        "remaining_requests": 100,
        "reset_at": (dt_util.utcnow() + timedelta(hours=12)).isoformat(),
    }
    await _setup(hass)
    assert mock_api.async_get_events.call_count == 0
    assert hass.states.get("device_tracker.test_atv") is not None


async def test_switch(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Switching queues the change and shows the queued value while pending."""
    await _setup(hass)
    entity_id = "switch.test_atv_power_saving_mode"

    mock_api.async_get_devices.return_value = [
        {
            **DEVICE,
            "powersaving_mode": {"current": True, "new_mode": False, "pending": True},
        }
    ]
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    mock_api.async_edit_device.assert_awaited_once_with(
        DEVICE["id"], {"powersavingswitch": False}
    )
    state = hass.states.get(entity_id)
    assert state.state == "off"
    assert state.attributes["pending"] is True

    mock_api.async_edit_device.return_value = {
        "skipped_fields": {"powersavingswitch": "function not supported by this device"}
    }
    with pytest.raises(HomeAssistantError, match="not supported"):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": entity_id}, blocking=True
        )


async def test_old_power_saving_binary_sensor_is_removed(
    hass: HomeAssistant, mock_api: AsyncMock, entity_registry: er.EntityRegistry
) -> None:
    """Upgrading from 0.1.0 does not leave the replaced entity behind."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="user_abc", data={CONF_API_TOKEN: "token"}
    )
    entry.add_to_hass(hass)
    old = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{DEVICE['id']}_powersaving_mode",
        config_entry=entry,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(old.entity_id) is None
