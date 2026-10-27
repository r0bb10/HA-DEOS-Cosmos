"""Read-only COSMOS digital outputs; deliberately not controllable switches."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DeosConfigEntry
from .entity import DeosEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DeosOutput(coordinator, channel)
        for channel in coordinator.device.channels
        if channel.kind == "digital_output"
    )


class DeosOutput(DeosEntity, BinarySensorEntity):
    """One observed digital output state."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    @property
    def is_on(self) -> bool | None:
        return self.reading.value if self.available else None
