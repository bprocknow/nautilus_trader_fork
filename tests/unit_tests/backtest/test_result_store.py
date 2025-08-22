import importlib.util
import json
import sys
import types
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


repo_root = Path(__file__).resolve().parents[3]
pkg = types.ModuleType("nautilus_trader")
pkg.__path__ = [str(repo_root / "nautilus_trader")]
sys.modules["nautilus_trader"] = pkg

_results = _load_module(
    repo_root / "nautilus_trader" / "backtest" / "results.py",
    "nautilus_trader.backtest.results",
)
_store = _load_module(
    repo_root / "nautilus_trader" / "backtest" / "result_store.py",
    "nautilus_trader.backtest.result_store",
)

BacktestResult = _results.BacktestResult
store_result = _store.store_result


def test_store_result_appends_json(tmp_path: Path) -> None:
    result = BacktestResult(
        trader_id="T",
        machine_id="M",
        run_config_id=None,
        instance_id="I",
        run_id="R",
        run_started=None,
        run_finished=None,
        backtest_start=None,
        backtest_end=None,
        elapsed_time=1.23,
        iterations=10,
        total_events=5,
        total_orders=2,
        total_positions=1,
        stats_pnls={},
        stats_returns={},
    )
    output_file = tmp_path / "results.jsonl"
    store_result(result, "STRAT-1", output_file)

    with output_file.open("r", encoding="utf-8") as f:
        data = json.loads(f.readline())

    assert data["strategy_id"] == "STRAT-1"
    assert data["run_id"] == "R"
