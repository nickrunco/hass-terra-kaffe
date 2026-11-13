"""API client for the Terra Kaffe (Afero) cloud."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AFERO_CLIENT_ID, AFERO_SERVICE_URL, AFERO_TOKEN_URL

_LOGGER = logging.getLogger(__name__)

# Refresh the access token this many seconds before it actually expires.
# Afero access tokens are short-lived (~120 s), so keep the margin modest.
TOKEN_EXPIRY_MARGIN = 30


class TerraKaffeAPIError(Exception):
    """Base exception for Terra Kaffe API errors."""


class TerraKaffeAuthError(TerraKaffeAPIError):
    """Authentication error (bad credentials or expired session)."""


class TerraKaffeAPI:
    """Afero API client for Terra Kaffe."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self.hass = hass
        self._session = session or async_get_clientsession(hass)
        self._base_url = AFERO_SERVICE_URL
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float | None = None  # time.monotonic() deadline
        self._account_id: str | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._auth_lock = asyncio.Lock()
        self._timeout = ClientTimeout(total=30, connect=10)
        # Called with the new refresh token whenever it changes, so the
        # integration can persist it in the config entry.
        self.on_refresh_token_update: Callable[[str], None] | None = None

    # ------------------------------------------------------------------
    # Token / credential handling
    # ------------------------------------------------------------------

    def set_credentials(self, username: str, password: str) -> None:
        """Store credentials so the client can log in again on its own."""
        self._username = username
        self._password = password

    def set_tokens(
        self,
        access_token: str | None,
        refresh_token: str | None = None,
        expires_in: int | None = None,
    ) -> None:
        """Set the authentication tokens."""
        self._access_token = access_token or None
        if refresh_token and refresh_token != self._refresh_token:
            self._refresh_token = refresh_token
            if self.on_refresh_token_update:
                self.on_refresh_token_update(refresh_token)
        if expires_in:
            margin = min(TOKEN_EXPIRY_MARGIN, expires_in // 2)
            self._token_expiry = time.monotonic() + expires_in - margin
        else:
            self._token_expiry = None

    @property
    def refresh_token(self) -> str | None:
        """Return the refresh token."""
        return self._refresh_token

    @property
    def _token_is_valid(self) -> bool:
        if not self._access_token:
            return False
        return self._token_expiry is None or time.monotonic() < self._token_expiry

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        """POST to the OAuth token endpoint and return the JSON body."""
        try:
            async with self._session.post(
                AFERO_TOKEN_URL,
                data={"client_id": AFERO_CLIENT_ID, **data},
                timeout=self._timeout,
            ) as response:
                if response.status in (400, 401):
                    try:
                        body = await response.json(content_type=None)
                    except (ValueError, aiohttp.ContentTypeError):
                        body = {}
                    message = (body or {}).get("error_description") or (
                        body or {}
                    ).get("error", "Authentication failed")
                    raise TerraKaffeAuthError(message)
                if response.status >= 400:
                    text = await response.text()
                    raise TerraKaffeAPIError(
                        f"Auth server returned {response.status}: {text[:200]}"
                    )
                token_data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TerraKaffeAPIError(f"Cannot reach Afero auth server: {err}") from err

        if not token_data.get("access_token"):
            raise TerraKaffeAPIError("No access token in auth response")
        self.set_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
        )
        return token_data

    async def async_login(self, username: str, password: str) -> dict[str, Any]:
        """Log in with email/password (OAuth resource-owner password grant)."""
        self.set_credentials(username, password)
        token_data = await self._token_request(
            {"grant_type": "password", "username": username, "password": password}
        )
        _LOGGER.debug("Login successful")
        await self._fetch_account_id()
        return token_data

    async def async_refresh_access_token(self) -> dict[str, Any]:
        """Get a new access token using the refresh token."""
        if not self._refresh_token:
            raise TerraKaffeAuthError("No refresh token available")
        return await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": self._refresh_token}
        )

    async def _reauthenticate(self) -> None:
        """Get a fresh access token: refresh first, then fall back to password."""
        if self._refresh_token:
            try:
                await self.async_refresh_access_token()
            except TerraKaffeAuthError:
                _LOGGER.debug("Refresh token rejected, falling back to password")
            else:
                return
        if self._username and self._password:
            await self._token_request(
                {
                    "grant_type": "password",
                    "username": self._username,
                    "password": self._password,
                }
            )
            return
        raise TerraKaffeAuthError("Session expired and no credentials available")

    async def _ensure_token_valid(self, force: bool = False) -> None:
        """Make sure we hold a usable access token."""
        async with self._auth_lock:
            if force or not self._token_is_valid:
                await self._reauthenticate()

    # ------------------------------------------------------------------
    # Generic request helper
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an authenticated request, retrying once after a 401."""
        await self._ensure_token_valid()
        for attempt in (1, 2):
            try:
                async with self._session.request(
                    method,
                    f"{self._base_url}{path}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                    timeout=self._timeout,
                    **kwargs,
                ) as response:
                    if response.status == 401 and attempt == 1:
                        _LOGGER.debug("Access token rejected, re-authenticating")
                        await self._ensure_token_valid(force=True)
                        continue
                    if response.status in (401, 403):
                        raise TerraKaffeAuthError(
                            f"Not authorized ({response.status}) for {path}"
                        )
                    if response.status >= 400:
                        text = await response.text()
                        message = text[:500]
                        try:
                            body = await response.json(content_type=None)
                            if isinstance(body, dict):
                                message = body.get("message") or body.get(
                                    "error", message
                                )
                        except (ValueError, aiohttp.ContentTypeError):
                            pass
                        raise TerraKaffeAPIError(
                            f"{method} {path} failed ({response.status}): {message}"
                        )
                    if response.status == 204:
                        return None
                    text = await response.text()
                    if not text:
                        return None
                    try:
                        return await response.json(content_type=None)
                    except ValueError:
                        return text
            except (aiohttp.ClientError, TimeoutError) as err:
                raise TerraKaffeAPIError(
                    f"Cannot reach Terra Kaffe cloud ({method} {path}): {err}"
                ) from err
        raise TerraKaffeAuthError("Not authorized after re-authentication")

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    async def _fetch_account_id(self) -> None:
        """Fetch the account ID from /v1/users/me."""
        user_data = await self._request("GET", "/v1/users/me")
        account_access = (user_data or {}).get("accountAccess", [])
        if account_access:
            self._account_id = account_access[0]["account"]["accountId"]

    async def async_get_accounts(self) -> list[dict[str, Any]]:
        """Return the user's account (Afero exposes one per user)."""
        if not self._account_id:
            await self._fetch_account_id()
        if self._account_id:
            return [{"accountId": self._account_id, "id": self._account_id}]
        raise TerraKaffeAPIError(
            "Failed to retrieve account information. Please try re-authenticating."
        )

    async def async_get_devices(self, account_id: str) -> list[dict[str, Any]]:
        """Get devices for an account."""
        data = await self._request(
            "GET",
            f"/v1/accounts/{account_id}/devices",
            params={"expansions": "state,attributes,timezone,tags"},
        )
        if isinstance(data, list):
            return data
        return (data or {}).get("items", (data or {}).get("devices", []))

    async def async_get_device_state(
        self, account_id: str, device_id: str
    ) -> dict[str, Any]:
        """Get device state and attributes."""
        return await self._request(
            "GET",
            f"/v1/accounts/{account_id}/devices/{device_id}",
            params={"expansions": "state,attributes,extendedData"},
        )

    async def async_set_attribute(
        self,
        account_id: str,
        device_id: str,
        attribute_id: int,
        value: Any,
    ) -> None:
        """Write a device attribute.

        Afero expects attribute values as strings, even numeric ones, wrapped
        in an ``attribute_write`` request.
        """
        _LOGGER.debug("Setting attribute %s on device %s", attribute_id, device_id)
        result = await self._request(
            "POST",
            f"/v1/accounts/{account_id}/devices/{device_id}/requests",
            json=[
                {"type": "attribute_write", "attrId": attribute_id, "value": str(value)}
            ],
        )
        # Afero answers 202 with a per-request status list; surface failures.
        if isinstance(result, list):
            for item in result:
                status = str(item.get("status", "SUCCESS")).upper()
                if status not in ("SUCCESS", "ACCEPTED", "QUEUED", "PENDING"):
                    raise TerraKaffeAPIError(
                        f"Machine rejected write to attribute {attribute_id}: {item}"
                    )

    async def async_test_connection(self) -> bool:
        """Test the API connection."""
        try:
            await self.async_get_accounts()
        except TerraKaffeAPIError:
            return False
        return True
