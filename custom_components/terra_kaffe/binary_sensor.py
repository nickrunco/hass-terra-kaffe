"""Binary sensor platform for Terra Kaffe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_CARE_STATUS,
    ATTR_LOCKED,
    ATTR_PREGROUND_SELECTED,
    ATTR_SCREEN_SAVER_ENABLED,
    ATTR_WIFI_ENABLED,
)
from .coordinator import TerraKaffeConfigEntry, TerraKaffeDataUpdateCoordinator
from .entity import TerraKaffeEntity


def parse_bool(value: Any) -> bool | None:
    """Parse boolean value from various formats."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "on", "yes")
    if isinstance(value, int):
        return value != 0
    return None


def parse_care_status_drip_tray(value: Any) -> bool | None:
    """Parse drip tray status from CARE_STATUS bitmask.

    Drip tray needs cleaning when bit 11 (0x800 = 2048) is set.
    Confirmed from network capture: care_status = 2048 when drip tray is full.
    """
    if value is None:
        return None
    try:
        status_int = int(value)
        # Bit 11 (0x800 = 2048) indicates drip tray needs cleaning
        return bool(status_int & 0x800)
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True, kw_only=True)
class TerraKaffeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe Terra Kaffe binary sensor."""

    attr_id: int
    value_fn: Callable[[Any], bool | None] = parse_bool


BINARY_SENSOR_DESCRIPTIONS: tuple[TerraKaffeBinarySensorEntityDescription, ...] = (
    TerraKaffeBinarySensorEntityDescription(
        key="locked",
        translation_key="locked",
        attr_id=ATTR_LOCKED,
        device_class=BinarySensorDeviceClass.LOCK,
        icon="mdi:lock",
    ),
    TerraKaffeBinarySensorEntityDescription(
        key="screen_saver_enabled",
        translation_key="screen_saver_enabled",
        attr_id=ATTR_SCREEN_SAVER_ENABLED,
        icon="mdi:monitor-eye",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TerraKaffeBinarySensorEntityDescription(
        key="preground_selected",
        translation_key="preground_selected",
        attr_id=ATTR_PREGROUND_SELECTED,
        icon="mdi:coffee-maker",
    ),
    TerraKaffeBinarySensorEntityDescription(
        key="wifi_enabled",
        translation_key="wifi_enabled",
        attr_id=ATTR_WIFI_ENABLED,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TerraKaffeBinarySensorEntityDescription(
        key="drip_tray_needs_cleaning",
        translation_key="drip_tray_needs_cleaning",
        attr_id=ATTR_CARE_STATUS,
        icon="mdi:tray-alert",
        value_fn=parse_care_status_drip_tray,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraKaffeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terra Kaffe binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        TerraKaffeBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class TerraKaffeBinarySensor(TerraKaffeEntity, BinarySensorEntity):
    """Representation of a Terra Kaffe binary sensor."""

    entity_description: TerraKaffeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TerraKaffeDataUpdateCoordinator,
        description: TerraKaffeBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return None
        attributes = self.coordinator.data.get("attributes", {})
        value = attributes.get(self.entity_description.attr_id)
        return self.entity_description.value_fn(value)
