# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2025 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .results import BacktestResult


def store_result(result: BacktestResult, strategy_id: str, output_path: str | Path) -> None:
    """
    Append a backtest result with metadata to a JSON lines file.
    """
    record: dict[str, Any] = asdict(result)
    record["strategy_id"] = strategy_id

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        json.dump(record, f)
        f.write("\n")
