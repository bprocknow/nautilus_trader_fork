#!/usr/bin/env python3
"""
Run a minimal backtest using data stored in MySQL.

The database must first be populated with Polygon aggregate bars using
``hist_generation/polygon_to_mysql.py``.  This script then loads the bars and
executes a simple EMA cross strategy using the Nautilus Trader backtest engine.

"""
from decimal import Decimal
from typing import Any, cast

from hist_generation.mysql_to_bars import load_bars_from_mysql
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.result_store import store_result
from nautilus_trader.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.examples.strategies.ema_cross_long_only import EMACrossLongOnly
from nautilus_trader.examples.strategies.ema_cross_long_only import EMACrossLongOnlyConfig
from nautilus_trader.model import TraderId
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.objects import Money


if __name__ == "__main__":
    bars, bar_type, instrument = load_bars_from_mysql()
    instrument = cast(Any, instrument)

    engine = BacktestEngine(
        config=BacktestEngineConfig(
            trader_id=TraderId("BACKTEST_TRADER-001"),
            logging=LoggingConfig(log_level="INFO"),
        ),
    )

    engine.add_venue(
        venue=instrument.id.venue,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        starting_balances=[Money(100_000, USD)],
        base_currency=USD,
        default_leverage=Decimal(1),
    )

    engine.add_instrument(instrument)
    engine.add_data(bars)

    strategy = EMACrossLongOnly(
        EMACrossLongOnlyConfig(
            instrument_id=instrument.id,
            bar_type=bar_type,
            trade_size=Decimal(100),
        ),
    )
    engine.add_strategy(strategy)

    engine.run()
    result = engine.get_result()
    store_result(result, strategy.id.value, "examples/backtest/results.jsonl")
    engine.dispose()
