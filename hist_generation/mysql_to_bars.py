#!/usr/bin/env python3
"""Load Polygon aggregate bars from MySQL for Nautilus backtests.

This utility reads the same ``config.yaml`` file used by ``polygon_to_mysql.py``
and converts the stored OHLCV data into a list of ``Bar`` objects which can be
consumed by the Nautilus Trader backtest engine.

Example
-------
>>> bars, bar_type, instrument = load_bars_from_mysql()
"""
from __future__ import annotations

from typing import Tuple, List

import pandas as pd
import mysql.connector
import yaml

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider

CONFIG_PATH = "hist_generation/config.yaml"


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_bars_from_mysql(config_path: str = CONFIG_PATH) -> Tuple[List[Bar], BarType, object]:
    """Load OHLCV bars from MySQL using the given configuration.

    Parameters
    ----------
    config_path : str
        Path to the YAML configuration file with ``polygon`` and ``mysql``
        sections.

    Returns
    -------
    tuple
        A tuple of ``(bars, bar_type, instrument)`` where ``bars`` is a list of
        :class:`~nautilus_trader.model.data.Bar` objects ready for backtesting.
    """
    cfg = _load_config(config_path)
    poly_cfg = cfg["polygon"]
    mysql_cfg = cfg["mysql"]

    ticker = poly_cfg["stocksTicker"]
    multiplier = int(poly_cfg["multiplier"])
    timespan = poly_cfg["timespan"].lower()

    conn = mysql.connector.connect(
        host=mysql_cfg["host"],
        port=int(mysql_cfg["port"]),
        user=mysql_cfg["username"],
        password=mysql_cfg["password"],
        database=mysql_cfg["database"],
    )

    query = (
        "SELECT dt_utc AS timestamp, `open`, `high`, `low`, `close`, `volume` "
        "FROM aggregates WHERE ticker=%s AND multiplier=%s AND timespan=%s ORDER BY ts_ms"
    )
    df = pd.read_sql(
        query,
        conn,
        params=(ticker, multiplier, timespan),
        parse_dates=["timestamp"],
    )
    conn.close()

    df = df.set_index("timestamp")

    instrument = TestInstrumentProvider.equity(symbol=ticker, venue="XNAS")
    bar_type = BarType.from_str(
        f"{instrument.id}-{multiplier}-{timespan.upper()}-LAST-EXTERNAL"
    )

    wrangler = BarDataWrangler(bar_type, instrument)
    bars: List[Bar] = wrangler.process(df)

    return bars, bar_type, instrument


__all__ = ["load_bars_from_mysql"]
