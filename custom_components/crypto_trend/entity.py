from __future__ import annotations
from datetime import datetime, timedelta
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from .const import ATTRIBUTION, COIN_URL, DOMAIN
from .coordinator import CryptoCoordinator
from .models import Coin

# Repeated failed updates do not reach the entities, so they check this often whether
# their prices have gone stale.
STALE_CHECK = timedelta(minutes=1)


def device_identifier(entry_id: str, coin_id: str) -> tuple[str, str]:
    return DOMAIN, f"{entry_id}_{coin_id}"


class CryptoEntity(CoordinatorEntity[CryptoCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: CryptoCoordinator, platform: str, coin: Coin, key: str) -> None:
        super().__init__(coordinator)
        self.coin_id = coin.id
        entry_id = coordinator.config_entry.entry_id
        currency = coordinator.currency
        self._attr_unique_id = f"{entry_id}_{coin.id}_{key}"
        self._attr_translation_key = key
        # Fixed entity IDs whatever the UI language, so the bundled dashboard always works.
        self.entity_id = f"{platform}.crypto_{slugify(coin.id)}_{slugify(currency)}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={device_identifier(entry_id, coin.id)},
            name=f"{coin.name} ({currency.upper()})",
            manufacturer="CoinGecko",
            model=coin.symbol,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=COIN_URL.format(coin_id=coin.id),
        )

    @property
    def coin(self) -> Coin | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.coins.get(self.coin_id)

    @property
    def available(self) -> bool:
        # Ride out a short CoinGecko outage or rate limit, but never show old prices as current.
        return self.coordinator.is_fresh and self.coin is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_interval(self.hass, self._async_check_stale, STALE_CHECK))

    @callback
    def _async_check_stale(self, _now: datetime) -> None:
        state = self.hass.states.get(self.entity_id)
        if state is not None and (state.state != STATE_UNAVAILABLE) != self.available:
            self.async_write_ha_state()
