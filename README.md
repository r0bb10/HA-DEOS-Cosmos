# DEOS COSMOS

Custom Home Assistant integration for reading temperatures and digital output states from a DEOS COSMOS controller over the local network. It connects directly to the controller over HTTP.

**This integration is read-only.** It reports output states as binary sensors, not switches. It cannot change setpoints, turn equipment on or off, or modify the controller's configuration.

## What it provides

- Eight mapped temperature channels, reported in °C.
- Twelve mapped digital output channels: four enabled by default and eight labelled as reserve and disabled by default in this installation.
- Local polling every 5 seconds by default, adjustable from 1 to 300 seconds.
- Controller model, serial number, and hardware and firmware versions when available.
- A link to the controller's web interface from its device page.
- English and Italian setup dialogs.

Missing or invalid readings become unavailable rather than showing a false zero or an off state. Other channels keep updating if they can still be read.

## Installation

Requires **Home Assistant 2026.10.1 or newer** and network access from Home Assistant to the controller.

### HACS

[HACS](https://www.hacs.xyz/docs/use/download/download/) must already be installed.

[![Open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=r0bb10&repository=HA-DEOS-Cosmos&category=integration)

Open the repository using the button above, download **DEOS COSMOS**, then restart Home Assistant.

To add the repository yourself:

1. Open **HACS** and select **⋮ → Custom repositories**.
2. Enter `https://github.com/r0bb10/HA-DEOS-Cosmos`.
3. Select **Integration** as the type and click **Add**.
4. Find **DEOS COSMOS** in HACS and download it.
5. Restart Home Assistant.

### Manual

1. Download `deos.zip` from the [latest release](https://github.com/r0bb10/HA-DEOS-Cosmos/releases/latest).
2. Create a `custom_components/deos` directory inside your Home Assistant configuration directory, alongside `configuration.yaml`.
3. Extract the ZIP contents into that directory. The manifest should end up at `custom_components/deos/manifest.json`.
4. Restart Home Assistant.

Alternatively, download the repository and copy its `custom_components/deos` folder into your own `custom_components` directory.

## Add the integration

After installing the files and restarting Home Assistant:

[![Add DEOS COSMOS to Home Assistant](https://my.home-assistant.io/badges/config_flow.svg)](https://my.home-assistant.io/redirect/config_flow/?domain=deos)

Or go to **Settings → Devices & services → Add integration** and search for **DEOS COSMOS**.

Enter the controller's connection details:

| Setting | Default | Description |
| --- | --- | --- |
| Controller hostname or IP address | — | Hostname or IP only, without `http://`, a port, or a path. |
| Controller HTTP port | `80` | Port used to read temperatures and output states. |
| System information HTTP port | `3000` | Port used to read the controller's identity and version information. |
| Polling interval | `5` seconds | Any whole number from 1 to 300 seconds. |

The integration checks that it can read controller data before completing setup. System information is optional: readings can still work if the information page is unavailable.

To change the address, ports, or polling interval later, open the integration's **⋮** menu and select **Reconfigure**. If the controller's serial number was previously recorded, it must still match.

## Entities

The integration creates the following entities from its fixed map. Channel IDs identify entries in this integration; they do not imply a particular equipment function on another controller. The Italian names shown in Home Assistant describe the author's installation only.

### Temperatures

| Channel | Default entity ID |
| --- | --- |
| AI00 | `sensor.cosmos_ai00` |
| AI01 | `sensor.cosmos_ai01` |
| AI02 | `sensor.cosmos_ai02` |
| AI03 | `sensor.cosmos_ai03` |
| AI04 | `sensor.cosmos_ai04` |
| AI05 | `sensor.cosmos_ai05` |
| AI06 | `sensor.cosmos_ai06` |
| AI07 | `sensor.cosmos_ai07` |

### Digital output states

| Channel | Default entity ID | Enabled by default |
| --- | --- | --- |
| DO00 | `binary_sensor.cosmos_do00` | Yes |
| DO01 | `binary_sensor.cosmos_do01` | Yes |
| DO02 | `binary_sensor.cosmos_do02` | Yes |
| DO03 | `binary_sensor.cosmos_do03` | Yes |
| DO04–DO11 | `binary_sensor.cosmos_do04`–`binary_sensor.cosmos_do11` | No |

Entity IDs may have a suffix if the default ID is already in use, for example when adding another controller.
