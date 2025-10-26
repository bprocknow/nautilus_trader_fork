# LLM Strategy Seed

This package contains the seed artifacts that demonstrate how an LLM should
describe, implement, and register Nautilus Trader strategies.

## Components

- `metadata.py` — declarative schema for strategy requirements and packaging.
- `strategies/ema_equity_momentum.py` — baseline EMA crossover algorithm for SPY,
  published together with a `StrategyManifest`.

## Quick Usage

```python
from decimal import Decimal
import sys

# Ensure the `python/` directory is on sys.path when running from the repo root.
sys.path.append("python")

from llm.strategies import EQUITY_EMA_MANIFEST

# Build the default config/strategy pair
config = EQUITY_EMA_MANIFEST.build_config()
strategy = EQUITY_EMA_MANIFEST.build_strategy()

# Override parameters for experimentation
custom = EQUITY_EMA_MANIFEST.build_strategy(
    {"fast_window": 18, "slow_window": 60, "trade_size": Decimal("15")}
)

# Export metadata for downstream orchestration (LLM prompts, registries, etc.)
payload = EQUITY_EMA_MANIFEST.metadata.to_payload()
```

The manifest exposes a `parameter_grid` that downstream tooling can iterate over
to schedule backtests. The LLM can extend this pattern by emitting new strategy
modules plus corresponding manifests.

