"""Sanitized controller diagnostics without addresses or hardware identities."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import DeosConfigEntry
from .const import CONF_CONTROLLER_SERIAL

TO_REDACT = {CONF_HOST, CONF_CONTROLLER_SERIAL, "token", "url", "id", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DeosConfigEntry
) -> dict[str, Any]:
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return {"configuration": async_redact_data(dict(entry.data), TO_REDACT)}
    return async_redact_data(
        {
            "configuration": dict(entry.data),
            "device": asdict(coordinator.device),
            "last_update_success": coordinator.last_update_success,
            "metadata_error": coordinator.metadata_error,
            "state": asdict(coordinator.data) if coordinator.data is not None else None,
        },
        TO_REDACT,
    )
