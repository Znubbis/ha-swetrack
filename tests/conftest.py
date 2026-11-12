"""Fixtures for the SweTrack tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

USER = {"id": "user_abc", "username": "tester", "email": "t@example.com"}

DEVICE: dict[str, Any] = {
    "id": "device_abc123",
    "name": "Test ATV",
    "uniqueid": "100000000001",
    "last_update": "2026-01-08T10:15:30.000Z",
    "status": "offline",
    "model": {"id": 14, "model": "Lite+ G2"},
    "position_info": {
        "latitude": 59.3293,
        "longitude": 18.0686,
        "datetime": "2026-01-08T10:10:00.000Z",
    },
    "battery": {
        "internal": 87,
        "external_voltage": 13.2,
        "external_power_supply": True,
    },
    "speed": {
        "current_speed": {"value": 12, "unit": "km/h"},
        "speed_limit": {"value": None, "unit": "km/h"},
    },
    "powersaving_mode": {"current": True, "new_mode": None, "pending": False},
    "ignition": {"value": False},
    "relay_switch": {"value": False, "new_mode": None, "pending": False},
}

USAGE = {
    "daily_limit": 1000,
    "request_count": 10,
    "remaining_requests": 990,
    "reset_at": "2026-01-09T00:00:00.000Z",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Replace the API client in both the integration and the config flow."""
    with (
        patch("custom_components.swetrack.SwetrackApi", autospec=True) as cls,
        patch("custom_components.swetrack.config_flow.SwetrackApi", new=cls),
    ):
        api = cls.return_value
        api.usage = dict(USAGE)
        api.async_get_account.return_value = dict(USER)
        api.async_get_devices.return_value = [DEVICE]
        api.async_get_events.return_value = []
        api.async_edit_device.return_value = {
            "updated_fields": {},
            "skipped_fields": {},
        }
        yield api
