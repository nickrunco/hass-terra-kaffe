"""Button platform for Terra Kaffe."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import TerraKaffeAPIError
from .const import (
    ATTR_BREWING_STATUS,
    ATTR_CANCEL_BREW,
    ATTR_DEVICE_STATUS,
    BREWING_STATUS_BREWING,
    BREWING_STATUS_PAUSED,
    BREWING_STATUS_PREWARMUP,
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
    async_add_entities(
        [TerraKaffePowerButton(coordinator), TerraKaffeCancelBrewButton(coordinator)]
    )


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


def boolean_true_like(current: object) -> str:
    """Return "true" in the same style the machine reports booleans.

    Afero reports BOOLEAN attributes as either "true"/"false" or "1"/"0"
    depending on the device profile; mirror whatever we last saw.
    """
    if isinstance(current, str) and current.strip() in ("0", "1"):
        return "1"
    if isinstance(current, (int, bool)) and not isinstance(current, str):
        return "1"
    return "true"


class TerraKaffeCancelBrewButton(TerraKaffeEntity, ButtonEntity):
    """Button that cancels the drink currently being made."""

    _attr_translation_key = "cancel_brew"
    _attr_icon = "mdi:coffee-off"

    def __init__(self, coordinator: TerraKaffeDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "cancel_brew")

    async def async_press(self) -> None:
        """Cancel the current brew."""
        attributes = (self.coordinator.data or {}).get("attributes", {})
        try:
            brewing_status = int(attributes.get(ATTR_BREWING_STATUS))
        except (TypeError, ValueError):
            brewing_status = None
        if brewing_status not in (
            BREWING_STATUS_BREWING,
            BREWING_STATUS_PREWARMUP,
            BREWING_STATUS_PAUSED,
        ):
            raise HomeAssistantError("Nothing is brewing right now.")

        try:
            await self.coordinator.api.async_set_attribute(
                self.coordinator.account_id,
                self.coordinator.device_id,
                ATTR_CANCEL_BREW,
                boolean_true_like(attributes.get(ATTR_CANCEL_BREW)),
            )
        except TerraKaffeAPIError as err:
            raise HomeAssistantError(f"Could not cancel the brew: {err}") from err
        await self.coordinator.async_request_refresh()
