from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import CryptoApiClient
from .const import api_key_of
from .coordinator import CryptoCoordinator
from .entity import device_identifier

PLATFORMS: list[Platform] = [Platform.SENSOR]

type CryptoConfigEntry = ConfigEntry[CryptoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CryptoConfigEntry) -> bool:
    client = CryptoApiClient(async_get_clientsession(hass), api_key_of(entry))
    coordinator = CryptoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Coins removed in the options take their device and entities with them.
    registry = dr.async_get(hass)
    keep = {device_identifier(entry.entry_id, coin_id) for coin_id in coordinator.coin_ids}
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not device.identifiers & keep:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: CryptoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CryptoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
