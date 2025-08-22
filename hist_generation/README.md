# Historical Data Generation and Backtesting

This directory contains utilities for fetching historical data and loading it
into a MySQL database as well as helpers to convert that data for Nautilus
Trader backtests.

## Usage

1. **Fetch data from Polygon and populate MySQL**

   ```bash
   python hist_generation/polygon_to_mysql.py --config hist_generation/config.yaml
   ```

   Ensure the `config.yaml` file contains valid Polygon and MySQL credentials.

2. **Run a backtest using the stored bars**

   ```bash
   python examples/backtest/mysql_backtest_demo.py
   ```

   The script loads the bars from MySQL, converts them to Nautilus Trader
   objects and executes a simple EMA cross strategy.
