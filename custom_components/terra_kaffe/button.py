"""Button platform for Terra Kaffe."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import TerraKaffeAPIError
from .const import (
    ATTR_DEVICE_STATUS,
    DEVICE_STATUS_GOING_TO_WAKE,
    DEVICE_STATUS_SLEEP,
    DEVICE_STATUS_WAKE,
)
from .coordinator import TerraKaffeConfigEntry, TerraKaffeDataUpdateCoordinator
from .entity import TerraKaffeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraKaffeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terra Kaffe button entities."""
    coordinator = entry.runtime_data
    async_add_entities([TerraKaffePowerButton(coordinator)])


class TerraKaffePowerButton(TerraKaffeEntity, ButtonEntity):
    """Button for toggling Terra Kaffe sleep/wake state."""

    _attr_translation_key = "power"

    def __init__(self, coordinator: TerraKaffeDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "power")

    @property
    def icon(self) -> str:
        """Return the icon based on current state."""
        if not self.coordinator.data:
            return "mdi:power"
        attributes = self.coordinator.data.get("attributes", {})
        status = attributes.get(ATTR_DEVICE_STATUS)
        # Show power-off icon if awake (pressing will sleep), power icon if sleeping (pressing will wake)
        if status in (DEVICE_STATUS_WAKE, DEVICE_STATUS_GOING_TO_WAKE):
            return "mdi:power-off"
        return "mdi:power"

    async def async_press(self) -> None:
        """Press the button to toggle wake/sleep state."""
        # Check if device is available
        device_state = (
            self.coordinator.data.get("device_state", {})
            if self.coordinator.data
            else {}
        )
        if not device_state.get("available", False):
            raise HomeAssistantError(
                "Device is not available. Please ensure the machine is powered on and connected."
            )

        # Get current status
        attributes = self.coordinator.data.get("attributes", {})
        current_status = attributes.get(ATTR_DEVICE_STATUS)

        # Determine target status based on current state
        # If awake or going to wake, put to sleep; otherwise wake up
        if current_status in (DEVICE_STATUS_WAKE, DEVICE_STATUS_GOING_TO_WAKE):
            target_status = DEVICE_STATUS_SLEEP
        else:
            target_status = DEVICE_STATUS_WAKE

        try:
            await self.coordinator.api.async_set_attribute(
                self.coordinator.account_id,
                self.coordinator.device_id,
                ATTR_DEVICE_STATUS,
                target_status,
            )
        except TerraKaffeAPIError as err:
            raise HomeAssistantError(f"Could not change power state: {err}") from err
        await self.coordinator.async_request_refresh()
