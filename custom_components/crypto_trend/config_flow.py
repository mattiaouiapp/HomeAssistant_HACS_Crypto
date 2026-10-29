from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from .api import CryptoApiClient, CryptoApiError, CryptoAuthError
from .const import (
    CONF_API_KEY,
    CONF_COINS,
    CONF_CURRENCY,
    CONF_SCAN_INTERVAL,
    CURRENCIES,
    DEFAULT_COINS,
    DEFAULT_CURRENCY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TOP_COINS,
    api_key_of,
)


class InvalidCoins(Exception):
    def __init__(self, unknown: list[str]) -> None:
        super().__init__(", ".join(unknown))
        self.unknown = unknown


async def _top_coins(hass: HomeAssistant, currency: str, api_key: str | None) -> list[SelectOptionDict]:
    """The largest coins for the dropdown; empty when CoinGecko cannot be reached."""
    client = CryptoApiClient(async_get_clientsession(hass), api_key)
    try:
        coins = await client.async_get_top(currency, TOP_COINS)
    except CryptoApiError:
        return []
    return [
        SelectOptionDict(value=c["id"], label=f"{c.get('name', c['id'])} ({str(c.get('symbol', '')).upper()})")
        for c in coins
    ]


async def _resolve(hass: HomeAssistant, currency: str, api_key: str | None, coins: list[str]) -> list[str]:
    """CoinGecko IDs of the chosen coins, which may also be typed as ticker symbols (btc).

    Raises InvalidCoins with the ones CoinGecko does not know.
    """
    client = CryptoApiClient(async_get_clientsession(hass), api_key)
    wanted = list(dict.fromkeys(c.strip().lower() for c in coins if c.strip()))
    found = {c["id"] for c in await client.async_get_markets(currency, wanted)}
    ids: list[str] = []
    unknown: list[str] = []
    for coin in wanted:
        if coin in found:
            ids.append(coin)
        elif match := await client.async_find_by_symbol(currency, coin):
            ids.append(match["id"])
        else:
            unknown.append(coin)
    if unknown:
        raise InvalidCoins(unknown)
    return list(dict.fromkeys(ids))


def _coins_selector(options: list[SelectOptionDict], selected: list[str]) -> SelectSelector:
    # Keep coins outside the top list (or every coin, when the list could not be loaded) selectable.
    known = {o["value"] for o in options}
    options = options + [SelectOptionDict(value=c, label=c) for c in selected if c not in known]
    return SelectSelector(
        SelectSelectorConfig(
            options=options, multiple=True, custom_value=True, sort=False, mode=SelectSelectorMode.DROPDOWN
        )
    )


def _interval_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL,
            max=MAX_SCAN_INTERVAL,
            step=1,
            unit_of_measurement="min",
            mode=NumberSelectorMode.BOX,
        )
    )


class CryptoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._currency = DEFAULT_CURRENCY
        self._api_key: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """First the currency and the optional key, then the coins priced in it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._currency = user_input[CONF_CURRENCY].strip().lower()
            self._api_key = user_input.get(CONF_API_KEY, "").strip() or None
            await self.async_set_unique_id(self._currency)
            self._abort_if_unique_id_configured()
            client = CryptoApiClient(async_get_clientsession(self.hass), self._api_key)
            try:
                await client.async_get_top(self._currency, 1)
            except CryptoAuthError:
                errors["base"] = "invalid_api_key"
            except CryptoApiError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_coins()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CURRENCY, default=self._currency): SelectSelector(
                        SelectSelectorConfig(
                            options=CURRENCIES, custom_value=True, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Optional(CONF_API_KEY, default=self._api_key or ""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_coins(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"unknown": ""}
        selected = DEFAULT_COINS
        if user_input is not None:
            selected = user_input.get(CONF_COINS) or []
            try:
                coins = await _resolve(self.hass, self._currency, self._api_key, selected)
            except InvalidCoins as err:
                errors["base"] = "unknown_coins"
                placeholders["unknown"] = ", ".join(err.unknown)
            except CryptoApiError:
                errors["base"] = "cannot_connect"
            else:
                if not coins:
                    errors["base"] = "no_coins"
                else:
                    return self.async_create_entry(
                        title=f"Crypto {self._currency.upper()}",
                        data={CONF_CURRENCY: self._currency, CONF_API_KEY: self._api_key},
                        options={CONF_COINS: coins, CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                    )

        options = await _top_coins(self.hass, self._currency, self._api_key)
        return self.async_show_form(
            step_id="coins",
            data_schema=vol.Schema(
                {vol.Required(CONF_COINS, default=selected): _coins_selector(options, selected)}
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY, "").strip() or None
            client = CryptoApiClient(async_get_clientsession(self.hass), api_key)
            try:
                await client.async_get_top(entry.data[CONF_CURRENCY], 1)
            except CryptoAuthError:
                errors["base"] = "invalid_api_key"
            except CryptoApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_API_KEY: api_key},
                    options={k: v for k, v in entry.options.items() if k != CONF_API_KEY},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_API_KEY, default=""): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return CryptoOptionsFlow()


class CryptoOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"unknown": ""}
        entry = self.config_entry
        currency = entry.data[CONF_CURRENCY]
        current_key = api_key_of(entry) or ""
        selected = list(entry.options.get(CONF_COINS, []))
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY, "").strip() or None
            selected = user_input.get(CONF_COINS) or []
            interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            try:
                coins = await _resolve(self.hass, currency, api_key, selected)
            except InvalidCoins as err:
                errors["base"] = "unknown_coins"
                placeholders["unknown"] = ", ".join(err.unknown)
            except CryptoAuthError:
                errors["base"] = "invalid_api_key"
            except CryptoApiError:
                errors["base"] = "cannot_connect"
            else:
                if not coins:
                    errors["base"] = "no_coins"
                else:
                    return self.async_create_entry(
                        data={CONF_COINS: coins, CONF_SCAN_INTERVAL: interval, CONF_API_KEY: api_key}
                    )

        options = await _top_coins(self.hass, currency, current_key or None)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COINS, default=selected): _coins_selector(options, selected),
                    vol.Required(CONF_SCAN_INTERVAL, default=interval): _interval_selector(),
                    vol.Optional(CONF_API_KEY, default=current_key): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
