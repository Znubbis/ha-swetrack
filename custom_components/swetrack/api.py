"""Minimal async client for the SweTrack public API."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import aiohttp

from .const import API_BASE_URL, REQUEST_TIMEOUT

AUTH_ERROR_CODES = {"UNAUTHORIZED", "TOKEN_NOT_FOUND"}


class SwetrackError(Exception):
    """Base error for the SweTrack API."""


class SwetrackConnectionError(SwetrackError):
    """The API could not be reached or returned something unreadable."""


class SwetrackAuthError(SwetrackError):
    """The API token was rejected."""


class SwetrackRateLimitError(SwetrackError):
    """The daily request quota is used up."""

    def __init__(self, message: str, reset_at: datetime | None = None) -> None:
        """Store when the quota resets, if the API told us."""
        super().__init__(message)
        self.reset_at = reset_at


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class SwetrackApi:
    """Talks to the SweTrack public REST API with a bearer token."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        """Initialize the client."""
        self._session = session
        self._token = token.strip()
        # Latest meta.api_usage block: daily_limit, request_count,
        # remaining_requests, reset_at.
        self.usage: dict[str, Any] = {}

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.request(
                    method, f"{API_BASE_URL}{path}", headers=headers, json=payload
                )
                status = response.status
                try:
                    body = await response.json(content_type=None)
                except ValueError:
                    body = None
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SwetrackConnectionError(f"Error talking to SweTrack: {err}") from err

        if not isinstance(body, dict):
            raise SwetrackConnectionError(f"Unexpected response (HTTP {status})")

        usage = (body.get("meta") or {}).get("api_usage")
        if isinstance(usage, dict):
            self.usage = usage

        if status < 400 and body.get("success"):
            return body.get("data") or {}

        error = body.get("error") or {}
        code = error.get("code")
        message = error.get("message") or f"HTTP {status}"
        if status == 401 or code in AUTH_ERROR_CODES:
            raise SwetrackAuthError(message)
        if status == 429:
            raise SwetrackRateLimitError(
                message, _parse_datetime(self.usage.get("reset_at"))
            )
        raise SwetrackError(f"{code or status}: {message}")

    async def async_get_account(self) -> dict[str, Any]:
        """Return the account's user block (id, username, email, language)."""
        data = await self._request("GET", "/account/info")
        return data.get("user") or {}

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return all devices with their latest position and status."""
        data = await self._request("GET", "/devices/info")
        return [
            device
            for device in data.get("devices") or []
            if isinstance(device, dict) and device.get("id")
        ]
