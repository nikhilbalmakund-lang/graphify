"""Instrument catalogue.

Contract specifications follow common retail CFD conventions with a USD
account. `demo_*` fields parameterise the deterministic DEMO price model only;
they are NOT market data and are never shown as prices.

Provider symbol mappings can be overridden at runtime with the
MARKET_DATA_SYMBOL_MAP environment variable (JSON: {"NAS100": "NDX"}).
"""

from __future__ import annotations

from market_data.models import AssetClass, AssetSpec, SessionType

_DEFAULT_ASSETS: list[AssetSpec] = [
    AssetSpec(
        symbol="XAUUSD",
        name="Gold / US Dollar",
        asset_class=AssetClass.COMMODITIES,
        session=SessionType.CFD,
        base="XAU",
        quote="USD",
        currencies=["USD", "XAU"],
        price_precision=2,
        tick_size=0.01,
        pip_size=0.1,
        contract_size=100,
        min_lot=0.01,
        lot_step=0.01,
        max_lot=50,
        max_leverage=20,
        typical_spread=0.25,
        commission_per_lot=0.0,
        demo_anchor_price=2350.0,
        demo_daily_vol=0.0095,
        demo_base_volume=3200,
        provider_symbols={"twelvedata": "XAU/USD"},
    ),
    AssetSpec(
        symbol="EURUSD",
        name="Euro / US Dollar",
        asset_class=AssetClass.FOREX,
        session=SessionType.FX,
        base="EUR",
        quote="USD",
        currencies=["EUR", "USD"],
        price_precision=5,
        tick_size=0.00001,
        pip_size=0.0001,
        contract_size=100_000,
        min_lot=0.01,
        lot_step=0.01,
        max_lot=50,
        max_leverage=30,
        typical_spread=0.00008,
        commission_per_lot=3.5,
        demo_anchor_price=1.09,
        demo_daily_vol=0.0045,
        demo_base_volume=5200,
        provider_symbols={"twelvedata": "EUR/USD"},
    ),
    AssetSpec(
        symbol="GBPUSD",
        name="British Pound / US Dollar",
        asset_class=AssetClass.FOREX,
        session=SessionType.FX,
        base="GBP",
        quote="USD",
        currencies=["GBP", "USD"],
        price_precision=5,
        tick_size=0.00001,
        pip_size=0.0001,
        contract_size=100_000,
        min_lot=0.01,
        lot_step=0.01,
        max_lot=50,
        max_leverage=30,
        typical_spread=0.00012,
        commission_per_lot=3.5,
        demo_anchor_price=1.27,
        demo_daily_vol=0.0052,
        demo_base_volume=4100,
        provider_symbols={"twelvedata": "GBP/USD"},
    ),
    AssetSpec(
        symbol="USDJPY",
        name="US Dollar / Japanese Yen",
        asset_class=AssetClass.FOREX,
        session=SessionType.FX,
        base="USD",
        quote="JPY",
        currencies=["USD", "JPY"],
        price_precision=3,
        tick_size=0.001,
        pip_size=0.01,
        contract_size=100_000,
        min_lot=0.01,
        lot_step=0.01,
        max_lot=50,
        max_leverage=30,
        typical_spread=0.012,
        commission_per_lot=3.5,
        demo_anchor_price=150.0,
        demo_daily_vol=0.0055,
        demo_base_volume=4800,
        provider_symbols={"twelvedata": "USD/JPY"},
    ),
    AssetSpec(
        symbol="BTCUSD",
        name="Bitcoin / US Dollar",
        asset_class=AssetClass.CRYPTO,
        session=SessionType.CRYPTO,
        base="BTC",
        quote="USD",
        currencies=["USD"],
        price_precision=2,
        tick_size=0.01,
        pip_size=1.0,
        contract_size=1,
        min_lot=0.001,
        lot_step=0.001,
        max_lot=20,
        max_leverage=2,
        typical_spread=15.0,
        commission_pct=0.0006,
        demo_anchor_price=60_000.0,
        demo_daily_vol=0.028,
        demo_base_volume=900,
        provider_symbols={"twelvedata": "BTC/USD"},
    ),
    AssetSpec(
        symbol="ETHUSD",
        name="Ether / US Dollar",
        asset_class=AssetClass.CRYPTO,
        session=SessionType.CRYPTO,
        base="ETH",
        quote="USD",
        currencies=["USD"],
        price_precision=2,
        tick_size=0.01,
        pip_size=0.1,
        contract_size=1,
        min_lot=0.01,
        lot_step=0.01,
        max_lot=200,
        max_leverage=2,
        typical_spread=1.5,
        commission_pct=0.0006,
        demo_anchor_price=3_000.0,
        demo_daily_vol=0.034,
        demo_base_volume=1400,
        provider_symbols={"twelvedata": "ETH/USD"},
    ),
    AssetSpec(
        symbol="NAS100",
        name="Nasdaq 100 Index",
        asset_class=AssetClass.INDICES,
        session=SessionType.CFD,
        base="NAS100",
        quote="USD",
        currencies=["USD"],
        price_precision=1,
        tick_size=0.1,
        pip_size=1.0,
        contract_size=1,
        min_lot=0.1,
        lot_step=0.1,
        max_lot=100,
        max_leverage=20,
        typical_spread=1.2,
        demo_anchor_price=18_000.0,
        demo_daily_vol=0.012,
        demo_base_volume=2600,
        provider_symbols={"twelvedata": "NDX"},
    ),
    AssetSpec(
        symbol="US30",
        name="Dow Jones 30 Index",
        asset_class=AssetClass.INDICES,
        session=SessionType.CFD,
        base="US30",
        quote="USD",
        currencies=["USD"],
        price_precision=1,
        tick_size=0.1,
        pip_size=1.0,
        contract_size=1,
        min_lot=0.1,
        lot_step=0.1,
        max_lot=100,
        max_leverage=20,
        typical_spread=2.0,
        demo_anchor_price=39_000.0,
        demo_daily_vol=0.0085,
        demo_base_volume=2100,
        provider_symbols={"twelvedata": "DJI"},
    ),
    AssetSpec(
        symbol="SPX500",
        name="S&P 500 Index",
        asset_class=AssetClass.INDICES,
        session=SessionType.CFD,
        base="SPX500",
        quote="USD",
        currencies=["USD"],
        price_precision=2,
        tick_size=0.01,
        pip_size=0.1,
        contract_size=1,
        min_lot=0.1,
        lot_step=0.1,
        max_lot=100,
        max_leverage=20,
        typical_spread=0.4,
        demo_anchor_price=5_200.0,
        demo_daily_vol=0.009,
        demo_base_volume=2900,
        provider_symbols={"twelvedata": "SPX"},
    ),
    AssetSpec(
        symbol="USOIL",
        name="WTI Crude Oil",
        asset_class=AssetClass.COMMODITIES,
        session=SessionType.CFD,
        base="WTI",
        quote="USD",
        currencies=["USD"],
        price_precision=2,
        tick_size=0.01,
        pip_size=0.01,
        contract_size=1000,
        min_lot=0.01,
        lot_step=0.01,
        max_lot=50,
        max_leverage=10,
        typical_spread=0.03,
        demo_anchor_price=75.0,
        demo_daily_vol=0.021,
        demo_base_volume=2300,
        provider_symbols={"twelvedata": "WTI/USD"},
    ),
]

DEFAULT_SYMBOLS: list[str] = [a.symbol for a in _DEFAULT_ASSETS]

# Common aliases accepted by search and the command palette.
SYMBOL_ALIASES: dict[str, str] = {
    "GOLD": "XAUUSD",
    "XAU": "XAUUSD",
    "BTC": "BTCUSD",
    "BITCOIN": "BTCUSD",
    "ETH": "ETHUSD",
    "ETHEREUM": "ETHUSD",
    "NASDAQ": "NAS100",
    "NDX": "NAS100",
    "DOW": "US30",
    "DJI": "US30",
    "SPX": "SPX500",
    "SP500": "SPX500",
    "S&P": "SPX500",
    "OIL": "USOIL",
    "WTI": "USOIL",
    "CRUDE": "USOIL",
    "EUR": "EURUSD",
    "GBP": "GBPUSD",
    "CABLE": "GBPUSD",
    "JPY": "USDJPY",
    "YEN": "USDJPY",
}


class AssetCatalog:
    """Registry of tradable instruments. Immutable after construction."""

    def __init__(
        self, assets: list[AssetSpec] | None = None, symbol_overrides: dict[str, dict[str, str]] | None = None
    ):
        items = [a.model_copy(deep=True) for a in (assets or _DEFAULT_ASSETS)]
        if symbol_overrides:
            for a in items:
                for provider, mapping in symbol_overrides.items():
                    if a.symbol in mapping:
                        a.provider_symbols[provider] = mapping[a.symbol]
        self._by_symbol = {a.symbol: a for a in items}

    def all(self) -> list[AssetSpec]:
        return list(self._by_symbol.values())

    def symbols(self) -> list[str]:
        return list(self._by_symbol)

    def get(self, symbol: str) -> AssetSpec:
        resolved = self.resolve(symbol)
        if resolved is None:
            raise KeyError(f"Unknown symbol '{symbol}'")
        return self._by_symbol[resolved]

    def resolve(self, text: str) -> str | None:
        key = text.strip().upper().replace("/", "").replace(" ", "")
        if key in self._by_symbol:
            return key
        alias = SYMBOL_ALIASES.get(key)
        if alias and alias in self._by_symbol:
            return alias
        return None

    def __contains__(self, symbol: str) -> bool:
        return self.resolve(symbol) is not None


DEFAULT_CATALOG = AssetCatalog()
