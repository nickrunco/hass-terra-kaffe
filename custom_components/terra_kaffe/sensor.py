"""Sensor platform for Terra Kaffe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_APPLICATION_VERSION,
    ATTR_BEAN_LEVEL,
    ATTR_BOOTLOADER_VERSION,
    ATTR_BREWING_PROGRESS,
    ATTR_BREWING_STATUS,
    ATTR_CARE_STATUS,
    ATTR_CLEAN_BREW_UNIT_STATE,
    ATTR_COFFEE_ORDER,
    ATTR_CURRENT_ESPRESSO_PROFILE,
    ATTR_DESCALE_UNIT_STATE,
    ATTR_DEVICE_FRIENDLY_NAME,
    ATTR_DEVICE_MODEL,
    ATTR_DEVICE_OS,
    ATTR_DEVICE_SERIAL,
    ATTR_DEVICE_STATUS,
    ATTR_DRINK_HISTORY,
    ATTR_DRINK_ORDER_ERROR,
    ATTR_DRINK_ORDER_RECEIVED,
    ATTR_DRIP_TRAY_STATE,
    ATTR_ESPRESSO_SHOT_COUNT,
    ATTR_GRIND_SETTING,
    ATTR_LANGUAGE,
    ATTR_MAINTENANCE_PERFORMED,
    ATTR_PROFILE_VERSION,
    ATTR_RINSE_MILK_STATE,
    ATTR_SCREEN_BRIGHTNESS,
    ATTR_STATS,
    ATTR_TIME_FORMAT,
    ATTR_TIME_ZONE,
    ATTR_TOTAL_CUP_COUNT,
    ATTR_WAKE_DRINK,
    ATTR_WASTE_BIN_COUNT,
    ATTR_WASTE_BIN_LEVEL,
    ATTR_WATER_FILTER_COUNT,
    ATTR_WATER_HARDNESS,
    ATTR_WIFI_BARS,
    ATTR_WIFI_SSID,
    BREWING_STATUS_BREWING,
    BREWING_STATUS_CLEANING,
    BREWING_STATUS_ERROR,
    BREWING_STATUS_PAUSED,
    BREWING_STATUS_PREWARMUP,
    BREWING_STATUS_READY,
    DEVICE_STATUS_GOING_TO_SLEEP,
    DEVICE_STATUS_GOING_TO_WAKE,
    DEVICE_STATUS_SLEEP,
    DEVICE_STATUS_WAKE,
)
from .coordinator import TerraKaffeConfigEntry, TerraKaffeDataUpdateCoordinator
from .entity import TerraKaffeEntity

BREWING_STATUS_MAP = {
    BREWING_STATUS_READY: "Ready",
    BREWING_STATUS_BREWING: "Brewing",
    BREWING_STATUS_PREWARMUP: "Prewarming",
    BREWING_STATUS_PAUSED: "Paused",
    BREWING_STATUS_CLEANING: "Cleaning",
    BREWING_STATUS_ERROR: "Error",
}

DEVICE_STATUS_MAP = {
    DEVICE_STATUS_SLEEP: "Sleep",
    DEVICE_STATUS_WAKE: "Awake",
    DEVICE_STATUS_GOING_TO_WAKE: "Waking up",
    DEVICE_STATUS_GOING_TO_SLEEP: "Going to sleep",
}

LANGUAGE_MAP = {
    0: "English",
    1: "Spanish",
    2: "French",
    3: "German",
    4: "Italian",
    5: "Portuguese",
}

TIME_FORMAT_MAP = {
    0: "12-hour",
    1: "24-hour",
}


def parse_percentage(value: Any) -> float | None:
    """Parse percentage from string like '60/300'."""
    if not value or not isinstance(value, str):
        return None
    try:
        parts = value.split("/")
        if len(parts) == 2:
            current = float(parts[0])
            max_val = float(parts[1])
            if max_val > 0:
                return round((current / max_val) * 100, 1)
    except (ValueError, AttributeError):
        pass
    return None


def parse_int(value: Any) -> int | None:
    """Parse integer value."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_str(value: Any) -> str | None:
    """Parse string value."""
    if value is None:
        return None
    return str(value) if value else None


def parse_rinse_milk(value: Any) -> str | None:
    """Parse rinse milk status from format 'status^name^count'.

    Format: "1^Rinse Milk System^1 Brews"
    Returns: "Good" if status is 1, otherwise shows the status.
    """
    if value is None:
        return None
    try:
        value_str = str(value)
        parts = value_str.split("^")
        if len(parts) >= 1:
            status = parts[0]
            # Status 1 = Good, 0 = needs attention
            if status == "1":
                return "Good"
            if status == "0":
                return "Needs attention"
            # Return the full value if format is unexpected
            return value_str
        return value_str
    except (ValueError, AttributeError):
        return str(value) if value else None


def parse_care_status(value: Any) -> str | None:
    """Parse care status bitmask into readable flags."""
    if value is None:
        return None
    try:
        status_int = int(value)
        if status_int == 0:
            return "OK"
        # Known bits; anything else is reported as "Other (bit N)".
        known = {
            0: "Brew unit",
            1: "Descale",
            2: "Water filter",
            3: "Waste bin",
            11: "Drip tray",
        }
        flags = [
            known.get(bit, f"Other (bit {bit})")
            for bit in range(status_int.bit_length())
            if status_int & (1 << bit)
        ]
        if flags:
            return ", ".join(flags)
        return f"Status: {status_int} (0x{status_int:X})"
    except (ValueError, TypeError):
        return str(value) if value else None


def parse_mapped_int(mapping: dict[int, str]) -> Callable[[Any], str | None]:
    """Create a parser for mapped integer values."""

    def parser(value: Any) -> str | None:
        if value is None:
            return None
        parsed = parse_int(value)
        if parsed is None:
            return None
        return mapping.get(parsed, f"Unknown ({parsed})")

    return parser


@dataclass(frozen=True, kw_only=True)
class TerraKaffeSensorEntityDescription(SensorEntityDescription):
    """Describe Terra Kaffe sensor."""

    attr_id: int
    value_fn: Callable[[Any], StateType] = lambda x: x


SENSOR_DESCRIPTIONS: tuple[TerraKaffeSensorEntityDescription, ...] = (
    # === Core Status Sensors ===
    TerraKaffeSensorEntityDescription(
        key="device_status",
        translation_key="device_status",
        attr_id=ATTR_DEVICE_STATUS,
        icon="mdi:power",
        value_fn=parse_mapped_int(DEVICE_STATUS_MAP),
    ),
    TerraKaffeSensorEntityDescription(
        key="brewing_status",
        translation_key="brewing_status",
        attr_id=ATTR_BREWING_STATUS,
        icon="mdi:coffee",
        value_fn=parse_mapped_int(BREWING_STATUS_MAP),
    ),
    TerraKaffeSensorEntityDescription(
        key="brewing_progress",
        translation_key="brewing_progress",
        attr_id=ATTR_BREWING_PROGRESS,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-clock",
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="coffee_order",
        translation_key="coffee_order",
        attr_id=ATTR_COFFEE_ORDER,
        icon="mdi:coffee-to-go",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="drink_history",
        translation_key="drink_history",
        attr_id=ATTR_DRINK_HISTORY,
        icon="mdi:history",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="current_espresso_profile",
        translation_key="current_espresso_profile",
        attr_id=ATTR_CURRENT_ESPRESSO_PROFILE,
        icon="mdi:coffee",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="drink_order_error",
        translation_key="drink_order_error",
        attr_id=ATTR_DRINK_ORDER_ERROR,
        icon="mdi:alert-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="drink_order_received",
        translation_key="drink_order_received",
        attr_id=ATTR_DRINK_ORDER_RECEIVED,
        icon="mdi:check-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    # === Level Sensors ===
    TerraKaffeSensorEntityDescription(
        key="bean_level",
        translation_key="bean_level",
        attr_id=ATTR_BEAN_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:seed",
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="waste_bin_level",
        translation_key="waste_bin_level",
        attr_id=ATTR_WASTE_BIN_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:delete",
        value_fn=parse_int,
    ),
    # === Counter Sensors ===
    TerraKaffeSensorEntityDescription(
        key="total_cups",
        translation_key="total_cups",
        attr_id=ATTR_TOTAL_CUP_COUNT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="espresso_shots",
        translation_key="espresso_shots",
        attr_id=ATTR_ESPRESSO_SHOT_COUNT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:coffee-maker",
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="stats",
        translation_key="stats",
        attr_id=ATTR_STATS,
        icon="mdi:chart-bar",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    # === Maintenance Sensors ===
    TerraKaffeSensorEntityDescription(
        key="clean_brew_unit",
        translation_key="clean_brew_unit",
        attr_id=ATTR_CLEAN_BREW_UNIT_STATE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:dishwasher",
        value_fn=parse_percentage,
    ),
    TerraKaffeSensorEntityDescription(
        key="descale_status",
        translation_key="descale_status",
        attr_id=ATTR_DESCALE_UNIT_STATE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
        value_fn=parse_percentage,
    ),
    TerraKaffeSensorEntityDescription(
        key="water_filter",
        translation_key="water_filter",
        attr_id=ATTR_WATER_FILTER_COUNT,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:filter",
        value_fn=parse_percentage,
    ),
    TerraKaffeSensorEntityDescription(
        key="waste_bin_count",
        translation_key="waste_bin_count",
        attr_id=ATTR_WASTE_BIN_COUNT,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:delete-clock",
        value_fn=parse_percentage,
    ),
    TerraKaffeSensorEntityDescription(
        key="drip_tray",
        translation_key="drip_tray",
        attr_id=ATTR_DRIP_TRAY_STATE,
        icon="mdi:tray",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="rinse_milk",
        translation_key="rinse_milk",
        attr_id=ATTR_RINSE_MILK_STATE,
        icon="mdi:water-circle",
        entity_registry_enabled_default=False,
        value_fn=parse_rinse_milk,
    ),
    TerraKaffeSensorEntityDescription(
        key="care_status",
        translation_key="care_status",
        attr_id=ATTR_CARE_STATUS,
        icon="mdi:wrench",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_care_status,
    ),
    TerraKaffeSensorEntityDescription(
        key="maintenance_performed",
        translation_key="maintenance_performed",
        attr_id=ATTR_MAINTENANCE_PERFORMED,
        icon="mdi:check-decagram",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    # === Settings Sensors ===
    TerraKaffeSensorEntityDescription(
        key="grind_setting",
        translation_key="grind_setting",
        attr_id=ATTR_GRIND_SETTING,
        icon="mdi:coffee-maker-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="water_hardness",
        translation_key="water_hardness",
        attr_id=ATTR_WATER_HARDNESS,
        icon="mdi:water",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="language",
        translation_key="language",
        attr_id=ATTR_LANGUAGE,
        icon="mdi:translate",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_mapped_int(LANGUAGE_MAP),
    ),
    TerraKaffeSensorEntityDescription(
        key="time_zone",
        translation_key="time_zone",
        attr_id=ATTR_TIME_ZONE,
        icon="mdi:map-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="time_format",
        translation_key="time_format",
        attr_id=ATTR_TIME_FORMAT,
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_mapped_int(TIME_FORMAT_MAP),
    ),
    TerraKaffeSensorEntityDescription(
        key="screen_brightness",
        translation_key="screen_brightness",
        attr_id=ATTR_SCREEN_BRIGHTNESS,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:brightness-6",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="wake_drink",
        translation_key="wake_drink",
        attr_id=ATTR_WAKE_DRINK,
        icon="mdi:coffee-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="friendly_name",
        translation_key="friendly_name",
        attr_id=ATTR_DEVICE_FRIENDLY_NAME,
        icon="mdi:rename-box",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    # === Device Info Sensors ===
    TerraKaffeSensorEntityDescription(
        key="serial_number",
        translation_key="serial_number",
        attr_id=ATTR_DEVICE_SERIAL,
        icon="mdi:barcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="model",
        translation_key="model",
        attr_id=ATTR_DEVICE_MODEL,
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="os_version",
        translation_key="os_version",
        attr_id=ATTR_DEVICE_OS,
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        attr_id=ATTR_APPLICATION_VERSION,
        icon="mdi:cellphone-arrow-down",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="bootloader_version",
        translation_key="bootloader_version",
        attr_id=ATTR_BOOTLOADER_VERSION,
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    TerraKaffeSensorEntityDescription(
        key="profile_version",
        translation_key="profile_version",
        attr_id=ATTR_PROFILE_VERSION,
        icon="mdi:file-document-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
    # === WiFi Sensors ===
    TerraKaffeSensorEntityDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        attr_id=ATTR_WIFI_SSID,
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_str,
    ),
    TerraKaffeSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        attr_id=ATTR_WIFI_BARS,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:wifi-strength-2",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=parse_int,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraKaffeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Terra Kaffe sensor entities."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        TerraKaffeSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    # Add device ID sensor
    entities.append(TerraKaffeDeviceIdSensor(coordinator))
    async_add_entities(entities)


class TerraKaffeSensor(TerraKaffeEntity, SensorEntity):
    """Representation of a Terra Kaffe sensor."""

    entity_description: TerraKaffeSensorEntityDescription

    def __init__(
        self,
        coordinator: TerraKaffeDataUpdateCoordinator,
        description: TerraKaffeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        attributes = self.coordinator.data.get("attributes", {})
        value = attributes.get(self.entity_description.attr_id)
        return self.entity_description.value_fn(value)


class TerraKaffeDeviceIdSensor(TerraKaffeEntity, SensorEntity):
    """Sensor for Terra Kaffe device ID."""

    _attr_translation_key = "device_id"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: TerraKaffeDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "device_id")

    @property
    def native_value(self) -> str:
        """Return the device ID."""
        return self.coordinator.device_id
