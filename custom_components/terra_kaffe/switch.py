"""Switch platform for Terra Kaffe: the remote-brewing safety arm."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import BREW_ARM_TIMEOUT
from .coordinator import TerraKaffeConfigEntry, TerraKaffeDataUpdateCoordinator
from .entity import TerraKaffeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraKaffeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terra Kaffe switches."""
    switch = TerraKaffeBrewArmSwitch(entry.runtime_data)
    entry.runtime_data.brew_arm_switch = switch
    async_add_entities([switch])


class TerraKaffeBrewArmSwitch(TerraKaffeEntity, SwitchEntity):
    """Must be on before a drink can be started from Home Assistant.

    Turns itself off after one drink is started, or after BREW_ARM_TIMEOUT
    seconds, whichever comes first. Always off after a restart.
    """

    _attr_translation_key = "allow_remote_brewing"
    _attr_icon = "mdi:coffee-maker-check"

    def __init__(self, coordinator: TerraKaffeDataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "allow_remote_brewing")
        self._cancel_timer: CALLBACK_TYPE | None = None

    @property
    def is_on(self) -> bool:
        """Return True while brewing is armed."""
        until = self.coordinator.brew_armed_until
        return until is not None and time.monotonic() < until

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm remote brewing for a limited time."""
        self.coordinator.brew_armed_until = time.monotonic() + BREW_ARM_TIMEOUT
        self._reset_timer()
        self._cancel_timer = async_call_later(
            self.hass, BREW_ARM_TIMEOUT, self._handle_timeout
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm remote brewing."""
        self.disarm()

    @callback
    def disarm(self) -> None:
        """Disarm (also called after a drink is started)."""
        self.coordinator.brew_armed_until = None
        self._reset_timer()
        if self.hass:
            self.async_write_ha_state()

    @callback
    def _handle_timeout(self, _now: Any) -> None:
        self._cancel_timer = None
        self.disarm()

    @callback
    def _reset_timer(self) -> None:
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None

    async def async_will_remove_from_hass(self) -> None:
        """Clean up the timer and disarm."""
        self._reset_timer()
        self.coordinator.brew_armed_until = None
