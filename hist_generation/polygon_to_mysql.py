#!/usr/bin/env python3
import argparse
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml
from polygon import RESTClient
import mysql.connector
from mysql.connector.connection import MySQLConnection


# ---------- Config loading ----------

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _as_bool(v: Any, default: bool = True) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def resolve_polygon_cfg(cfg: dict, ticker_override: Optional[str]) -> dict:
    """
    Support the 'polygon' block you used earlier:
      polygon:
        apiKey, stocksTicker, multiplier, timespan, start_date, end_date, adjusted?, sort?, limit?
    Also allow env override STOCK_TICKER and CLI --ticker.
    """
    if "polygon" not in cfg:
        raise ValueError("config.yaml must contain a 'polygon' section")

    p = cfg["polygon"].copy()
    if ticker_override:
        p["stocksTicker"] = ticker_override
    p["stocksTicker"] = os.getenv("STOCK_TICKER", p.get("stocksTicker", ""))

    # defaults
    p.setdefault("multiplier", 1)
    p.setdefault("timespan", "minute")
    p.setdefault("adjusted", "true")
    p.setdefault("sort", "asc")
    p.setdefault("limit", 50_000)

    # normalize types
    p["multiplier"] = int(p["multiplier"])
    p["limit"] = int(p["limit"])
    p["adjusted"] = _as_bool(p.get("adjusted"), True)
    p["sort"] = p["sort"] if p["sort"] in ("asc", "desc") else "asc"

    required = ["apiKey", "stocksTicker", "start_date", "end_date", "timespan", "multiplier"]
    missing = [k for k in required if not p.get(k)]
    if missing:
        raise ValueError(f"Missing polygon config fields: {', '.join(missing)}")

    return p


def resolve_mysql_cfg(cfg: dict) -> dict:
    if "mysql" not in cfg:
        raise ValueError("config.yaml must contain a 'mysql' section")
    m = cfg["mysql"]
    required = ["host", "port", "database", "username", "password"]
    missing = [k for k in required if not m.get(k)]
    if missing:
        raise ValueError(f"Missing MySQL config fields: {', '.join(missing)}")
    return m


# ---------- MySQL helpers ----------

CREATE_DB_SQL = "CREATE DATABASE IF NOT EXISTS `{db}` /* created by polygon_to_mysql */"
USE_DB_SQL = "USE `{db}`"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `aggregates` (
  `ticker`        VARCHAR(16)  NOT NULL,
  `multiplier`    INT          NOT NULL,
  `timespan`      VARCHAR(16)  NOT NULL,
  `ts_ms`         BIGINT       NOT NULL,
  `dt_utc`        DATETIME     NOT NULL,
  `open`          DECIMAL(18,6) NOT NULL,
  `high`          DECIMAL(18,6) NOT NULL,
  `low`           DECIMAL(18,6) NOT NULL,
  `close`         DECIMAL(18,6) NOT NULL,
  `volume`        BIGINT       NULL,
  `vwap`          DECIMAL(18,6) NULL,
  `transactions`  INT          NULL,
  PRIMARY KEY (`ticker`, `multiplier`, `timespan`, `ts_ms`),
  KEY `idx_dt` (`dt_utc`),
  KEY `idx_ticker_dt` (`ticker`, `dt_utc`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

INSERT_SQL = """
INSERT INTO `aggregates`
(`ticker`,`multiplier`,`timespan`,`ts_ms`,`dt_utc`,`open`,`high`,`low`,`close`,`volume`,`vwap`,`transactions`)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
  `open`=VALUES(`open`),
  `high`=VALUES(`high`),
  `low`=VALUES(`low`),
  `close`=VALUES(`close`),
  `volume`=VALUES(`volume`),
  `vwap`=VALUES(`vwap`),
  `transactions`=VALUES(`transactions`)
"""


def mysql_connect(mysql_cfg: dict) -> MySQLConnection:
    conn = mysql.connector.connect(
        host=mysql_cfg["host"],
        port=int(mysql_cfg["port"]),
        user=mysql_cfg["username"],
        password=mysql_cfg["password"],
        database=mysql_cfg.get("database"),
        autocommit=False,
    )
    return conn


def mysql_prepare(conn: MySQLConnection, dbname: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(CREATE_DB_SQL.format(db=dbname))
        cur.execute(USE_DB_SQL.format(db=dbname))
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        cur.close()


def chunked(iterable: List[Tuple], size: int) -> Iterable[List[Tuple]]:
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


# ---------- Polygon fetch + transform ----------

def _get_attr(obj: Any, *names: str, default=None):
    # Support both dict-like and attribute-style fields with short or long names
    for n in names:
        if isinstance(obj, dict):
            if n in obj:
                return obj[n]
        else:
            if hasattr(obj, n):
                return getattr(obj, n)
    return default


def _to_row(
    rec: Any,
    ticker: str,
    multiplier: int,
    timespan: str,
) -> Tuple:
    """
    Map Polygon aggregate record to SQL row.
    Supports both short-form (v,vw,o,c,h,l,t,n) and long-form names.
    """
    ts_ms = int(_get_attr(rec, "t", "timestamp"))
    # Some clients may return seconds—defend against it
    if ts_ms < 10_000_000_000:  # seconds epoch
        ts_ms *= 1000

    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None)

    o = _get_attr(rec, "o", "open", default=None)
    h = _get_attr(rec, "h", "high", default=None)
    l = _get_attr(rec, "l", "low", default=None)
    c = _get_attr(rec, "c", "close", default=None)
    v = _get_attr(rec, "v", "volume", default=None)
    vw = _get_attr(rec, "vw", "vwap", default=None)
    n = _get_attr(rec, "n", "transactions", default=None)

    # Ensure numeric types are safe for MySQL
    def to_num(x):
        if x is None:
            return None
        try:
            return float(x)
        except Exception:
            return None

    return (
        ticker,
        multiplier,
        timespan,
        ts_ms,
        dt,
        to_num(o),
        to_num(h),
        to_num(l),
        to_num(c),
        int(v) if v is not None and not isinstance(v, bool) else None,
        to_num(vw),
        int(n) if n is not None and not isinstance(n, bool) else None,
    )


def fetch_aggregates(
    client: RESTClient,
    *,
    ticker: str,
    multiplier: int,
    timespan: str,
    start_date: str,
    end_date: str,
    adjusted: bool,
    sort: str,
    limit: int,
    retries: int = 5,
    backoff_base: float = 0.75,
) -> List[Any]:
    """
    Pull aggregates using Polygon's generator, with simple retry/backoff.
    """
    items: List[Any] = []
    attempt = 0
    while True:
        try:
            for a in client.list_aggs(
                ticker=ticker,
                multiplier=multiplier,
                timespan=timespan,
                from_=start_date,
                to=end_date,
                adjusted=adjusted,
                sort=sort,
                limit=limit,
            ):
                items.append(a.__dict__ if hasattr(a, "__dict__") else a)
            break  # success
        except Exception as e:
            attempt += 1
            if attempt > retries:
                raise
            sleep_s = backoff_base * (2 ** (attempt - 1))
            print(f"[WARN] list_aggs failed (attempt {attempt}/{retries}): {e}. Backing off {sleep_s:.2f}s")
            time.sleep(sleep_s)
    return items


# ---------- Main flow ----------

def main():
    parser = argparse.ArgumentParser(description="Populate MySQL from Polygon aggregates (no Airbyte).")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML configuration file")
    parser.add_argument("--ticker", help="Override ticker symbol")
    parser.add_argument("--start", help="Override start date (YYYY-MM-DD or ms epoch)")
    parser.add_argument("--end", help="Override end date (YYYY-MM-DD or ms epoch)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per INSERT batch")
    args = parser.parse_args()

    cfg = load_config(args.config)
    poly = resolve_polygon_cfg(cfg, args.ticker)
    mysql_cfg = resolve_mysql_cfg(cfg)

    if args.start:
        poly["start_date"] = args.start
    if args.end:
        poly["end_date"] = args.end

    client = RESTClient(api_key=poly["apiKey"])

    print(f"Fetching {poly['timespan']}-bars for {poly['stocksTicker']} "
          f"{poly['start_date']} → {poly['end_date']} (limit={poly['limit']}, sort={poly['sort']})")

    recs = fetch_aggregates(
        client,
        ticker=poly["stocksTicker"],
        multiplier=poly["multiplier"],
        timespan=poly["timespan"],
        start_date=poly["start_date"],
        end_date=poly["end_date"],
        adjusted=poly["adjusted"],
        sort=poly["sort"],
        limit=poly["limit"],
    )

    print(f"Fetched {len(recs)} records. Preparing MySQL…")

    conn = mysql_connect(mysql_cfg)
    try:
        mysql_prepare(conn, mysql_cfg["database"])
        rows = [_to_row(r, poly["stocksTicker"], poly["multiplier"], poly["timespan"]) for r in recs]

        total = 0
        cur = conn.cursor()
        try:
            for batch in chunked(rows, args.batch_size):
                cur.executemany(INSERT_SQL, batch)
                conn.commit()
                total += len(batch)
                print(f"Inserted/updated {total}/{len(rows)}…")
        finally:
            cur.close()

        print(f"Done. Upserted {total} rows into `{mysql_cfg['database']}`.`aggregates`.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

