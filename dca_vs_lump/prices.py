import io
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRICES_FILE = DATA_DIR / "monthly_prices.csv"

TICKERS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq-100",
    "VTI": "US total stock market",
    "VEA": "Developed markets ex-US",
    "AGG": "US aggregate bonds",
    "GLD": "Gold",
}

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"


def to_monthly(daily: pd.Series, today: date) -> pd.Series:
    monthly = daily.dropna().resample("ME").last().dropna()
    # drop the month we're in: it would "end" on whatever day the script ran
    # and the newest window would look a few weeks shorter than the rest
    current = pd.Timestamp(today) + pd.offsets.MonthEnd(0)
    return monthly[monthly.index < current]


def download_yahoo(ticker: str) -> pd.Series:
    frame = yf.download(ticker, period="max", auto_adjust=True, progress=False, multi_level_index=False)
    if frame.empty:
        raise ValueError(f"Yahoo Finance returned no data for {ticker}")
    close = frame["Close"]
    close.index = pd.DatetimeIndex(close.index).tz_localize(None)
    return close.rename(ticker)


def parse_stooq_csv(text: str, ticker: str) -> pd.Series:
    # split-adjusted, NOT dividend-adjusted (SPY ends up ~1.5%/yr low)
    if not text.startswith("Date,"):
        # captcha page comes back as a 200
        raise ValueError(f"Stooq did not return a CSV for {ticker}")
    frame = pd.read_csv(io.StringIO(text), parse_dates=["Date"], index_col="Date")
    return frame["Close"].rename(ticker)


def download_stooq(ticker: str, session: requests.Session) -> pd.Series:
    r = session.get(STOOQ_URL.format(symbol=ticker.lower()), timeout=30)
    r.raise_for_status()
    return parse_stooq_csv(r.text, ticker)


def save_prices(prices: pd.DataFrame, path: Path = PRICES_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(path, index_label="date", float_format="%.4f", date_format="%Y-%m-%d")


def load_prices(path: Path = PRICES_FILE) -> pd.DataFrame:
    return pd.read_csv(path, index_col="date", parse_dates=["date"])
