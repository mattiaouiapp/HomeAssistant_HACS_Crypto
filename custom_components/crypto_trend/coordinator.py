from __future__ import annotations
from datetime import timedelta
from logging import getLogger
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from .api import CryptoApiClient, CryptoApiError, CryptoAuthError
from .const import CONF_COINS, CONF_CURRENCY, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, STALE_AFTER
from .models import CryptoData

_LOGGER = getLogger(__name__)


class CryptoCoordinator(DataUpdateCoordinator[CryptoData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: CryptoApiClient) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=minutes))
        self.config_entry = entry
        self._client = client

    @property
    def currency(self) -> str:
        return self.config_entry.data[CONF_CURRENCY]

    @property
    def coin_ids(self) -> list[str]:
        return list(self.config_entry.options.get(CONF_COINS, []))

    @property
    def is_fresh(self) -> bool:
        """Whether the last prices are recent enough to show, even if the latest update failed."""
        return self.data is not None and dt_util.utcnow() - self.data.fetched < STALE_AFTER

    async def _async_update_data(self) -> CryptoData:
        try:
            raw = await self._client.async_get_markets(self.currency, self.coin_ids)
        except CryptoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CryptoApiError as err:
            raise UpdateFailed(f"CoinGecko request failed: {err}") from err
        if self.coin_ids and not raw:
            raise UpdateFailed("CoinGecko returned none of the configured coins")
        return CryptoData.from_raw(self.currency, raw)
