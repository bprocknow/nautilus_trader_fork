"""
Baseline equity momentum strategy for LLM-driven experimentation.

The implementation mirrors the structure expected by Nautilus Trader so that
subsequent LLM-generated strategies can follow the same template: define a
config, implement the strategy behaviour, and describe requirements via a
``StrategyManifest``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd

from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import PositiveInt
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy

from ..metadata import (
    BacktestSpec,
    DataSpec,
    ParameterSpec,
    StrategyManifest,
    StrategyMetadata,
)


class EquityEmaCrossConfig(StrategyConfig, frozen=True):
    """
    Configuration for ``EquityEmaCrossStrategy`` instances.

    Parameters
    ----------
    instrument_id : InstrumentId
        The instrument ID for the primary trading symbol.
    bar_type : BarType
        The bar type used for signal generation.
    trade_size : Decimal
        The notional quantity per trade (shares for equities).
    fast_window : int
        EMA lookback for the fast moving average.
    slow_window : int
        EMA lookback for the slow moving average (must be greater than fast).
    warmup_days : int
        Historical bar span requested on start to warm up indicators.
    subscribe_trade_ticks : bool, default True
        Subscribe to trade ticks for richer telemetry.
    subscribe_quote_ticks : bool, default False
        Subscribe to quote ticks.
    request_historical_bars : bool, default True
        Request historical bars during warmup.
    close_positions_on_stop : bool, default True
        Close open positions on strategy stop.
    order_time_in_force : TimeInForce, optional
        Explicit time in force for market orders.

    """

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_window: PositiveInt = 20
    slow_window: PositiveInt = 50
    warmup_days: PositiveInt = 5
    subscribe_trade_ticks: bool = True
    subscribe_quote_ticks: bool = False
    request_historical_bars: bool = True
    close_positions_on_stop: bool = True
    order_time_in_force: TimeInForce | None = None


class EquityEmaCrossStrategy(Strategy):
    """
    Long-only EMA crossover strategy suitable for equity backtests.
    """

    def __init__(self, config: EquityEmaCrossConfig) -> None:
        PyCondition.is_true(
            config.fast_window < config.slow_window,
            "{config.fast_window=} must be less than {config.slow_window=}",
        )
        super().__init__(config)

        self.instrument: Instrument | None = None

        self.fast_ema = ExponentialMovingAverage(config.fast_window)
        self.slow_ema = ExponentialMovingAverage(config.slow_window)
        self._previous_spread: float | None = None

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Instrument not available for {self.config.instrument_id}")
            self.stop()
            return

        self.register_indicator_for_bars(self.config.bar_type, self.fast_ema)
        self.register_indicator_for_bars(self.config.bar_type, self.slow_ema)

        if self.config.request_historical_bars:
            lookback = pd.Timedelta(days=int(self.config.warmup_days))
            self.request_bars(
                self.config.bar_type,
                start=self._clock.utc_now() - lookback,
            )

        self.subscribe_bars(self.config.bar_type)
        if self.config.subscribe_trade_ticks:
            self.subscribe_trade_ticks(self.config.instrument_id)
        if self.config.subscribe_quote_ticks:
            self.subscribe_quote_ticks(self.config.instrument_id)

    def on_bar(self, bar: Bar) -> None:
        self.log.debug(
            f"Bar received {bar.instrument_id} close={bar.close}",
            color=LogColor.BLUE,
        )

        if not self.indicators_initialized():
            return

        spread = float(self.fast_ema.value - self.slow_ema.value)
        if self._previous_spread is None:
            self._previous_spread = spread
            return

        crossed_up = self._previous_spread <= 0.0 and spread > 0.0
        crossed_down = self._previous_spread >= 0.0 and spread < 0.0

        if crossed_up:
            if self.portfolio.is_flat(self.config.instrument_id):
                self._enter_long()
            elif self.portfolio.is_net_short(self.config.instrument_id):
                self.close_all_positions(self.config.instrument_id)
                self._enter_long()
        elif crossed_down and self.portfolio.is_net_long(self.config.instrument_id):
            self.close_all_positions(self.config.instrument_id)

        self._previous_spread = spread

    def _enter_long(self) -> None:
        order: MarketOrder = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.BUY,
            quantity=self._create_order_qty(),
            time_in_force=self.config.order_time_in_force or TimeInForce.GTC,
        )
        self.submit_order(order)

    def _create_order_qty(self) -> Quantity:
        return self.instrument.make_qty(self.config.trade_size)  # type: ignore[union-attr]

    def on_stop(self) -> None:
        self.cancel_all_orders(self.config.instrument_id)
        if self.config.close_positions_on_stop:
            self.close_all_positions(self.config.instrument_id)

        self.unsubscribe_bars(self.config.bar_type)
        if self.config.subscribe_trade_ticks:
            self.unsubscribe_trade_ticks(self.config.instrument_id)
        if self.config.subscribe_quote_ticks:
            self.unsubscribe_quote_ticks(self.config.instrument_id)

    def on_reset(self) -> None:
        self.fast_ema.reset()
        self.slow_ema.reset()
        self._previous_spread = None


DEFAULT_INSTRUMENT = InstrumentId.from_str("SPY.XNAS")
DEFAULT_BAR_TYPE = BarType.from_str("SPY.XNAS-15-MINUTE-LAST-EXTERNAL")

EQUITY_EMA_METADATA = StrategyMetadata(
    strategy_id="equity_ema_crossover",
    display_name="Equity EMA Crossover (Long Only)",
    summary=(
        "Long-only EMA crossover on SPY 15-minute bars with configurable window sizes "
        "and share quantity. Serves as the seed blueprint for LLM-generated variants."
    ),
    tags=("equities", "momentum", "baseline"),
    data=DataSpec(
        instrument_id=DEFAULT_INSTRUMENT,
        bar_type=DEFAULT_BAR_TYPE,
        warmup="7D",
        subscribe_trade_ticks=True,
        subscribe_quote_ticks=False,
        request_historical_bars=True,
    ),
    parameters=(
        ParameterSpec(
            name="fast_window",
            type_hint="int",
            description="Exponential moving average lookback for the fast signal.",
            default=20,
            min_value=5,
            max_value=40,
        ),
        ParameterSpec(
            name="slow_window",
            type_hint="int",
            description="Exponential moving average lookback for the slow signal.",
            default=50,
            min_value=30,
            max_value=120,
        ),
        ParameterSpec(
            name="trade_size",
            type_hint="decimal",
            description="Number of shares to trade per signal.",
            default="10",
            min_value=1,
            max_value=100,
        ),
    ),
    backtest=BacktestSpec(
        start=datetime(2022, 1, 1, tzinfo=timezone.utc),
        end=datetime(2023, 1, 1, tzinfo=timezone.utc),
        initial_cash=Decimal("100000"),
        slippage_bps=1.0,
        commission_bps=0.5,
        benchmark_symbol="SPY",
    ),
    risk_notes=(
        "This starter strategy is long-only and does not place protective stops "
        "beyond exiting on the reverse crossover. Apply additional risk overlays "
        "before live deployment."
    ),
    prompt_context=(
        "Focus on U.S. equity ETFs with liquid intraday data. Signals should adapt "
        "to changing volatility regimes while respecting long-only mandate."
    ),
)

EQUITY_EMA_MANIFEST = StrategyManifest[EquityEmaCrossConfig, EquityEmaCrossStrategy](
    metadata=EQUITY_EMA_METADATA,
    config_cls=EquityEmaCrossConfig,
    strategy_cls=EquityEmaCrossStrategy,
    default_config={
        "instrument_id": DEFAULT_INSTRUMENT,
        "bar_type": DEFAULT_BAR_TYPE,
        "trade_size": Decimal("10"),
        "fast_window": 20,
        "slow_window": 50,
        "warmup_days": 7,
        "subscribe_trade_ticks": True,
        "subscribe_quote_ticks": False,
        "request_historical_bars": True,
        "close_positions_on_stop": True,
        "order_time_in_force": TimeInForce.DAY,
    },
    parameter_grid={
        "fast_window": (12, 18, 24),
        "slow_window": (48, 60, 72),
        "trade_size": (Decimal("5"), Decimal("10"), Decimal("15")),
    },
)

