"""
Metadata primitives describing LLM-generated trading strategies.

These dataclasses capture the information a downstream automation stack needs in
order to build, backtest, and evaluate strategies produced by an LLM. They are
lightweight enough to be serialized to JSON, while still carrying strongly
typed Nautilus Trader objects for direct integration.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence, TypeVar, Generic

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy


StrategyConfigT = TypeVar("StrategyConfigT", bound=StrategyConfig)
StrategyT = TypeVar("StrategyT", bound=Strategy)


@dataclass(slots=True)
class ParameterSpec:
    """
    Metadata describing a tunable strategy parameter.
    """

    name: str
    type_hint: str
    description: str
    default: Any | None = None
    min_value: float | Decimal | None = None
    max_value: float | Decimal | None = None
    choices: Sequence[Any] | None = None
    tunable: bool = True

    def to_payload(self) -> dict[str, Any]:
        """
        Represent the parameter spec as JSON-serializable payload.
        """
        payload: dict[str, Any] = {
            "name": self.name,
            "type_hint": self.type_hint,
            "description": self.description,
            "default": self.default,
            "tunable": self.tunable,
        }
        if self.min_value is not None:
            payload["min_value"] = float(self.min_value)
        if self.max_value is not None:
            payload["max_value"] = float(self.max_value)
        if self.choices is not None:
            payload["choices"] = list(self.choices)
        return payload


@dataclass(slots=True)
class DataSpec:
    """
    Data feed requirements for a strategy.
    """

    instrument_id: InstrumentId
    bar_type: BarType
    warmup: str = "3D"
    subscribe_trade_ticks: bool = True
    subscribe_quote_ticks: bool = False
    request_historical_bars: bool = True

    def to_payload(self) -> dict[str, Any]:
        """
        Represent the data specification as JSON-serializable payload.
        """
        return {
            "instrument_id": str(self.instrument_id),
            "bar_type": str(self.bar_type),
            "warmup": self.warmup,
            "subscribe_trade_ticks": self.subscribe_trade_ticks,
            "subscribe_quote_ticks": self.subscribe_quote_ticks,
            "request_historical_bars": self.request_historical_bars,
        }


@dataclass(slots=True)
class BacktestSpec:
    """
    Default backtest context for a strategy.
    """

    start: datetime
    end: datetime
    initial_cash: Decimal
    slippage_bps: float = 1.0
    commission_bps: float = 0.0
    benchmark_symbol: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """
        Represent the backtest specification as JSON-serializable payload.
        """
        payload: dict[str, Any] = {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "initial_cash": float(self.initial_cash),
            "slippage_bps": self.slippage_bps,
            "commission_bps": self.commission_bps,
        }
        if self.benchmark_symbol is not None:
            payload["benchmark_symbol"] = self.benchmark_symbol
        return payload


@dataclass(slots=True)
class StrategyMetadata:
    """
    Human and machine-readable description of a strategy artifact.
    """

    strategy_id: str
    display_name: str
    summary: str
    version: str = "0.1.0"
    author: str = "llm-agent"
    tags: tuple[str, ...] = ()
    data: DataSpec | None = None
    parameters: tuple[ParameterSpec, ...] = ()
    backtest: BacktestSpec | None = None
    risk_notes: str | None = None
    prompt_context: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """
        Represent the metadata as JSON-serializable payload.
        """
        payload: dict[str, Any] = {
            "strategy_id": self.strategy_id,
            "display_name": self.display_name,
            "summary": self.summary,
            "version": self.version,
            "author": self.author,
            "tags": list(self.tags),
        }
        if self.data is not None:
            payload["data"] = self.data.to_payload()
        if self.parameters:
            payload["parameters"] = [param.to_payload() for param in self.parameters]
        if self.backtest is not None:
            payload["backtest"] = self.backtest.to_payload()
        if self.risk_notes is not None:
            payload["risk_notes"] = self.risk_notes
        if self.prompt_context is not None:
            payload["prompt_context"] = self.prompt_context
        return payload


@dataclass(slots=True)
class StrategyManifest(Generic[StrategyConfigT, StrategyT]):
    """
    Bundles strategy metadata together with the concrete config/strategy classes.
    """

    metadata: StrategyMetadata
    config_cls: type[StrategyConfigT]
    strategy_cls: type[StrategyT]
    default_config: Mapping[str, Any]
    parameter_grid: Mapping[str, Sequence[Any]] | None = None

    def build_config(self, overrides: Mapping[str, Any] | None = None) -> StrategyConfigT:
        """
        Instantiate the strategy configuration with optional overrides.
        """
        config_kwargs: dict[str, Any] = copy.deepcopy(dict(self.default_config))
        if overrides:
            config_kwargs.update(overrides)
        return self.config_cls(**config_kwargs)

    def build_strategy(self, overrides: Mapping[str, Any] | None = None) -> StrategyT:
        """
        Instantiate the strategy using the resolved configuration.
        """
        return self.strategy_cls(self.build_config(overrides))

    def iter_parameter_grid(self) -> Iterable[Mapping[str, Any]]:
        """
        Yield parameter combinations if a grid has been supplied.
        """
        if not self.parameter_grid:
            return

        import itertools

        keys = list(self.parameter_grid.keys())
        values_product = itertools.product(*(self.parameter_grid[key] for key in keys))
        for values in values_product:
            yield dict(zip(keys, values))


@dataclass(slots=True)
class StrategyPackage(Generic[StrategyConfigT, StrategyT]):
    """
    Container that couples a manifest with resolved configuration instances.
    """

    manifest: StrategyManifest[StrategyConfigT, StrategyT]
    config: StrategyConfigT
    strategy: StrategyT

    def to_payload(self) -> dict[str, Any]:
        """
        Render a serializable payload describing the package.
        """
        payload = self.manifest.metadata.to_payload()
        payload["config"] = self.config.json_primitives()
        return payload

