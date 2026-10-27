"""Native, read-only connection to a DEOS COSMOS controller."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CONTROLLER_SERIAL,
    CONF_INFO_PORT,
    DEFAULT_INFO_PORT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .coordinator import DeosCoordinator
from .cosmos import Connection, CosmosClient
from .models import INVENTORY

type DeosConfigEntry = ConfigEntry[DeosCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DeosConfigEntry) -> bool:
    """Connect once, then forward native entity platforms."""
    if CONF_HOST not in entry.data:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="reconfigure_required")
    client = CosmosClient(
        async_get_clientsession(hass),
        Connection(
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data.get(CONF_INFO_PORT, DEFAULT_INFO_PORT),
        ),
    )
    coordinator = DeosCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    device = coordinator.device
    if entry.title == f"{device.manufacturer} {device.model}":
        hass.config_entries.async_update_entry(entry, title=device.model)
    _async_align_entity_ids(hass, entry)
    _async_clear_default_name_overrides(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def _async_align_entity_ids(hass: HomeAssistant, entry: DeosConfigEntry) -> None:
    """Apply the channel-only naming once, without taking another entity's ID."""
    if entry.minor_version >= 2:
        return
    registry = er.async_get(hass)
    own = {
        entity.unique_id: entity
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.platform == DOMAIN
    }
    renames = []
    for channel in INVENTORY:
        current = own.get(f"{entry.unique_id}_{channel.id.lower()}")
        if current is None or current.entity_id == channel.entity_id:
            continue
        if registry.async_get(channel.entity_id) or hass.states.get(channel.entity_id):
            LOGGER.warning(
                "Entity ID %s is already in use; keeping existing IDs", channel.entity_id
            )
            return
        renames.append((current.entity_id, channel.entity_id))
    for previous, target in renames:
        registry.async_update_entity(previous, new_entity_id=target)
    hass.config_entries.async_update_entry(entry, minor_version=2)


@callback
def _async_clear_default_name_overrides(hass: HomeAssistant, entry: DeosConfigEntry) -> None:
    """Remove the previous default-name override once, preserving distinct custom names."""
    if entry.minor_version < 2 or entry.minor_version >= 3:
        return
    registry = er.async_get(hass)
    labels = {
        f"{entry.unique_id}_{channel.id.lower()}": channel.name.title() for channel in INVENTORY
    }
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        label = labels.get(entity.unique_id)
        if entity.platform == DOMAIN and label is not None and entity.name == label:
            registry.async_update_entity(entity.entity_id, name=None)
    hass.config_entries.async_update_entry(entry, minor_version=3)


async def async_unload_entry(hass: HomeAssistant, entry: DeosConfigEntry) -> bool:
    """Unload entities and cancel polling, without closing HA's shared session."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: DeosConfigEntry) -> bool:
    """Upgrade configuration entries while preserving their identities."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        data = {CONF_SCAN_INTERVAL: entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)}
        registered = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, entry.unique_id), entry.entry_id
        )
        if registered and registered.serial_number:
            data[CONF_CONTROLLER_SERIAL] = registered.serial_number
        hass.config_entries.async_update_entry(entry, data=data, version=2, minor_version=1)
    return True
