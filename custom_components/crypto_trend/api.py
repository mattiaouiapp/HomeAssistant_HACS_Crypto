"""Minimal async client for the CoinGecko v3 public API."""
from __future__ import annotations
import asyncio
from typing import Any
import aiohttp
from .const import API_BASE_URL, API_KEY_HEADER, CHANGE_PERIODS

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
# /coins/markets returns at most this many coins per page.
PAGE_SIZE = 250


class CryptoApiError(Exception):
    """CoinGecko could not be reached or returned garbage."""


class CryptoAuthError(CryptoApiError):
    """The API key was rejected."""


class CryptoRateLimitError(CryptoApiError):
    """Too many requests for the plan in use."""


class CryptoApiClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str | None = None) -> None:
        self._session = session
        self._headers = {"accept": "application/json"}
        if api_key:
            self._headers[API_KEY_HEADER] = api_key

    async def _get(self, endpoint: str, **params: Any) -> Any:
        url = f"{API_BASE_URL}/{endpoint}"
        try:
            async with self._session.get(
                url, params=params, headers=self._headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status == 429:
                    raise CryptoRateLimitError(f"{endpoint}: rate limited")
                if resp.status in (401, 403):
                    raise CryptoAuthError(f"API key rejected ({resp.status})")
                if resp.status == 400:
                    # A Pro key on the public API, or an unknown currency.
                    text = await resp.text()
                    if "key" in text.lower():
                        raise CryptoAuthError(f"API key rejected: {text[:200]}")
                    raise CryptoApiError(f"{endpoint}: {text[:200]}")
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except CryptoApiError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise CryptoApiError(f"{endpoint}: {err}") from err

    async def _markets(self, currency: str, sparkline: bool, **params: Any) -> list[dict[str, Any]]:
        data = await self._get(
            "coins/markets",
            vs_currency=currency,
            order="market_cap_desc",
            sparkline="true" if sparkline else "false",
            price_change_percentage=",".join(CHANGE_PERIODS),
            **params,
        )
        if not isinstance(data, list):
            raise CryptoApiError(f"coins/markets: unexpected response {str(data)[:200]}")
        return [c for c in data if isinstance(c, dict) and c.get("id")]

    async def async_get_markets(self, currency: str, coin_ids: list[str]) -> list[dict[str, Any]]:
        """Price, changes and the 7 day sparkline of the given coins."""
        coins: list[dict[str, Any]] = []
        for start in range(0, len(coin_ids), PAGE_SIZE):
            chunk = coin_ids[start : start + PAGE_SIZE]
            coins += await self._markets(currency, True, ids=",".join(chunk), per_page=PAGE_SIZE)
        return coins

    async def async_get_top(self, currency: str, count: int) -> list[dict[str, Any]]:
        return await self._markets(currency, False, per_page=count, page=1)

    async def async_find_by_symbol(self, currency: str, symbol: str) -> dict[str, Any] | None:
        """The coin with the largest market cap among those using a ticker symbol."""
        coins = await self._markets(currency, False, symbols=symbol.lower(), per_page=10)
        return coins[0] if coins else None
