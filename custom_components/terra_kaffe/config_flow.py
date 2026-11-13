"""Config flow for Terra Kaffe integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import TerraKaffeAPI, TerraKaffeAPIError, TerraKaffeAuthError
from .const import CONF_REFRESH_TOKEN, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_credentials(
    hass: HomeAssistant, username: str, password: str
) -> tuple[TerraKaffeAPI, dict[str, Any]]:
    """Validate the credentials and return API client and account/device info."""
    api = TerraKaffeAPI(hass)
    try:
        await api.async_login(username, password)
        accounts = await api.async_get_accounts()
        if not accounts:
            raise CannotConnect("No accounts found")

        # Get the first account
        account = accounts[0]
        account_id = account.get("accountId") or account.get("id")
        if not account_id:
            raise CannotConnect("Invalid account data")

        # Get devices for the account
        devices = await api.async_get_devices(account_id)
        if not devices:
            raise CannotConnect("No devices found")

        return api, {
            "account_id": account_id,
            "devices": devices,
        }
    except TerraKaffeAuthError as err:
        raise InvalidAuth from err
    except TerraKaffeAPIError as err:
        raise CannotConnect from err


class TerraKaffeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Terra Kaffe."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._account_id: str | None = None
        self._devices: list[dict[str, Any]] = []
        self._api: TerraKaffeAPI | None = None
        self._username: str | None = None
        self._password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._username = user_input[CONF_USERNAME]
                self._password = user_input[CONF_PASSWORD]
                self._api, info = await validate_credentials(
                    self.hass, self._username, self._password
                )
                self._account_id = info["account_id"]
                self._devices = info["devices"]

                # If only one device, configure it automatically
                if len(self._devices) == 1:
                    return await self._create_entry(self._devices[0])

                return await self.async_step_device()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input["device_id"]
            # Find the selected device
            device = next(
                (d for d in self._devices if d.get("deviceId") == device_id), None
            )
            if not device:
                errors["base"] = "invalid_device"
            else:
                return await self._create_entry(device)

        # Build device selection schema
        device_options = {
            device.get("deviceId"): (
                device.get("friendlyName")
                or device.get("name")
                or f"Terra Kaffe {device.get('deviceId', 'unknown')[:8]}"
            )
            for device in self._devices
        }

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): vol.In(device_options),
                }
            ),
            errors=errors,
        )

    async def _create_entry(self, device: dict[str, Any]) -> ConfigFlowResult:
        """Create the config entry for a device."""
        device_id = device.get("deviceId")
        if not device_id:
            raise CannotConnect("Invalid device data")

        # Use device ID as unique ID
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        device_name = (
            device.get("friendlyName")
            or device.get("name")
            or f"Terra Kaffe {device_id[:8]}"
        )

        return self.async_create_entry(
            title=device_name,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_REFRESH_TOKEN: self._api.refresh_token if self._api else None,
                "account_id": self._account_id,
                "device_id": device_id,
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                api = TerraKaffeAPI(self.hass)
                await api.async_login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                accounts = await api.async_get_accounts()
                account_id = accounts[0]["accountId"] if accounts else None
            except TerraKaffeAuthError:
                errors["base"] = "invalid_auth"
            except TerraKaffeAPIError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if account_id != reauth_entry.data.get("account_id"):
                    errors["base"] = "wrong_account"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data_updates={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_REFRESH_TOKEN: api.refresh_token,
                        },
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_USERNAME: reauth_entry.data.get(CONF_USERNAME)},
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
