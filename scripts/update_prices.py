"""Refresh data/monthly_prices.csv.

Usage:
    python scripts/update_prices.py              # every ticker
    python scripts/update_prices.py SPY QQQ      # some tickers
    python scripts/update_prices.py --file SPY spy_us_d.csv
        # import a daily CSV saved from stooq.com in a browser

Prices come from Yahoo Finance, adjusted for dividends. If Yahoo fails for a
ticker, Stooq is tried next; Stooq prices are not adjusted for dividends,
which the script reports so the difference is never silent. A ticker that
fails on both keeps its previous snapshot.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dca_vs_lump.prices import (
    PRICES_FILE,
    TICKERS,
    download_stooq,
    download_yahoo,
    load_prices,
    parse_stooq_csv,
    save_prices,
    to_monthly,
)


def fetch(ticker: str, session: requests.Session) -> pd.Series | None:
    try:
        return download_yahoo(ticker)
    except (ValueError, KeyError, requests.RequestException) as exc:
        print(f"{ticker}: Yahoo Finance failed ({exc}), trying Stooq")
    try:
        daily = download_stooq(ticker, session)
    except (ValueError, requests.RequestException) as exc:
        print(f"{ticker}: Stooq failed too ({exc})")
        return None
    print(f"{ticker}: using Stooq prices, NOT adjusted for dividends")
    return daily


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("tickers", nargs="*", help="tickers to refresh (default: all)")
    parser.add_argument("--file", nargs=2, metavar=("TICKER", "PATH"), help="import a Stooq daily CSV")
    args = parser.parse_args()

    prices = load_prices() if PRICES_FILE.exists() else pd.DataFrame()
    today = date.today()
    failed = []

    if args.file:
        ticker = args.file[0].upper()
        daily = parse_stooq_csv(Path(args.file[1]).read_text(encoding="utf-8"), ticker)
        updates = {ticker: daily}
    else:
        session = requests.Session()
        updates = {}
        for ticker in [t.upper() for t in args.tickers] or list(TICKERS):
            daily = fetch(ticker, session)
            if daily is None:
                failed.append(ticker)
            else:
                updates[ticker] = daily

    for ticker, daily in updates.items():
        monthly = to_monthly(daily, today)
        prices = prices.drop(columns=ticker, errors="ignore").join(monthly.rename(ticker), how="outer")
        print(f"{ticker}: {len(monthly)} months, {monthly.index[0]:%Y-%m} to {monthly.index[-1]:%Y-%m}")

    ordered = [t for t in TICKERS if t in prices.columns] + [t for t in prices.columns if t not in TICKERS]
    save_prices(prices[ordered].sort_index())

    if failed:
        print(f"\nNot updated: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
