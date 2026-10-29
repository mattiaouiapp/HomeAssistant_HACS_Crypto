from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from homeassistant.util import dt as dt_util
from .const import (
    CHANGE_PERIODS,
    HISTORY_STEP,
    TREND_DOWN,
    TREND_STABLE,
    TREND_STRONG,
    TREND_STRONG_DOWN,
    TREND_STRONG_UP,
    TREND_UP,
    TREND_WEAK,
)


def _float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def trend_of(change: float | None) -> str | None:
    if change is None:
        return None
    if change >= TREND_STRONG:
        return TREND_STRONG_UP
    if change >= TREND_WEAK:
        return TREND_UP
    if change > -TREND_WEAK:
        return TREND_STABLE
    if change > -TREND_STRONG:
        return TREND_DOWN
    return TREND_STRONG_DOWN


@dataclass(frozen=True)
class Coin:
    id: str
    symbol: str
    name: str
    image: str | None
    rank: int | None
    price: float | None
    market_cap: float | None
    volume_24h: float | None
    high_24h: float | None
    low_24h: float | None
    change_24h: float | None
    ath: float | None
    ath_change: float | None
    ath_date: datetime | None
    circulating_supply: float | None
    last_updated: datetime | None
    # Price change in percent by period ("1h", "24h", "7d", ...).
    changes: dict[str, float | None] = field(default_factory=dict)
    # Hourly prices of the last 7 days, oldest first.
    sparkline: list[float] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Coin:
        changes = {
            period: _float(raw.get(f"price_change_percentage_{period}_in_currency"))
            for period in CHANGE_PERIODS
        }
        if changes.get("24h") is None:
            changes["24h"] = _float(raw.get("price_change_percentage_24h"))
        sparkline = [
            p for p in ((raw.get("sparkline_in_7d") or {}).get("price") or []) if isinstance(p, int | float)
        ]
        rank = raw.get("market_cap_rank")
        return cls(
            id=str(raw["id"]),
            symbol=str(raw.get("symbol") or raw["id"]).upper(),
            name=str(raw.get("name") or raw["id"]),
            image=raw.get("image"),
            rank=int(rank) if isinstance(rank, int | float) else None,
            price=_float(raw.get("current_price")),
            market_cap=_float(raw.get("market_cap")),
            volume_24h=_float(raw.get("total_volume")),
            high_24h=_float(raw.get("high_24h")),
            low_24h=_float(raw.get("low_24h")),
            change_24h=_float(raw.get("price_change_24h")),
            ath=_float(raw.get("ath")),
            ath_change=_float(raw.get("ath_change_percentage")),
            ath_date=dt_util.parse_datetime(raw["ath_date"]) if raw.get("ath_date") else None,
            circulating_supply=_float(raw.get("circulating_supply")),
            last_updated=dt_util.parse_datetime(raw["last_updated"]) if raw.get("last_updated") else None,
            changes=changes,
            sparkline=[float(p) for p in sparkline],
        )

    @property
    def trend(self) -> str | None:
        return trend_of(self.changes.get("24h"))

    def history(self) -> list[float]:
        """The 7 day sparkline thinned out to keep the state attributes small, ending on the latest point."""
        if not self.sparkline:
            return []
        points = self.sparkline[::-1][::HISTORY_STEP][::-1]
        return [_round(p) for p in points]

    @property
    def range_7d(self) -> tuple[float, float] | None:
        if not self.sparkline:
            return None
        return min(self.sparkline), max(self.sparkline)


def _round(value: float) -> float:
    """Keep 5 significant digits, enough for a chart of any price."""
    return float(f"{value:.5g}")


def precision(price: float | None) -> int:
    """Decimals worth showing for a price: 2 for 1 and above, more for cheap coins."""
    if price is None or price >= 1:
        return 2
    if price >= 0.01:
        return 4
    if price >= 0.0001:
        return 6
    return 8


@dataclass
class CryptoData:
    currency: str
    coins: dict[str, Coin]
    fetched: datetime

    @classmethod
    def from_raw(cls, currency: str, raw: list[dict[str, Any]]) -> CryptoData:
        return cls(
            currency=currency,
            coins={c.id: c for c in (Coin.from_raw(r) for r in raw)},
            fetched=dt_util.utcnow(),
        )
