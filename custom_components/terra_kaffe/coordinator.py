"""Data update coordinator for Terra Kaffe."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TerraKaffeAPI, TerraKaffeAPIError, TerraKaffeAuthError
from .const import (
    ATTR_DEVICE_FRIENDLY_NAME,
    ATTR_DEVICE_MODEL,
    ATTR_DEVICE_OS,
    ATTR_DEVICE_SERIAL,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    UPDATE_INTERVAL_CLOUD,
)

type TerraKaffeConfigEntry = ConfigEntry[TerraKaffeDataUpdateCoordinator]


class TerraKaffeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Terra Kaffe data."""

    config_entry: TerraKaffeConfigEntry
    api: TerraKaffeAPI

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TerraKaffeConfigEntry,
        api: TerraKaffeAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_CLOUD),
        )
        self.api = api
        self.account_id = config_entry.data["account_id"]
        self.device_id = config_entry.data["device_id"]
        # Remote-brew safety: monotonic deadline until which brewing is
        # allowed. None = not armed. Never persisted, so a restart disarms.
        self.brew_armed_until: float | None = None
        self.brew_arm_switch: Any = None  # set by the switch platform

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            state = await self.api.async_get_device_state(
                self.account_id, self.device_id
            )
            # Parse attributes array: [{"id": 1, "value": "3"}, ...] -> {1: "3", ...}
            attributes_array = state.get("attributes", [])
            attributes = {
                attr["id"]: attr.get("value")
                for attr in attributes_array
                if "id" in attr
            }
            return {
                "attributes": attributes,
                "device_state": state.get("deviceState", {}),
                "extended_data": state.get("extendedData", {}),
                "raw_state": state,
            }
        except TerraKaffeAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except TerraKaffeAPIError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        data = self.data or {}
        attributes = data.get("attributes", {})
        extended_data = data.get("extended_data", {})

        # Get device info from attributes
        serial = attributes.get(ATTR_DEVICE_SERIAL) or self.device_id
        model = attributes.get(ATTR_DEVICE_MODEL) or "TK-02"
        sw_version = attributes.get(ATTR_DEVICE_OS)
        friendly_name = attributes.get(ATTR_DEVICE_FRIENDLY_NAME)

        # Use friendly name if set, otherwise use serial
        name = friendly_name if friendly_name else f"Terra Kaffe {serial}"

        # Get MAC addresses from extendedData if available
        wifi_mac = extended_data.get("wifiMac")
        ble_mac = extended_data.get("bleMac")

        # Format MAC addresses using Home Assistant's format_mac function
        connections = set()
        if wifi_mac:
            # Format: "c4d8d54d2bfc" -> "c4:d8:d5:4d:2b:fc"
            formatted_mac = ":".join(
                wifi_mac[i : i + 2] for i in range(0, len(wifi_mac), 2)
            )
            connections.add((dr.CONNECTION_NETWORK_MAC, dr.format_mac(formatted_mac)))
        if ble_mac:
            # Format: "c4d8d54d2bfe" -> "c4:d8:d5:4d:2b:fe"
            formatted_mac = ":".join(
                ble_mac[i : i + 2] for i in range(0, len(ble_mac), 2)
            )
            connections.add((dr.CONNECTION_BLUETOOTH, dr.format_mac(formatted_mac)))

        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=sw_version,
            serial_number=serial if serial != self.device_id else None,
            connections=connections if connections else None,
        )
