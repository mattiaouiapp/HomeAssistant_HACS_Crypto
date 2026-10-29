from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import CryptoConfigEntry
from .const import TREND_DOWN, TREND_STABLE, TREND_STRONG_DOWN, TREND_STRONG_UP, TREND_UP, TRENDS
from .coordinator import CryptoCoordinator
from .entity import CryptoEntity
from .models import Coin, precision

TREND_ICONS = {
    TREND_STRONG_UP: "mdi:rocket-launch",
    TREND_UP: "mdi:trending-up",
    TREND_STABLE: "mdi:trending-neutral",
    TREND_DOWN: "mdi:trending-down",
    TREND_STRONG_DOWN: "mdi:arrow-down-bold",
}


@dataclass(frozen=True, kw_only=True)
class CryptoSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Coin], Any]
    attrs_fn: Callable[[Coin], dict[str, Any]] | None = None
    # The value is an amount in the configured currency.
    monetary: bool = False


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _price_attrs(coin: Coin) -> dict[str, Any]:
    low, high = coin.range_7d or (None, None)
    return {
        "coin_id": coin.id,
        "symbol": coin.symbol,
        "coin_name": coin.name,
        "image": coin.image,
        "rank": coin.rank,
        "trend": coin.trend,
        "change_24h": coin.change_24h,
        **{f"change_{period}_pct": value for period, value in coin.changes.items()},
        "low_7d": low,
        "high_7d": high,
        "history_7d": coin.history(),
        "last_updated": _iso(coin.last_updated),
    }


def _change(period: str, enabled: bool = True) -> CryptoSensorDescription:
    return CryptoSensorDescription(
        key=f"change_{period}",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:percent-outline",
        entity_registry_enabled_default=enabled,
        value_fn=lambda c: c.changes.get(period),
    )


SENSORS: tuple[CryptoSensorDescription, ...] = (
    CryptoSensorDescription(
        key="price",
        monetary=True,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:bitcoin",
        value_fn=lambda c: c.price,
        attrs_fn=_price_attrs,
    ),
    _change("1h"),
    _change("24h"),
    _change("7d"),
    _change("30d"),
    _change("1y", enabled=False),
    CryptoSensorDescription(
        key="trend",
        device_class=SensorDeviceClass.ENUM,
        options=TRENDS,
        value_fn=lambda c: c.trend,
    ),
    CryptoSensorDescription(
        key="high_24h",
        monetary=True,
        icon="mdi:arrow-collapse-up",
        value_fn=lambda c: c.high_24h,
    ),
    CryptoSensorDescription(
        key="low_24h",
        monetary=True,
        icon="mdi:arrow-collapse-down",
        value_fn=lambda c: c.low_24h,
    ),
    CryptoSensorDescription(
        key="ath_distance",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:summit",
        value_fn=lambda c: c.ath_change,
        attrs_fn=lambda c: {"ath": c.ath, "ath_date": _iso(c.ath_date)},
    ),
    CryptoSensorDescription(
        key="market_cap",
        monetary=True,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:chart-pie",
        value_fn=lambda c: c.market_cap,
        attrs_fn=lambda c: {"circulating_supply": c.circulating_supply},
    ),
    CryptoSensorDescription(
        key="volume_24h",
        monetary=True,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:swap-horizontal",
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.volume_24h,
    ),
    CryptoSensorDescription(
        key="rank",
        icon="mdi:podium",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.rank,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: CryptoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        CryptoSensor(coordinator, coin, description)
        for coin in coordinator.data.coins.values()
        for description in SENSORS
    )


class CryptoSensor(CryptoEntity, SensorEntity):
    entity_description: CryptoSensorDescription
    # The 7 day chart changes on every update: keep it out of the database.
    _unrecorded_attributes = frozenset({"history_7d"})

    def __init__(self, coordinator: CryptoCoordinator, coin: Coin, description: CryptoSensorDescription) -> None:
        super().__init__(coordinator, Platform.SENSOR, coin, description.key)
        self.entity_description = description
        if description.monetary:
            self._attr_native_unit_of_measurement = coordinator.currency.upper()
            if description.suggested_display_precision is None:
                self._attr_suggested_display_precision = precision(coin.price)

    @property
    def native_value(self) -> Any:
        coin = self.coin
        return None if coin is None else self.entity_description.value_fn(coin)

    @property
    def icon(self) -> str | None:
        if self.entity_description.key == "trend" and (coin := self.coin) is not None:
            return TREND_ICONS.get(coin.trend or "", "mdi:chart-line")
        return super().icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        coin = self.coin
        if coin is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(coin)
