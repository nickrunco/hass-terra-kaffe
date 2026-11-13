"""Constants for Terra Kaffe integration."""

from __future__ import annotations

import logging

DOMAIN = "terra_kaffe"
MANUFACTURER = "Terra Kaffe"
LOGGER = logging.getLogger(__package__)

# Afero API endpoints
# The mobile app uses direct Afero OAuth for device access
AFERO_CLIENT_ID = "tk_android"
AFERO_SERVICE_URL = "https://api2.gk7qmfrz.afero.net"
AFERO_AUTH_URL = "https://auth1.gk7qmfrz.afero.net"
AFERO_TOKEN_URL = f"{AFERO_AUTH_URL}/auth/realms/tkf/protocol/openid-connect/token"

# Terra Kaffe middleware API (for bootstrap/news, not used for device access)
TERRA_KAFFE_API_URL = "https://api.terrakaffeservices.com/api"

# Configuration keys
CONF_REFRESH_TOKEN = "refresh_token"

# Afero attribute IDs for TK-02 coffee machine (from network capture)
# Core status attributes
ATTR_DEVICE_STATUS = 1  # SINT8: 0=Sleep, 1=Wake, 2=Going to Wake, 3=Going to Sleep
ATTR_COFFEE_ORDER = 2  # UTF8S: Current coffee order (read-only)
ATTR_DRINK_HISTORY = 3  # UTF8S: Drink history
ATTR_BEAN_LEVEL = 4  # SINT16: Bean hopper level
ATTR_WASTE_BIN_LEVEL = 5  # SINT8: Waste bin fill level
ATTR_CARE_STATUS = 6  # SINT32: Care/maintenance status
ATTR_GRIND_SETTING = 7  # UTF8S: Grind settings (format: "level|offset")
ATTR_MAINTENANCE_PERFORMED = 9  # SINT8: Maintenance status
ATTR_DRINK_ORDER = 10  # UTF8S: Send drink order to machine (RW)
ATTR_DRINK_ORDER_ERROR = 11  # UTF8S: Drink order error message
ATTR_DRINK_ORDER_RECEIVED = 12  # UTF8S: Drink order receipt confirmation
ATTR_BREWING_STATUS = (
    13  # SINT8: 0=Ready, 1=Brewing, 2=Pre-warmup, 3=Paused, 4=Cleaning, 5=Error
)
ATTR_BREWING_PROGRESS = 14  # SINT8: Brewing progress percentage
ATTR_CANCEL_BREW = 15  # BOOLEAN: Cancel current brew
ATTR_CURRENT_ESPRESSO_PROFILE = 16  # UTF8S: Current espresso profile ID
ATTR_STATS = 17  # UTF8S: Stats (format: "val1^val2^val3")
ATTR_TOTAL_CUP_COUNT = 18  # SINT64: Total cups brewed
ATTR_ESPRESSO_SHOT_COUNT = 19  # SINT64: Total espresso shots

# Settings attributes
ATTR_LANGUAGE = 20  # SINT8: Language setting
ATTR_TIME_ZONE = 21  # SINT8: Timezone
ATTR_TIME_FORMAT = 22  # SINT8: Time format (12/24h)
ATTR_WATER_HARDNESS = 23  # SINT8: Water hardness setting
ATTR_DRINK_MENU_ORDER = 24  # UTF8S: Drink menu order
ATTR_NOTIFICATION_SETTINGS = 25  # SINT16: Notification settings
ATTR_SCREEN_SAVER_ENABLED = 26  # BOOLEAN: Screen saver enabled
ATTR_SCREEN_BRIGHTNESS = 27  # SINT8: Screen brightness
ATTR_PIN = 28  # SINT16: Machine PIN
ATTR_LOCKED = 29  # BOOLEAN: Machine locked state
ATTR_PREGROUND_SELECTED = 45  # BOOLEAN: Pre-ground coffee selected
ATTR_WIFI_ENABLED = 46  # BOOLEAN: WiFi enabled state
ATTR_WIFI_SSID = 47  # UTF8S: Connected WiFi SSID
ATTR_DEVICE_FRIENDLY_NAME = 49  # UTF8S: Device friendly name
ATTR_WAKE_DRINK = 50  # UTF8S: Wake-up drink recipe

# Maintenance attributes
ATTR_CLEAN_BREW_UNIT_STATE = (
    39  # UTF8S: Clean brew unit counter (format: "current/max")
)
ATTR_DESCALE_UNIT_STATE = 40  # UTF8S: Descale counter (format: "current/max")
ATTR_WATER_FILTER_COUNT = 41  # UTF8S: Water filter counter (format: "current/max")
ATTR_WASTE_BIN_COUNT = 42  # UTF8S: Waste bin counter (format: "current/max")
ATTR_DRIP_TRAY_STATE = 43  # SINT8: Drip tray state (0 = empty/good, not a counter)
ATTR_RINSE_MILK_STATE = (
    44  # UTF8S: Rinse milk system status (format: "status^name^count")
)
ATTR_UNKNOWN_MAINTENANCE_48 = 48  # Unknown maintenance attribute

# Device info
ATTR_DEVICE_SERIAL = 100  # UTF8S: Device serial number
ATTR_DEVICE_MODEL = 101  # UTF8S: Device model/firmware version
ATTR_DEVICE_OS = 102  # UTF8S: Device OS version

# Saved drinks (slots 200-209)
ATTR_SAVED_DRINK_BASE = 200  # UTF8S: Saved drink slots 200-209

# Espresso profiles (slots 300-309)
ATTR_ESPRESSO_PROFILE_BASE = 300  # UTF8S: Espresso profile slots 300-309

# Version info
ATTR_BOOTLOADER_VERSION = 2001  # SINT64: Bootloader version
ATTR_APPLICATION_VERSION = 2003  # SINT64: Application version
ATTR_PROFILE_VERSION = 2004  # SINT64: Profile version

# WiFi info
ATTR_WIFI_BARS = 65005  # SINT8: WiFi signal strength (RSSI)
ATTR_WIFI_STEADY_STATE = 65006  # SINT8: WiFi steady state
ATTR_WIFI_SETUP_STATE = 65007  # SINT8: WiFi setup state

# Device status values (TkDevicePowerStatus enum)
DEVICE_STATUS_SLEEP = 0
DEVICE_STATUS_WAKE = 1
DEVICE_STATUS_GOING_TO_WAKE = 2
DEVICE_STATUS_GOING_TO_SLEEP = 3

# Brewing status values (TkBrewingStatus enum)
BREWING_STATUS_READY = 0
BREWING_STATUS_BREWING = 1
BREWING_STATUS_PREWARMUP = 2
BREWING_STATUS_PAUSED = 3
BREWING_STATUS_CLEANING = 4
BREWING_STATUS_ERROR = 5

# Update intervals
UPDATE_INTERVAL_CLOUD = 30  # seconds

# Remote brewing safety
BREW_ARM_TIMEOUT = 600  # seconds the "Allow remote brewing" switch stays on
SAVED_DRINK_SLOTS = 10  # attributes 200-209
