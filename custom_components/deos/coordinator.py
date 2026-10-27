"""Poll COSMOS directly, once per cycle for all entities."""

import time
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CONTROLLER_SERIAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    METADATA_REFRESH_INTERVAL,
)
from .cosmos import CosmosClient, CosmosError, serial_number
from .models import Device, Reading, State
from .protocol import (
    ANALOG_INPUT_MAP,
    ANALOG_INPUT_PAYLOAD,
    DIGITAL_OUTPUT_MAP,
    DIGITAL_OUTPUT_PAYLOAD,
    ProtocolError,
    decode_analog,
    decode_digital,
)

if TYPE_CHECKING:
    from . import DeosConfigEntry


class DeosCoordinator(DataUpdateCoordinator[State]):
    """Independent per-channel validity with one shared polling lifecycle."""

    def __init__(self, hass: HomeAssistant, entry: DeosConfigEntry, client: CosmosClient) -> None:
        interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="DEOS COSMOS",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.entry = entry
        self.stale_after = max(30, 3 * interval)
        self.device = Device(id=entry.unique_id)
        self.metadata_error: str | None = "not_polled"
        self._metadata: dict[str, str] = {}
        self._next_metadata = 0.0
        self._group_errors: dict[str, str | None] = {}

    async def _async_setup(self) -> None:
        registry = dr.async_get(self.hass)
        if registered := registry.async_get_device_by_identifier(
            (DOMAIN, self.entry.unique_id), self.entry.entry_id
        ):
            self._metadata = {
                key: value
                for key in ("model", "serial_number", "sw_version", "hw_version")
                if (value := getattr(registered, key)) is not None
            }
            self.device = Device.from_info(self.entry.unique_id, self._metadata)
        await self._async_refresh_metadata()

    async def _async_refresh_metadata(self) -> None:
        try:
            info = await self.client.async_get_system_info()
        except CosmosError as err:
            self.metadata_error = str(err)
            self._next_metadata = time.monotonic() + 60
            return  # Optional metadata must not hide valid controller measurements.
        self._next_metadata = time.monotonic() + METADATA_REFRESH_INTERVAL
        serial = serial_number(info)
        expected = self.entry.data.get(CONF_CONTROLLER_SERIAL)
        if serial and expected and serial != expected:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="controller_serial_changed"
            )
        if serial and not expected:
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, CONF_CONTROLLER_SERIAL: serial}
            )
        self.metadata_error = None
        self._metadata.update(info)
        self.device = Device.from_info(self.entry.unique_id, self._metadata)
        registry = dr.async_get(self.hass)
        if registered := registry.async_get_device_by_identifier(
            (DOMAIN, self.entry.unique_id), self.entry.entry_id
        ):
            registry.async_update_device(
                registered.id,
                manufacturer=self.device.manufacturer,
                model=self.device.model,
                serial_number=self.device.serial_number,
                sw_version=self.device.sw_version,
                hw_version=self.device.hw_version,
                name=self.device.name,
                configuration_url=self.client.connection.configuration_url,
            )

    async def _async_update_data(self) -> State:
        if time.monotonic() >= self._next_metadata:
            await self._async_refresh_metadata()
        readings = {}
        for group, payload, mapping, decoder in (
            ("analog", ANALOG_INPUT_PAYLOAD, ANALOG_INPUT_MAP, decode_analog),
            ("digital", DIGITAL_OUTPUT_PAYLOAD, DIGITAL_OUTPUT_MAP, decode_digital),
        ):
            error = None
            values = {}
            try:
                values = decoder(await self.client.async_read(payload))
            except (CosmosError, ProtocolError) as err:
                error = str(err)
            now = time.monotonic()
            for channel, _ in mapping.values():
                value = values.get(channel)
                readings[channel] = (
                    Reading(value=value, observed_at=now, error=None)
                    if value is not None
                    else Reading(error=error or "invalid_or_missing_reading")
                )
            group_error = error or (
                "invalid_or_missing_reading"
                if any(values.get(key) is None for key, _ in mapping.values())
                else None
            )
            if group_error != self._group_errors.get(group):
                if group_error:
                    LOGGER.warning("COSMOS %s polling degraded: %s", group, group_error)
                else:
                    LOGGER.info("COSMOS %s polling recovered", group)
            self._group_errors[group] = group_error
        if not any(reading.available for reading in readings.values()):
            raise UpdateFailed("No valid readings from COSMOS")
        return State(channels=readings)
