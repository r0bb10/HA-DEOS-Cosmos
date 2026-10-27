"""Shared native entity behavior with independent channel availability."""

import time

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DeosCoordinator
from .models import Channel, Reading


class DeosEntity(CoordinatorEntity[DeosCoordinator]):
    """Base entity for a COSMOS channel."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DeosCoordinator, channel: Channel) -> None:
        super().__init__(coordinator, context=channel.id)
        self.channel = channel
        self._attr_unique_id = f"{coordinator.device.id}_{channel.id.lower()}"
        self.entity_id = channel.entity_id
        self._attr_name = channel.name.title()
        self._attr_entity_registry_enabled_default = not channel.reserve

    @property
    def device_info(self) -> DeviceInfo:
        device = self.coordinator.device
        return DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=device.serial_number,
            sw_version=device.sw_version,
            hw_version=device.hw_version,
            configuration_url=self.coordinator.client.connection.configuration_url,
        )

    @property
    def reading(self) -> Reading:
        if self.coordinator.data is None:
            return Reading()
        return self.coordinator.data.channels.get(self.channel.id, Reading())

    @property
    def available(self) -> bool:
        reading = self.reading
        if not super().available or not reading.available:
            return False
        return time.monotonic() - reading.observed_at <= self.coordinator.stale_after
