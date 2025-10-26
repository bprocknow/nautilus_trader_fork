# LLM Trading Agent Roster

This document defines the specialist agents that collaborate to discover, evaluate, and deploy trading strategies in this project. Each agent has a clear mission, expected artifacts, and hand-off rules so that the overall system can be automated or supervised with minimal ambiguity.

## Workflow At A Glance

1. **Research Orchestrator** spins up an end-to-end strategy experiment, tracks metadata, and coordinates the downstream agents.
2. **Strategy Ideator** prompts an LLM to propose trading logic together with parameter grids and instrumentation hooks.
3. **Strategy Sanitizer** performs static validation and safety checks before any strategy code is executed.
4. **Backtest Runner** compiles the candidate strategy, runs parameter sweeps across historical periods, and logs results.
5. **Performance Analyst** scores the backtests, applies risk filters, and tags promising configurations.
6. **Portfolio Selector** compares current champions vs. challengers and updates the live-ready roster.
7. **Live Execution Steward** deploys champion strategies, manages orders, and enforces kill-switch risk controls.
8. **Telemetry Sentinel** monitors live performance, alerts on anomalies, and feeds learnings back to the orchestrator.

The agents communicate via structured artifacts (YAML/JSON manifests, tabular metrics, code bundles) stored under version control or a shared object store. This allows the system to mix automated execution with human-in-the-loop review.

## Agent Profiles

### Research Orchestrator
- **Mission:** Kick off strategy discovery experiments and maintain the experiment ledger.
- **Inputs:** User goals, market universes, capital constraints, historical data catalog.
- **Outputs:** Experiment manifest, agent task graph, storage locations for intermediate artifacts.
- **Tools/Data:** Project configuration (`pyproject.toml`, `Makefile`), run metadata registry (local SQLite or remote DB), task scheduler.
- **Notes:** Responsible for recovering from interruptions and rerouting tasks when an agent fails.

### Strategy Ideator
- **Mission:** Use an LLM to propose trading strategies aligned with experiment goals.
- **Inputs:** Experiment manifest, prompt templates, prior winning strategies, market microstructure notes.
- **Outputs:** Strategy design document, executable code skeleton (Python or Rust), parameter grid, instrumentation hooks.
- **Tools/Data:** Prompt library (`docs/` or `assets/prompts/`), code templates under `nautilus_trader/`, style and risk guidelines.
- **Notes:** Must reference historical context to avoid duplicate ideas and should annotate assumptions explicitly.

### Strategy Sanitizer
- **Mission:** Validate candidate strategy code before execution.
- **Inputs:** Strategy bundle from the ideator (code + metadata).
- **Outputs:** Sanitized strategy package or rejection report.
- **Checks:** Lint/static analysis, adherence to risk guardrails, resource usage caps, dependency whitelist.
- **Tools/Data:** Static analyzers (`ruff`, `cargo clippy`), custom rule sets (`deny.toml`, `clippy.toml`).
- **Notes:** Blocks promotion if any guardrail fails; may suggest auto-fixes when feasible.

### Backtest Runner
- **Mission:** Evaluate strategies across historical data slices and parameter grids.
- **Inputs:** Sanitized strategy package, backtest configuration (time ranges, symbols, fees, latency profiles).
- **Outputs:** Backtest result bundles (performance metrics, fills, logs, equity curves).
- **Tools/Data:** `nautilus_trader` backtesting APIs, historical data under `assets/` or `schema/`, compute resource manager.
- **Notes:** Tags each run with reproducible seeds and environment hashes for auditability.

### Performance Analyst
- **Mission:** Score backtest outputs and identify high-quality configurations.
- **Inputs:** Backtest result bundles, scoring rubric, risk thresholds.
- **Outputs:** Ranked leaderboard, diagnostic plots, stop-list of rejected variants.
- **Metrics:** CAGR, Sharpe/Sortino, max drawdown, hit rate, turnover, slippage sensitivity.
- **Notes:** Flags regimes where performance is unstable and recommends additional data slices when uncertainty is high.

### Portfolio Selector
- **Mission:** Decide which strategies graduate to live trading or simulated forward tests.
- **Inputs:** Ranked leaderboard, capital allocation policy, correlation matrices, live roster state.
- **Outputs:** Updated deployment manifest, capital weights, rotation schedule.
- **Notes:** Ensures diversification targets are met and enforces cooling-off periods after strategy removal.

### Live Execution Steward
- **Mission:** Deploy champion strategies, manage real-time execution, and enforce safety constraints.
- **Inputs:** Deployment manifest, exchange/broker credentials, real-time market data feeds.
- **Outputs:** Order flow, execution reports, live P&L streams, incident logs.
- **Controls:** Position limits, kill switches, latency monitoring, failover routines.
- **Notes:** Integrates with Nautilus Trader execution services and maintains up-to-date runbooks for operators.

### Telemetry Sentinel
- **Mission:** Monitor live performance, detect anomalies, and trigger mitigations.
- **Inputs:** Live telemetry (P&L, risk metrics, order latency), historical baselines, alert thresholds.
- **Outputs:** Alert notifications, post-mortem templates, feedback tickets to the orchestrator.
- **Notes:** Can automatically demote strategies or request more backtests when degradation is detected.

## Collaboration Model

- Agents exchange artifacts through structured manifests stored within the repository or a versioned object store.
- The orchestrator maintains an experiment graph so that downstream agents can run in parallel where dependencies allow.
- Every promotion step (ideation → sanitize → backtest → selection → live) requires an explicit approval record, enabling human sign-off when desired.
- Feedback loops are critical: telemetry findings feed back into the orchestrator, which can schedule fresh ideation or additional validation.

## Implementation Hooks

- Define agent task schemas in `docs/` (e.g., `docs/agents/*.yaml`) to keep prompts and validation steps reproducible.
- Use `scripts/` for automation entry points (`scripts/run_backtest.py`, `scripts/score_leaderboard.py`, etc.).
- Maintain experiment metadata under `assets/experiments/` or an external database for traceability.
- Mirror this document in onboarding materials so contributors understand how to extend or swap agents.

