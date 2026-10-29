from __future__ import annotations
from datetime import timedelta

DOMAIN = "crypto_trend"
NAME = "MMOUi Crypto"
ATTRIBUTION = "Data provided by CoinGecko"

CONF_API_KEY = "api_key"
CONF_COINS = "coins"
CONF_CURRENCY = "currency"
CONF_SCAN_INTERVAL = "scan_interval"

API_BASE_URL = "https://api.coingecko.com/api/v3"
# Demo keys (free, from the CoinGecko developer dashboard) raise the rate limit
# of the public API; without a key it is a few requests per minute.
API_KEY_HEADER = "x-cg-demo-api-key"
COIN_URL = "https://www.coingecko.com/en/coins/{coin_id}"

DEFAULT_CURRENCY = "eur"
CURRENCIES = ["eur", "usd", "gbp", "chf", "jpy", "cad", "aud", "btc", "eth"]
DEFAULT_COINS = ["bitcoin", "ethereum", "solana"]
# Coins offered in the setup dropdown, by market cap.
TOP_COINS = 100

# One request per update covers every coin, so even the keyless limit is far away.
DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 60
# Prices older than this are no longer shown.
STALE_AFTER = timedelta(minutes=30)

# Price changes requested next to the 24 h one CoinGecko always returns.
CHANGE_PERIODS = ("1h", "24h", "7d", "30d", "1y")
# The hourly 7 day sparkline is kept every this many points (every 4 hours).
HISTORY_STEP = 4

# Trend of the last 24 hours, from the price change in percent.
TREND_STRONG = 5.0
TREND_WEAK = 1.0
TREND_STRONG_UP = "strong_up"
TREND_UP = "up"
TREND_STABLE = "stable"
TREND_DOWN = "down"
TREND_STRONG_DOWN = "strong_down"
TRENDS = [TREND_STRONG_UP, TREND_UP, TREND_STABLE, TREND_DOWN, TREND_STRONG_DOWN]


def api_key_of(entry) -> str | None:
    """The key set in the options wins, even when cleared there, over the one given at setup."""
    if CONF_API_KEY in entry.options:
        return entry.options[CONF_API_KEY] or None
    return entry.data.get(CONF_API_KEY) or None
