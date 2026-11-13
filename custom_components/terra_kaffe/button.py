"""Button platform for Terra Kaffe."""

from __future__ import annotations

import time
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import TerraKaffeAPIError
from .const import (
    ATTR_BREWING_STATUS,
    ATTR_CANCEL_BREW,
    ATTR_DEVICE_STATUS,
    ATTR_DRINK_ORDER,
    ATTR_SAVED_DRINK_BASE,
    BREWING_STATUS_BREWING,
    BREWING_STATUS_PAUSED,
    BREWING_STATUS_PREWARMUP,
    BREWING_STATUS_READY,
    DEVICE_STATUS_GOING_TO_WAKE,
    DEVICE_STATUS_SLEEP,
    DEVICE_STATUS_WAKE,
    SAVED_DRINK_SLOTS,
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
    entities: list[ButtonEntity] = [
        TerraKaffePowerButton(coordinator),
        TerraKaffeCancelBrewButton(coordinator),
    ]
    entities.extend(
        TerraKaffeSavedDrinkButton(coordinator, slot)
        for slot in range(SAVED_DRINK_SLOTS)
    )
    async_add_entities(entities)


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


@dataclass(frozen=True)
class SavedDrink:
    """A drink stored in one of the machine's saved-drink slots."""

    uid: str
    name: str
    recipe: str


def parse_saved_drink(value: object) -> SavedDrink | None:
    """Parse a slot value of the form ``uid^timestamp^name^recipe``.

    Returns None for empty or unrecognised slots.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    parts = value.split("^")
    if len(parts) < 4:
        return None
    uid, _timestamp, name = parts[0], parts[1], parts[2]
    recipe = "^".join(parts[3:]).strip()
    if not recipe.startswith("$"):
        return None
    return SavedDrink(uid=uid, name=name.strip() or "Saved drink", recipe=recipe)


class TerraKaffeSavedDrinkButton(TerraKaffeEntity, ButtonEntity):
    """Starts one of the drinks saved on the machine (slots 200-209)."""

    _attr_icon = "mdi:coffee"

    def __init__(
        self, coordinator: TerraKaffeDataUpdateCoordinator, slot: int
    ) -> None:
        """Initialize the button for a saved-drink slot (0-9)."""
        super().__init__(coordinator, f"saved_drink_{slot + 1}")
        self._slot = slot
        self._attr_id = ATTR_SAVED_DRINK_BASE + slot
        # Hide unused slots by default; users can enable them later.
        self._attr_entity_registry_enabled_default = (
            self._drink is not None if coordinator.data else slot == 0
        )

    @property
    def _drink(self) -> SavedDrink | None:
        attributes = (self.coordinator.data or {}).get("attributes", {})
        return parse_saved_drink(attributes.get(self._attr_id))

    @property
    def name(self) -> str:
        """Use the drink's own name, e.g. "Brew Morning latte"."""
        drink = self._drink
        if drink:
            return f"Brew {drink.name}"
        return f"Saved drink {self._slot + 1} (empty)"

    @property
    def available(self) -> bool:
        """Only available when the slot holds a drink."""
        return super().available and self._drink is not None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the recipe so automations can see what will be made."""
        drink = self._drink
        if not drink:
            return None
        return {"recipe": drink.recipe, "slot": str(self._slot + 1)}

    async def async_press(self) -> None:
        """Start this drink, subject to the safety checks."""
        coordinator = self.coordinator
        drink = self._drink
        if drink is None:
            raise HomeAssistantError("This saved-drink slot is empty.")

        armed_until = coordinator.brew_armed_until
        if armed_until is None or time.monotonic() >= armed_until:
            raise HomeAssistantError(
                "Remote brewing is off. Put a cup under the spout, then turn on "
                "'Allow remote brewing' and try again."
            )

        data = coordinator.data or {}
        if not data.get("device_state", {}).get("available", False):
            raise HomeAssistantError("The machine is offline.")
        attributes = data.get("attributes", {})
        try:
            power = int(attributes.get(ATTR_DEVICE_STATUS))
        except (TypeError, ValueError):
            power = None
        if power != DEVICE_STATUS_WAKE:
            raise HomeAssistantError(
                "The machine is asleep or waking up. Press Power and wait until "
                "it's ready."
            )
        try:
            brewing = int(attributes.get(ATTR_BREWING_STATUS))
        except (TypeError, ValueError):
            brewing = None
        if brewing != BREWING_STATUS_READY:
            raise HomeAssistantError("The machine is busy. Wait until it's ready.")

        # One drink per arm: disarm before sending so a retry can't double-brew.
        if coordinator.brew_arm_switch is not None:
            coordinator.brew_arm_switch.disarm()
        else:
            coordinator.brew_armed_until = None

        try:
            await coordinator.api.async_set_attribute(
                coordinator.account_id,
                coordinator.device_id,
                ATTR_DRINK_ORDER,
                drink.recipe,
            )
        except TerraKaffeAPIError as err:
            raise HomeAssistantError(f"Could not start {drink.name}: {err}") from err
        await coordinator.async_request_refresh()
