"""The Terra Kaffe integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import TerraKaffeAPI, TerraKaffeAPIError, TerraKaffeAuthError
from .const import CONF_REFRESH_TOKEN, LOGGER
from .coordinator import TerraKaffeConfigEntry, TerraKaffeDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TerraKaffeConfigEntry) -> bool:
    """Set up Terra Kaffe from a config entry."""
    api = TerraKaffeAPI(hass)

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    if username and password:
        api.set_credentials(username, password)
    # Seed the stored refresh token without triggering the persist callback.
    api.set_tokens(access_token=None, refresh_token=entry.data.get(CONF_REFRESH_TOKEN))

    @callback
    def _persist_refresh_token(token: str) -> None:
        if entry.data.get(CONF_REFRESH_TOKEN) != token:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_REFRESH_TOKEN: token}
            )

    api.on_refresh_token_update = _persist_refresh_token

    try:
        # Tries the stored refresh token first, then email/password.
        await api.async_get_accounts()
    except TerraKaffeAuthError as err:
        LOGGER.debug("Setup authentication failed: %s", err)
        raise ConfigEntryAuthFailed("Authentication failed") from err
    except TerraKaffeAPIError as err:
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    coordinator = TerraKaffeDataUpdateCoordinator(hass, entry, api)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TerraKaffeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
