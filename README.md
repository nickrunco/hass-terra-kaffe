# Terra Kaffe Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integration for Terra Kaffe coffee machines (TK-02 model). This integration allows you to monitor and control your Terra Kaffe coffee machine directly from Home Assistant.

## Features

- **Device Control**: Wake and sleep your coffee machine
- **Status Monitoring**: Track brewing status, device state, and maintenance needs
- **Level Monitoring**: Monitor bean hopper level, waste bin level, and maintenance counters
- **Statistics**: Track total cups brewed and espresso shots
- **Maintenance Alerts**: Get notified when maintenance is needed (brew unit cleaning, descaling, water filter, waste bin, drip tray)
- **Device Information**: Access device serial number, model, firmware version, and more
- **WiFi Status**: Monitor WiFi connectivity and signal strength

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz) is installed
2. Go to HACS → Integrations
3. Click the three dots (⋮) in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/nickrunco/hass-terra-kaffe`
6. Select category "Integration"
7. Click "Add"
8. Search for "Terra Kaffe" in HACS
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/terra_kaffe` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Terra Kaffe**
4. Enter your Terra Kaffe account credentials:
   - **Username**: Your Terra Kaffe account email
   - **Password**: Your Terra Kaffe account password
5. If you have multiple devices, select the device you want to add
6. Click **Submit**

The integration will automatically discover your Terra Kaffe devices and set up all entities.

### Reauthentication

If your credentials expire, you'll be prompted to reauthenticate. Simply follow the reauthentication flow when prompted.

## Entities

### Sensors

#### Core Status
- **Device Status**: Current power state (Sleep, Awake, Waking up, Going to sleep)
- **Brewing Status**: Current brewing state (Ready, Brewing, Prewarming, Paused, Cleaning, Error)
- **Brewing Progress**: Brewing progress percentage (0-100%)

#### Levels
- **Bean Level**: Bean hopper fill level (percentage)
- **Waste Bin Level**: Waste bin fill level (percentage)

#### Counters
- **Total Cups**: Total number of cups brewed
- **Espresso Shots**: Total number of espresso shots

#### Maintenance
- **Clean Brew Unit**: Brew unit cleaning status (percentage remaining)
- **Descale Status**: Descaling status (percentage remaining)
- **Water Filter**: Water filter status (percentage remaining)
- **Waste Bin Count**: Waste bin counter (percentage remaining)
- **Rinse Milk**: Milk system rinse status
- **Care Status**: Overall maintenance status flags

#### Device Information
- **Serial Number**: Device serial number
- **Model**: Device model and firmware version
- **OS Version**: Device OS version
- **Firmware Version**: Application version
- **Bootloader Version**: Bootloader version
- **Profile Version**: Profile version
- **Device ID**: Unique device identifier

#### Settings
- **Grind Setting**: Current grind setting
- **Water Hardness**: Water hardness setting
- **Language**: Device language setting
- **Time Zone**: Device timezone
- **Time Format**: 12-hour or 24-hour format
- **Screen Brightness**: Screen brightness level
- **Wake Drink**: Configured wake-up drink
- **Friendly Name**: Custom device name

#### WiFi
- **WiFi SSID**: Connected WiFi network name
- **WiFi Signal**: WiFi signal strength (dBm)

#### Diagnostic (Disabled by default)
- **Coffee Order**: Current coffee order
- **Drink History**: Recent drink history
- **Current Espresso Profile**: Active espresso profile ID
- **Drink Order Error**: Last drink order error message
- **Drink Order Received**: Last order confirmation
- **Drip Tray**: Drip tray state
- **Maintenance Performed**: Maintenance status

### Binary Sensors

- **Locked**: Whether the device is locked
- **Screen Saver Enabled**: Whether the screen saver is active
- **Preground Selected**: Whether pre-ground coffee mode is selected
- **WiFi Enabled**: Whether WiFi is enabled
- **Drip Tray Needs Cleaning**: Whether the drip tray needs cleaning

### Buttons

- **Power**: Toggle device wake/sleep state
  - If the device is awake, pressing this will put it to sleep
  - If the device is sleeping, pressing this will wake it up
- **Cancel brew**: Stops the drink currently being made (only works while
  brewing, pre-warming, or paused)

### Remote brewing

- **Allow remote brewing** (switch): a safety arm, off by default. The machine
  can't tell whether a cup is under the spout, so a drink can only be started
  while this is on. It turns itself off after one drink is started, after 10
  minutes, or when Home Assistant restarts.
- **Brew \<drink name\>** (buttons): one per drink saved on the machine
  (slots 1–10). Empty slots are disabled. Each button shows the recipe it will
  send as an attribute. A drink only starts when the safety arm is on, the
  machine is awake, and it's idle.

## Usage Examples

### Automation: Wake Machine Before Morning Routine

```yaml
automation:
  - alias: "Wake Terra Kaffe for Morning Coffee"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.terra_kaffe_power
```

### Automation: Alert When Maintenance Needed

```yaml
automation:
  - alias: "Terra Kaffe Maintenance Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.terra_kaffe_clean_brew_unit
        below: 20
      - platform: numeric_state
        entity_id: sensor.terra_kaffe_descale_status
        below: 20
      - platform: numeric_state
        entity_id: sensor.terra_kaffe_water_filter
        below: 20
      - platform: state
        entity_id: binary_sensor.terra_kaffe_drip_tray_needs_cleaning
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Terra Kaffe maintenance needed: {{ trigger.entity_id }}"
```

### Automation: Alert When Beans Are Low

```yaml
automation:
  - alias: "Terra Kaffe Low Beans Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.terra_kaffe_bean_level
        below: 20
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Terra Kaffe bean level is low: {{ states('sensor.terra_kaffe_bean_level') }}%"
```

### Template: Display Brewing Status

```yaml
template:
  - sensor:
      - name: "Terra Kaffe Status"
        state: >
          {% if is_state('sensor.terra_kaffe_brewing_status', 'Brewing') %}
            Brewing ({{ states('sensor.terra_kaffe_brewing_progress') }}%)
          {% elif is_state('sensor.terra_kaffe_brewing_status', 'Error') %}
            Error - Check machine
          {% elif is_state('sensor.terra_kaffe_device_status', 'Sleep') %}
            Sleeping
          {% else %}
            Ready
          {% endif %}
```

## Requirements

- Home Assistant 2025.1.0 or later
- Terra Kaffe account credentials
- Terra Kaffe TK-02 coffee machine connected to WiFi

## Troubleshooting

### Integration Won't Connect

1. Verify your Terra Kaffe credentials are correct
2. Ensure your coffee machine is powered on and connected to WiFi
3. Check the Home Assistant logs for error messages
4. Try removing and re-adding the integration

### Entities Not Updating

1. Check the device status sensor - if it shows "Sleep", the device may not be responding
2. Wake the device using the power button
3. Check your WiFi connection
4. Review the Home Assistant logs for API errors

### Authentication Errors

If you see authentication errors:
1. The integration will automatically prompt for reauthentication
2. Enter your credentials again when prompted
3. If issues persist, remove and re-add the integration

### Device Not Found

1. Ensure your Terra Kaffe account has access to the device
2. Verify the device is registered in the Terra Kaffe mobile app
3. Check that the device is online in the Terra Kaffe app

## API Information

This integration uses the Afero API (via `api2.gk7qmfrz.afero.net`) to communicate with Terra Kaffe devices. The integration authenticates using OAuth2 with your Terra Kaffe account credentials.

For detailed API documentation, see [API_DOCUMENTATION.md](custom_components/terra_kaffe/API_DOCUMENTATION.md).

## Support

- **Issues**: Report issues on the [GitHub Issues](https://github.com/nickrunco/hass-terra-kaffe/issues) page
- **Feature Requests**: Submit feature requests via GitHub Issues

## Credits

Forked from [bassrock/hass-terra-kaffe](https://github.com/bassrock/hass-terra-kaffe).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Security notes

- Your Terra Kaffe email and password are stored in Home Assistant's config entry
  (`.storage/core.config_entries`) so the integration can log in again when its
  session expires. Anyone with access to your HA config or backups can read them,
  so use a password you don't use anywhere else.
- Authentication goes directly to Afero's OAuth server (the same one the official
  app uses), impersonating the Android app's public client ID.

## License

This project is licensed under the MIT License.

## Disclaimer

This integration is not officially supported by Terra Kaffe. It is a community-developed integration that uses the same API as the official Terra Kaffe mobile app. Use at your own risk.

