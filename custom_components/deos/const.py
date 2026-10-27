"""Constants for the DEOS COSMOS integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "deos"
PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR)
DEFAULT_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 300
DEFAULT_PORT = 80
DEFAULT_INFO_PORT = 3000
CONF_INFO_PORT = "info_port"
CONF_CONTROLLER_SERIAL = "controller_serial"
REQUEST_TIMEOUT = 5
MAX_RESPONSE_BYTES = 1024 * 1024
METADATA_REFRESH_INTERVAL = 300
LOGGER = logging.getLogger(__package__)
