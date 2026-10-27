"""UI setup and reconfiguration for a direct controller connection."""

from collections.abc import Mapping
from typing import Any

import probatio
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_CONTROLLER_SERIAL,
    CONF_INFO_PORT,
    DEFAULT_INFO_PORT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
)
from .cosmos import Connection, CosmosClient, CosmosError, serial_number
from .models import Device
from .protocol import (
    ANALOG_INPUT_PAYLOAD,
    DIGITAL_OUTPUT_PAYLOAD,
    ProtocolError,
    decode_analog,
    decode_digital,
)


def _number(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            mode=NumberSelectorMode.BOX,
        )
    )


def _schema(defaults: Mapping[str, Any]) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): TextSelector(),
            probatio.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): _number(
                1, 65535
            ),
            probatio.Required(
                CONF_INFO_PORT, default=defaults.get(CONF_INFO_PORT, DEFAULT_INFO_PORT)
            ): _number(1, 65535),
            probatio.Required(
                CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): _number(1, MAX_SCAN_INTERVAL),
        }
    )


class DeosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure a COSMOS controller."""

    VERSION = 2
    MINOR_VERSION = 3

    async def _async_validate(self, user_input: dict[str, Any]) -> tuple[dict[str, Any], Device]:
        connection = Connection(
            user_input[CONF_HOST],
            user_input.get(CONF_PORT, DEFAULT_PORT),
            user_input.get(CONF_INFO_PORT, DEFAULT_INFO_PORT),
        )
        interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if (
            type(interval) not in {int, float}
            or not 1 <= interval <= MAX_SCAN_INTERVAL
            or int(interval) != interval
        ):
            raise ValueError("invalid_interval")
        client = CosmosClient(async_get_clientsession(self.hass), connection)
        try:
            info = await client.async_get_system_info()
        except CosmosError:
            info = {}
        # Both requests are read-only. Accept a partial response but not an unrelated web server.
        readings = []
        for payload, decoder in (
            (ANALOG_INPUT_PAYLOAD, decode_analog),
            (DIGITAL_OUTPUT_PAYLOAD, decode_digital),
        ):
            try:
                readings.extend(decoder(await client.async_read(payload)).values())
            except CosmosError, ProtocolError:
                continue
        if not any(value is not None for value in readings):
            raise CosmosError("cannot_connect")
        data = {
            CONF_HOST: connection.host,
            CONF_PORT: connection.port,
            CONF_INFO_PORT: connection.info_port,
            CONF_SCAN_INTERVAL: int(interval),
        }
        if serial := serial_number(info):
            data[CONF_CONTROLLER_SERIAL] = serial
        return data, Device.from_info(connection.identity(info), info)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                data, device = await self._async_validate(user_input)
            except CosmosError:
                errors["base"] = "cannot_connect"
            except ValueError as err:
                errors["base"] = str(err)
            else:
                await self.async_set_unique_id(device.id)
                self._abort_if_unique_id_configured()
                for entry in self._async_current_entries():
                    if (entry.data.get(CONF_HOST), entry.data.get(CONF_PORT, DEFAULT_PORT)) == (
                        data[CONF_HOST],
                        data[CONF_PORT],
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_create_entry(title=device.model, data=data)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                data, device = await self._async_validate(user_input)
            except CosmosError:
                errors["base"] = "cannot_connect"
            except ValueError as err:
                errors["base"] = str(err)
            else:
                expected = entry.data.get(CONF_CONTROLLER_SERIAL)
                if expected and not device.serial_number:
                    errors["base"] = "cannot_identify"
                elif expected and expected != device.serial_number:
                    return self.async_abort(reason="wrong_device")
                else:
                    # Preserve the entry's unique ID and all current entity/device registrations.
                    return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema({**entry.data, **(user_input or {})}),
            errors=errors,
        )
